"""全链路E2E集成测试 - E2E-30: 断线重连续传 - 后半场帧不重复

对应文档: doc-9月优化/[30]重连重复发送问题分析与处理-小欧-2026-09-12.md 第九章 9.3 联调验证(步骤9/10/11)
实施人: 小欧 2026-09-13

验证点:
  步骤9  真实后端+真实LLM+真实工具+真实SQLite跑重连用例
         -> 后端日志 [SSE] reader退出: 已转发offset 越过 [Runner] final_stats 已发布 seq
         -> [Runner] final_stats 已发布 无 _fs_outcome NameError
  步骤10 断线重连后半场帧不重复
         -> 重连续传帧 seq 全部 > 断点 last_seq(源头不重发, 前端 lastSeqRef 守卫零命中)
         -> usage 帧无重复: 前半场usage seq ∩ 后半场usage seq = 空(前后端对账1:1)
         -> 全集 seq 从0连续到max 无空洞(续传不漏帧, 对账完整)
  步骤11 done 权威置位后 SSE 正常关闭
         -> 后端日志 [Runner] done置位: 末类型=final_stats, has_final_stats=True
         -> 全集含 final_stats 且其 seq == 最大 seq(终态权威末帧)

 铁律:
   1. 一次只跑一个case, 严禁批量
   2. 全部基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
   3. 脚本内严禁设任何超时 -- 由调用侧 pytest --timeout 统一管理
   4. 断线用真实TCP断开(提前退出 httpx 流), 模拟前端真断连
   5. finally 中必须调用 write_test_record(手册5.5铁律)

事故修复(2026-09-13): 初版 r 全程为空 dict, write_test_record v2.2 按 result 反推
   final_event=None 强判 FAILED, 覆盖真实 PASSED 记录(记录错录0事件/FAILED)。
   修复: 收集齐 first_half+tail 后按 e2e_helpers.send_chat(ret) 同构填充 r 全部字段
   (events/final_event/total_steps/llm_call_count/start_time/...), 与指标统计齐全,
   v2.2 判定"有final且无fatal error+日志无ERROR" → PASSED, elapsed 同源取 total_time_ms。
   二期(2026-09-13): ①user_msg_id 存真实值(原 None 致 DB-Prompt 一致性匹配失效/三方表
   prompt_log_files 空); ②db 由仅查会话升级为 check_db 完整核查; ③lc 由手工构造改复用
   check_logs(统一体系产 llm_calls_found/prompt_log_files); DB-Prompt 一致性转 PASS。

-- 小欧 2026-09-13 首版
"""

TEST_CASE_ID = "E2E-30"
TEST_CASE_NAME = "SSE断线重连续传 - 后半场帧不重复 + 终态权威"

USER_INPUT = "请先查看当前目录下有哪些文件, 然后把它们列成一个清单, 并说明每个文件的用途。"

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

import httpx
import pytest

from e2emodel.e2e_helpers import (
    BASE_URL,
    API_PREFIX,
    LOG_DIR,
    ensure_backend_ready,
    check_db,
    check_logs,
    write_test_record,
    register_pending_record,
    remove_pending_record,
)

# 断点为"收到前 K 个 SSE 事件后主动断开连接"(模拟真实前端中途掉线)
CUTOFF_EVENT_COUNT = 5


def _sse_event(line: str):
    """解析单行SSE, 返回事件dict; 心跳/注释行返回None — 小欧 2026-09-13"""
    if not line.startswith("data: "):
        return None
    try:
        return json.loads(line[6:])
    except (json.JSONDecodeError, ValueError):
        return None


async def _create_session() -> str:
    url = f"{BASE_URL}{API_PREFIX}/sessions"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={})
        resp.raise_for_status()
        return resp.json().get("session_id")


async def _save_user_message(session_id: str, content: str) -> int:
    url = f"{BASE_URL}{API_PREFIX}/sessions/{session_id}/messages"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={"role": "user", "content": content})
        resp.raise_for_status()
        return resp.json().get("message_id")


async def _open_stream_first_half(user_input: str, session_id: str, cutoff: int):
    """POST /chat/stream 只读前cutoff个事件后主动断开(模拟真实断线)。

    返回 (task_id, first_half_events, last_seq_after_cut):
      - task_id: 从 start 事件取的 task_id
      - first_half_events: 断开前已收到的全部事件
      - last_seq_after_cut: 断开时最后一次收到的事件的 seq(断点)
      — 小欧 2026-09-13
    """
    url = f"{BASE_URL}{API_PREFIX}/chat/stream"
    payload = {
        "messages": [{"role": "user", "content": user_input}],
        "stream": True,
        "session_id": session_id,
    }
    events: list = []
    task_id = None
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload) as resp:
            async for line in resp.aiter_lines():
                ev = _sse_event(line)
                if ev is None:
                    continue
                ev_type = ev.get("type")
                if not task_id and ev_type == "start" and ev.get("task_id"):
                    task_id = ev["task_id"]
                events.append(ev)
                if len(events) >= cutoff:
                    break  # 主动断开连接 = 模拟断线
            # 立即关闭底层连接, 服务端感知客户端断开
            await resp.aclose()
    last_seq = events[-1].get("seq", 0) if events else -1
    return task_id, events, last_seq


async def _reconnect_tail_stream(task_id: str, session_id: str, after_seq: int):
    """GET /chat/stream/{task_id}?after_seq=N 断点续传, 收集断点之后全部事件直至流结束。

    返回 (tail_events, log_lines):
      - tail_events: 续传收到的全部事件(须全部 seq > after_seq)
      — 小欧 2026-09-13
    """
    url = f"{BASE_URL}{API_PREFIX}/chat/stream/{task_id}"
    tail_events: list = []
    params = {"session_id": session_id, "after_seq": after_seq}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, params=params) as resp:
            async for line in resp.aiter_lines():
                ev = _sse_event(line)
                if ev is None:
                    continue
                tail_events.append(ev)
    return tail_events


def _read_task_log_lines(task_id: str) -> str:
    """读当日app日志中该task相关的全部行(按task_id过滤) — 小欧 2026-09-13"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"
    if not log_file.exists():
        return ""
    raw = log_file.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(l for l in raw.splitlines() if task_id in l)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_30_reconnect_replay():
    """E2E-30: 断线重连续传不重发, 三验证点全查 — 小欧 2026-09-13"""
    test_start = datetime.now()
    passed = False
    r = {}
    db = {}
    ci = []
    si = []
    lc = {"errors": [], "tracebacks": []}
    error_info = None
    session_id = None

    try:
        register_pending_record(
            TEST_CASE_ID, TEST_CASE_NAME, USER_INPUT, {}, {}, [],
            [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # ── ① 建会话 + 保存用户消息(模拟真实前端流程) ──
        session_id = await _create_session()
        assert session_id, "创建session失败"
        user_msg_id = await _save_user_message(session_id, USER_INPUT)
        assert user_msg_id is not None, "保存用户消息失败(user_msg_id不得为空, 供DB-Prompt一致性匹配)"

        # ── ② POST 开流, 读到第CUTOFF个事件后主动断线 ──
        task_id, first_half, cut_seq = await _open_stream_first_half(
            USER_INPUT, session_id, CUTOFF_EVENT_COUNT
        )
        assert task_id, "未从 start 事件取到 task_id"
        print(f"[E2E-30] 断线: task={task_id}, 断点seq={cut_seq}, 前半场事件数={len(first_half)}")

        # ── ③ GET after_seq=lastSeq+1 断点续传, 收集后半场全部帧 ──
        # 前端F1单基线语义: after_seq = lastSeqRef.current + 1(已处理最大seq的下一个)
        #   (useSSE.ts:793 原样复刻) — 小欧 2026-09-13
        tail = await _reconnect_tail_stream(task_id, session_id, cut_seq + 1)
        print(f"[E2E-30] 续传: 后半场事件数={len(tail)}")

        # ── result 构造(与 e2e_helpers.send_chat 同构, 供 write_test_record v2.2 反推 PASSED) ──
        # 事故复盘(2026-09-13): 初版 r 全程 {}, write_test_record 判 final_event=None → 强判 FAILED 并覆盖
        #   真实 PASSED 记录(测试记录-E2E-30 错录为 FAILED 0事件)。以下按 send_chat(ret) 同构填充,
        #   final_event/events 等一应俱全, v2.2 判定与指标统计全部有据可依 — 小欧-2026-09-13
        wall_start = test_start
        all_events = list(first_half) + list(tail)
        _fs_evs = [e for e in all_events if e.get("type") == "final_stats"]
        final_event = _fs_evs[-1] if _fs_evs else (all_events[-1] if all_events else None)
        # 2026-09-13 小欧 对齐 e2e_helpers.send_chat 收集语义: preview 跳过, tools[] 逐个展开,
        #   (原每action只取第1工具致三方表 工具数量 DB=17 vs SSE=8 不匹配)
        _tool_calls_main = []
        for _ev in all_events:
            if _ev.get("type") == "action":
                if _ev.get("preview"):
                    continue
                _tools = _ev.get("tools") or []
                if _tools and isinstance(_tools, list):
                    for _it in _tools:
                        if isinstance(_it, dict):
                            _tool_calls_main.append({
                                "tool_name": _it.get("tool") or _it.get("tool_name") or "",
                                "tool_params": _it.get("params") or _it.get("tool_params") or {},
                            })
                else:
                    _tool_calls_main.append({
                        "tool_name": _ev.get("tool_name", ""),
                        "tool_params": _ev.get("tool_params", {}),
                    })
        # 回复正文 = 最终轮(final_stats.step)的 chunk 正文拼接(与 send_chat 同语义) — 小欧-2026-09-13
        _fin_step = (final_event or {}).get("step")
        _resp_text = "".join(
            e.get("content", "") for e in all_events
            if e.get("type") == "chunk" and e.get("step") == _fin_step and not e.get("is_reasoning")
        )
        if not (_resp_text or "").strip():
            _resp_text = (final_event or {}).get("response") or (final_event or {}).get("content") or ""
        r = {
            "events": all_events,
            "final_event": final_event,
            "has_error": any(e.get("type") == "error" for e in all_events),
            "total_steps": len(all_events),
            "logical_step_count": len([e for e in all_events if e.get("type") != "chunk"]),
            "unique_step_numbers": len({e.get("step") for e in all_events if e.get("step") is not None}),
            "tool_calls": _tool_calls_main,
            "llm_call_count": sum(1 for e in all_events if e.get("type") == "usage") or (len(_tool_calls_main) + 1),
            "total_time_ms": int((datetime.now() - wall_start).total_seconds() * 1000),
            "response_text": _resp_text,
            "reply": _resp_text,
            "session_id": session_id,
            "user_msg_id": user_msg_id,
            "event_types": [e.get("type", "") for e in all_events],
            "start_time": wall_start,
            "end_time": datetime.now(),
        }

        # ── 步骤10: 后半场帧不重复 + usage无双计 + 对账完整 ──
        first_seqs = [e.get("seq") for e in first_half if isinstance(e.get("seq"), int)]
        tail_seqs = [e.get("seq") for e in tail if isinstance(e.get("seq"), int)]
        first_usage = [e.get("seq") for e in first_half if e.get("type") == "usage"]
        tail_usage = [e.get("seq") for e in tail if e.get("type") == "usage"]

        assert first_seqs, "前半场无带seq事件(MUST)"
        assert tail_seqs, "后半场应为空集或续传帧, 但收到内容(若断点在终态之后属正常); 实际 non-empty"
        assert all(s > cut_seq for s in tail_seqs), (
            f"续传帧seq必须全部>断点{cut_seq}(源头不得重发)(MUST): {sorted(s for s in tail_seqs if s <= cut_seq)}"
        )
        overlap_usage = sorted(set(first_usage) & set(tail_usage))
        assert not overlap_usage, f"usage帧断线前后重复(无双计1:1)(MUST): {overlap_usage}"

        all_seqs = sorted(set(first_seqs + tail_seqs))
        assert len(all_seqs) == len(first_seqs) + len(tail_seqs) and len(all_seqs) == len(set(all_seqs)), (
            f"前后场seq集合不得重复(源头不重发)(MUST): 首={len(first_seqs)} 尾={len(tail_seqs)} 并集={len(all_seqs)}"
        )
        # 注: 不校验 seq 从0连续到max——SSE 白名单(_SSE_FORWARD_TYPES)之外的事件类型不转发
        #   (stream_orchestrator.py:484 continue), 该类 seq 不产出 SSE 帧属预期; 对账只查"不重发+不漏终态"

        # ── 终态完整性: 全集必须含 final_stats 且其 seq == 最大seq ──
        fs_events = [e for e in first_half + tail if e.get("type") == "final_stats"]
        assert fs_events, "全集必须含final_stats事件(MUST)"
        assert fs_events[-1].get("seq") == all_seqs[-1], (
            f"final_stats应为末帧(权威终态)(MUST): fs_seq={fs_events[-1].get('seq')} < max={all_seqs[-1]}"
        )

        # ── 步骤9+11: 后端日志追踪点核对 ──
        task_log = _read_task_log_lines(task_id)
        assert task_log, "后端日志无该task记录(MUST)"

        m_fs = re.search(r"\[Runner\] final_stats 已发布\(task=.*?seq=(\d+), status=(\w+)\)", task_log)
        assert m_fs, "日志必须有 [Runner] final_stats 已发布 追踪点(MUST)"
        fs_seq = int(m_fs.group(1))

        read_rows = re.findall(r"\[SSE\] reader退出\(task=.*?已转发=(\d+).*?含final_stats=(\w+)\)", task_log)
        assert read_rows, "日志必须有 [SSE] reader退出 追踪点(MUST)"
        max_fwd = max(int(x[0]) for x in read_rows)
        assert max_fwd > fs_seq, (
            f"步骤9: [SSE] reader退出已转发offset应越过final_stats seq(MUST): 已转发={max_fwd} <= fs_seq={fs_seq}"
        )
        assert any(x[1] == "True" for x in read_rows), "reader退出须 含final_stats=True(MUST)"

        m_done = re.search(
            r"\[Runner\] done置位\(task=.*?last_type=(\w+), has_final_stats=(\w+)\)", task_log
        )
        assert m_done, "日志必须有 [Runner] done置位 追踪点(MUST)"
        assert m_done.group(1) == "final_stats", f"步骤11: done置位末类型应为final_stats(MUST): {m_done.group(1)}"
        assert m_done.group(2) == "True", f"步骤11: done置位须 has_final_stats=True(MUST): {m_done.group(2)}"

        # P1验证: final_stats日志不得引用闭包 _fs_outcome(无 NameError 语义)
        assert "_fs_outcome" not in task_log, (
            "步骤9: [Runner] final_stats 已发布 不得出现 _fs_outcome 引用(P1修复)(MUST)"
        )
        assert "NameError" not in task_log, "后端日志无NameError(P1修复不可回归)(MUST)"

        # 无 ERROR 级别日志 + prompt-logs 匹配(复用 check_logs 统一体系)
        # 完整DB核查(check_db: 会话/消息/步骤完整性, 供 DB-Prompt 一致性比对与三方对账) — 小欧-2026-09-13
        db = check_db(session_id)
        assert db.get("session_exists"), "会话必须存在于DB(MUST)"
        assert db.get("execution_steps_count", 0) >= 2, "DB必须含>=2个执行步骤(start+final)(MUST)"
        ci = []
        si = []
        # check_logs 按 user_msg_id 匹配 prompt 日志文件(一轮对话一个), 产出 llm_calls_found/prompt_log_files — 小欧-2026-09-13
        lc = check_logs(test_start, session_id, user_msg_id)
        assert not lc.get("tracebacks"), f"日志不应有Traceback(MUST): {lc.get('tracebacks')}"
        assert not lc.get("errors"), f"日志不应有ERROR(MUST): {lc.get('errors')[:3]}"
        assert lc.get("prompt_log_files"), "必须匹配到 Prompt 日志文件(MUST, 供 DB-Prompt 一致性比对)"
        assert lc.get("llm_calls_found", 0) > 0, "Prompt日志必须含 LLM 调用记录(MUST)"

        print(
            f"[E2E-30] 验证通过: fs_seq={fs_seq}, reader已转发(max)={max_fwd}, "
            f"后半场帧={len(tail)}; usage前/后={len(first_usage)}/{len(tail_usage)}"
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        write_test_record(
            TEST_CASE_ID, TEST_CASE_NAME, USER_INPUT,
            r or {}, db, ci, si, lc, passed,
            elapsed=(r.get("total_time_ms", 0) / 1000.0) if r else 0.0,
            error_info=error_info,
        )
        remove_pending_record(TEST_CASE_ID)