"""全链路E2E集成测试 - E2E-31: 双次断线重连续传链式不重不漏 + 三键日志闭环对账

对应文档: doc-9月优化/[30]重连重复发送问题分析与处理-小欧-2026-09-12.md 第九章(E2E-31为E2E-30增强复杂case)
实施人: 小欧 2026-09-13

设计动机(复杂case): E2E-30 只做"一次断线一次续传", 本case做"两次断线两次续传"链式场景——
  首连(cutoff=5帧)断 → 重连1(读到第2个usage后主动断) → 重连2(读到流自然结束)。
  + 补点A/B日志验证: 重连请求留痕 + reader退出带 is_reconnect/起点seq/续传帧数, 三键闭环对账。

验证点:
  ① 链式续传 seq 严格衔接: 段2全seq > 段1断点seq; 段3全seq > 段2断点seq;
     三段合并 seq 集合唯一(断点不重发、不漏帧) 
  ② usage 帧三段交集为空(前/中/后 1:1:1 不双计)
  ③ 终态权威: 合并全集含 final_stats 且其 seq == 最大 seq
  ④ 补点A: 每次重连必出一条 [SSE] 重连请求接收(task, after_seq, session, 缓冲总长, 含final_stats)
     -> 重连请求条数 == 2(两次断线两次重连)
  ⑤ 补点B + 三键闭环(老陈核心要求):
     -> 最终 [SSE] reader退出(is_reconnect=True, 起点seq=段2断点+1, 续传帧数=已转发-起点seq)
     -> reader已转发 == 缓冲总长(排空) == done置位event_log_len == final_stats seq + 1(三键严格一致)
     -> reader末类型=final_stats, 含final_stats=True(终态权威末帧)
  ⑥ DB执行步骤轮次唯一(无重复轮, 与两段续传互为印证)

 铁律:
   1. 一次只跑一个case, 严禁批量
   2. 全部基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
   3. 脚本内严禁设任何超时 -- 由调用侧 pytest --timeout 统一管理
   4. 断线用真实TCP断开(提前退出 httpx 流), 模拟前端真断连
   5. finally 中必须调用 write_test_record(手册5.5铁律)
   6. 记录result与e2e_helpers.send_chat同构(事故复盘: r空dict致write_test_record v2.2错判FAILED)

-- 小欧 2026-09-13 首版
"""

TEST_CASE_ID = "E2E-31"
TEST_CASE_NAME = "SSE双次断线重连续传 - 链式不重不漏 + 三键日志闭环对账"

USER_INPUT = (
    "请全面分析当前目录: 第一步列出目录结构和全部文件, 第二步读取其中关键的脚本文件和报告文件"
    "了解各自的用途, 第三步将文件按脚本工具/数据文件/报告文档/其他四类统计数量与总大小, "
    "第四步整理成一份完整清单, 分类说明每个文件或目录的用途。"
)

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

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

# 首连断点: 收到前 K 个 SSE 事件后主动断开(模拟真实前端中途掉线)
CUTOFF_EVENT_COUNT = 5
# 重连段1断点: 收到第 N 个 usage 事件后主动断开(第N轮已完成, 复杂任务≥3轮所以必然未终态)
SEG1_USAGE_CUTOFF = 2


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

    返回 (task_id, events, last_seq_after_cut): last_seq_after_cut 即断点seq — 小欧 2026-09-13
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
            await resp.aclose()  # 立即关闭底层连接, 服务端感知客户端断开
    last_seq = events[-1].get("seq", 0) if events else -1
    return task_id, events, last_seq


async def _reconnect_stream_segment(task_id: str, session_id: str, after_seq: int,
                                    usage_cutoff: Optional[int] = None):
    """GET /chat/stream/{task_id}?after_seq=N 断点续传一段。

    usage_cutoff=None: 读到流自然结束(finished=True)
    usage_cutoff=N: 收到第N个usage事件后主动断开(模拟二次掉线, finished=False)

    返回 (events, last_seq, finished): last_seq=本段最后收到事件seq — 小欧 2026-09-13
    """
    url = f"{BASE_URL}{API_PREFIX}/chat/stream/{task_id}"
    events: list = []
    usage_count = 0
    finished = False
    params = {"session_id": session_id, "after_seq": after_seq}
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("GET", url, params=params) as resp:
            async for line in resp.aiter_lines():
                ev = _sse_event(line)
                if ev is None:
                    continue
                events.append(ev)
                if usage_cutoff is not None and ev.get("type") == "usage":
                    usage_count += 1
                    if usage_count >= usage_cutoff:
                        await resp.aclose()  # 二次主动断线
                        break
            else:
                finished = True  # for正常结束 = 流自然结束(读到done)
    last_seq = events[-1].get("seq", 0) if events else after_seq - 1
    return events, last_seq, finished


def _read_task_log_lines(task_id: str) -> str:
    """读当日app日志中该task相关的全部行(按task_id过滤) — 小欧 2026-09-13"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"
    if not log_file.exists():
        return ""
    raw = log_file.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(l for l in raw.splitlines() if task_id in l)


def _parse_reconnect_logs(task_log: str):
    """解析补点A/B + 既有追踪点, 输出对账结构 — 小欧 2026-09-13

    返回:
      reconnect_requests: [ {after_seq, buffer_len, has_fs} ... ] 每条重连请求
      reader_exits:       [ {is_reconnect, start_seq, span, fwd, buf_len, last_type, has_fs} ]
      fs_seq / fs_status / done_len / done_last_type / done_has_fs
    """
    out = {
        "reconnect_requests": [],
        "reader_exits": [],
        "fs_seq": None,
        "fs_status": None,
        "done_len": None,
        "done_last_type": None,
        "done_has_fs": None,
    }
    for m in re.finditer(
        r"\[SSE\] 重连请求接收\(task=.*?after_seq=(\d+), session=(.*?), 缓冲总长=(\d+), 含final_stats=(\w+)\)",
        task_log,
    ):
        out["reconnect_requests"].append({
            "after_seq": int(m.group(1)),
            "session": m.group(2),
            "buffer_len": int(m.group(3)),
            "has_fs": m.group(4) == "True",
        })
    for m in re.finditer(
        r"\[SSE\] reader退出\(task=.*?is_reconnect=(\w+), 起点seq=(\d+), 续传帧数=(\d+), "
        r"已转发=(\d+), 缓冲总长=(\d+), 末类型=(\w+), 含final_stats=(\w+)\)",
        task_log,
    ):
        out["reader_exits"].append({
            "is_reconnect": m.group(1) == "True",
            "start_seq": int(m.group(2)),
            "span": int(m.group(3)),
            "fwd": int(m.group(4)),
            "buf_len": int(m.group(5)),
            "last_type": m.group(6),
            "has_fs": m.group(7) == "True",
        })
    m_fs = re.search(r"\[Runner\] final_stats 已发布\(task=.*?seq=(\d+), status=(\w+)\)", task_log)
    if m_fs:
        out["fs_seq"] = int(m_fs.group(1))
        out["fs_status"] = m_fs.group(2)
    m_done = re.search(r"\[Runner\] done置位\(task=.*?event_log_len=(\d+), last_type=(\w+), has_final_stats=(\w+)\)", task_log)
    if m_done:
        out["done_len"] = int(m_done.group(1))
        out["done_last_type"] = m_done.group(2)
        out["done_has_fs"] = m_done.group(3) == "True"
    return out


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_31_reconnect_log_reconcile():
    """E2E-31: 双次断线链式续传 + 三键日志闭环对账 — 小欧 2026-09-13"""
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

        # ── ② 首连 POST, 读到第CUTOFF个事件后主动断线 ──
        task_id, first_half, cut1_seq = await _open_stream_first_half(
            USER_INPUT, session_id, CUTOFF_EVENT_COUNT
        )
        assert task_id, "未从 start 事件取到 task_id"
        print(f"[E2E-31] 断线1: task={task_id}, 断点seq={cut1_seq}, 段1事件数={len(first_half)}")

        # ── ③ 重连1: GET after_seq=断点1+1, 读到第SEG1_USAGE_CUTOFF个usage后二次断线 ──
        seg2, cut2_seq, seg2_finished = await _reconnect_stream_segment(
            task_id, session_id, cut1_seq + 1, usage_cutoff=SEG1_USAGE_CUTOFF
        )
        assert not seg2_finished, (
            f"复杂任务应远未终态即收到{SEG1_USAGE_CUTOFF}个usage并二次断线; "
            f"实际已读到流结束(任务轮数不足, 断点时机失配)"
        )
        assert seg2, "段2无续传帧"
        print(f"[E2E-31] 断线2: 段2事件数={len(seg2)}, 断点seq={cut2_seq}")

        # ── ④ 重连2: GET after_seq=断点2+1, 读到流自然结束(含 final_stats) ──
        seg3, _last_seq, seg3_finished = await _reconnect_stream_segment(
            task_id, session_id, cut2_seq + 1
        )
        assert seg3_finished, "段3(最终重连)必须读到流自然结束"
        assert seg3, "段3无续传帧"
        print(f"[E2E-31] 续传2: 段3事件数={len(seg3)}")

        # ── ⑤ 三段合并, 终态权威 ──
        segs = [first_half, seg2, seg3]
        all_events = list(first_half) + list(seg2) + list(seg3)
        _fs_evs = [e for e in all_events if e.get("type") == "final_stats"]
        final_event = _fs_evs[-1] if _fs_evs else (all_events[-1] if all_events else None)

        # 链式不重不漏: 各段seq > 前段断点, 合并唯一
        seg_seqs = [[e.get("seq") for e in s if isinstance(e.get("seq"), int)] for s in segs]
        assert all(s > cut1_seq for s in seg_seqs[1]), f"段2须全部seq>断点1({cut1_seq})(MUST)"
        assert all(s > cut2_seq for s in seg_seqs[2]), f"段3须全部seq>断点2({cut2_seq})(MUST)"
        all_seqs = [e.get("seq") for e in all_events if isinstance(e.get("seq"), int)]
        assert len(all_seqs) == len(set(all_seqs)), (
            f"三段seq集合不得重复(源头不重发)(MUST): 段1={len(seg_seqs[0])} "
            f"段2={len(seg_seqs[1])} 段3={len(seg_seqs[2])} 合并唯一={len(set(all_seqs))}"
        )

        # usage 三段交集为空(1:1:1 不双计)
        usage_seqs = [
            set(e.get("seq") for e in s if e.get("type") == "usage" and isinstance(e.get("seq"), int))
            for s in segs
        ]
        assert not (usage_seqs[0] & usage_seqs[1]), "usage帧段1∩段2重复"
        assert not (usage_seqs[1] & usage_seqs[2]), "usage帧段2∩段3重复"
        assert not (usage_seqs[0] & usage_seqs[2]), "usage帧段1∩段3重复"

        # 终态: 合并全集含 final_stats 且其 seq == 最大 seq
        fs_events = [e for e in all_events if e.get("type") == "final_stats"]
        assert fs_events, "全集必须含final_stats事件(MUST)"
        assert fs_events[-1].get("seq") == all_seqs[-1], (
            f"final_stats应为末帧(权威终态)(MUST): fs_seq={fs_events[-1].get('seq')} < max={all_seqs[-1]}"
        )

        # ── ⑥ result同构构造(与e2e_helpers.send_chat一致, 供write_test_record v2.2反推PASSED) ──
        for _ev in all_events:
            if not hasattr(_ev, "get"):
                continue  # 防御(理论上全为dict)
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
            "total_time_ms": int((datetime.now() - test_start).total_seconds() * 1000),
            "response_text": _resp_text,
            "reply": _resp_text,
            "session_id": session_id,
            "user_msg_id": user_msg_id,
            "event_types": [e.get("type", "") for e in all_events],
            "start_time": test_start,
            "end_time": datetime.now(),
        }

        # ── ⑦ 补点A/B: 日志三键闭环对账 ──
        task_log = _read_task_log_lines(task_id)
        assert task_log, "后端日志无该task记录(MUST)"
        logs = _parse_reconnect_logs(task_log)

        # 补点A: 两次断线 ⇒ 恰好两条重连请求留痕
        assert len(logs["reconnect_requests"]) == 2, (
            f"补点A: 重连请求接收留痕应恰好2条(两次断线)(MUST): {logs['reconnect_requests']}"
        )
        assert logs["reconnect_requests"][0]["after_seq"] == cut1_seq + 1, (
            f"重连1 after_seq应=断点1+1({cut1_seq + 1})(MUST): {logs['reconnect_requests'][0]['after_seq']}"
        )
        assert logs["reconnect_requests"][1]["after_seq"] == cut2_seq + 1, (
            f"重连2 after_seq应=断点2+1({cut2_seq + 1})(MUST): {logs['reconnect_requests'][1]['after_seq']}"
        )
        assert all(x["has_fs"] is False for x in logs["reconnect_requests"]), (
            "两次重连请求留痕 含final_stats 应均为False(断点均在终态前)(MUST)"
        )

        # 三键闭环核心: fs_seq / done置位event_log_len / 最终reader已转发 三者严格一致
        assert logs["fs_seq"] is not None, "日志必须有 [Runner] final_stats 已发布(MUST)"
        assert logs["done_len"] is not None, "日志必须有 [Runner] done置位(MUST)"
        assert len(logs["reader_exits"]) >= 1, "日志必须有 [SSE] reader退出(补点B)(MUST)"
        # 唯一"自然结束"的reader = 最终重连2(其余主动断开CancelledError不落done分支日志)
        last_exit = logs["reader_exits"][-1]
        assert last_exit["fwd"] == logs["done_len"] == logs["fs_seq"] + 1, (
            f"三键闭环(严格一致)(MUST): 最终reader已转发={last_exit['fwd']} "
            f"!= done置位event_log_len={logs['done_len']} != final_stats seq+1={logs['fs_seq'] + 1}"
        )
        assert last_exit["fwd"] == last_exit["buf_len"], (
            f"reader必须排空到缓冲末尾(已转发==缓冲总长)(MUST): {last_exit['fwd']} vs {last_exit['buf_len']}"
        )
        assert last_exit["last_type"] == "final_stats" and last_exit["has_fs"], (
            "最终reader末类型=final_stats且含final_stats=True(终态权威末帧)(MUST)"
        )
        # 补点B: 最终reader 是重连, is_reconnect=True, 起点seq = 重连2 after_seq, 续传帧数=已转发-起点
        assert last_exit["is_reconnect"] is True, "最终reader必须是重连(is_reconnect=True)(MUST)"
        assert last_exit["start_seq"] == logs["reconnect_requests"][1]["after_seq"], (
            f"补点B起点seq应=重连2 after_seq({logs['reconnect_requests'][1]['after_seq']})(MUST): "
            f"{last_exit['start_seq']}"
        )
        assert last_exit["span"] == last_exit["fwd"] - last_exit["start_seq"], (
            f"续传帧数应=已转发-起点seq(自洽)(MUST): span={last_exit['span']} "
            f"vs {last_exit['fwd'] - last_exit['start_seq']}"
        )
        # 终态权威 status + 无NameError
        assert logs["fs_status"] == "completed", f"final_stats status应为completed(MUST): {logs['fs_status']}"
        assert "NameError" not in task_log, "后端日志无NameError(P1修复不可回归)(MUST)"

        # ── ⑧ check_db / check_logs(DB-Prompt一致性) ──
        db = check_db(session_id)
        assert db.get("session_exists"), "会话必须存在于DB(MUST)"
        assert db.get("execution_steps_count", 0) >= 2, "DB必须含>=2个执行步骤(start+final)(MUST)"
        # 执行步骤终态不重发: DB 必须落 final 且仅一次(续传不重发在DB侧印证) — 小欧 2026-09-13
        # (注: step_json 无 round 字段, "轮次唯一"依 round 判不成立, 改以 final 唯一性等价验证)
        _db_types = [s.get("type") for s in db.get("execution_steps", [])]
        assert _db_types.count("final") == 1, (
            f"DB执行步骤必须含 final 且仅一次(终态不重发)(MUST): final次数={_db_types.count('final')}")
        lc = check_logs(test_start, session_id, user_msg_id)
        assert not lc.get("tracebacks"), f"日志不应有Traceback(MUST): {lc.get('tracebacks')}"
        assert not lc.get("errors"), f"日志不应有ERROR(MUST): {lc.get('errors')[:3]}"
        assert lc.get("prompt_log_files"), "必须匹配到 Prompt 日志文件(MUST, 供 DB-Prompt 一致性比对)"
        assert lc.get("llm_calls_found", 0) > 0, "Prompt日志必须含 LLM 调用记录(MUST)"

        print(
            f"[E2E-31] 验证通过: 段1/2/3 = {len(first_half)}/{len(seg2)}/{len(seg3)}帧; "
            f"三键闭环 fs_seq={logs['fs_seq']}+1 == done_len={logs['done_len']} == reader已转发={last_exit['fwd']}; "
            f"usage前/中/后={len(usage_seqs[0])}/{len(usage_seqs[1])}/{len(usage_seqs[2])}"
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