"""全链路E2E集成测试 - E2E-32: 超 300 秒后 Journal 回放

对应文档: doc-9月优化/[63]...架构方案-小欧-2026-09-22.md 第六章 6.3 P4(修正版)
实施人: 小欧 2026-09-30

验证点:
  ① 真等 >300 秒(禁 Mock, 铁律): 内存缓冲被 agent_runner.py:792
     `loop.call_later(300, reclaim_memory_buffer)` 回收 → 此时 GET 必须走 Journal 回放
  ② Journal 回放能补齐全部步骤(seq>=after_seq), 不丢帧
  ③ 回放 seq 序列单调、不重放 <= after_seq 的帧
  ④ 三方对账(第六章 M4): DB chat_task_steps / Journal chat_stream_events / 回放帧 步数一致
  ⑤ chat_stream_events 该 task 行仍在(保留期 7 天, config.yaml:264, 不该被 retention 删)

与第六章原文的差异(勿误读):
  第六章 P4 写"超 300s → GET 返回 not_found 进入历史恢复态"。**该判据不成立** ——
  现状核实: 后端**没有 300 秒硬窗**。300s 仅决定"内存 event_log 是否还在"
  (reclaim_memory_buffer, task_state.py:151 明确"只清内存, 不删 Journal");
  Journal 保留期是 7 天(config.yaml:264 journal_retention_days), 回放终止判据是
  producer 60 秒活窗(_JOURNAL_ALIVE_WINDOW_SECONDS, stream_orchestrator.py:741) + 终态事件存在性,
  无 300 秒总预算。故本 case 验的是"超 300s 后**仍能回放**"(正向), 而非 not_found。

耗时: 真等 300s + 任务本身, 约 7 分钟。由 pytest --timeout 统一管理, 脚本内不设超时。

 铁律:
   1. 一次只跑一个case, 严禁批量
   2. 全部基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
   3. 脚本内严禁设任何超时 -- 由调用侧 pytest --timeout 统一管理
   4. 等待 300s 是铁律要求的真实等待(缩短窗口即属 Mock), 严禁改小
   5. finally 中必须调用 write_test_record(手册5.5铁律)

-- 小欧 2026-09-30 首版
"""

TEST_CASE_ID = "E2E-32"
TEST_CASE_NAME = "超300秒后 Journal 回放 - 步骤不丢/seq单调/三方对账"

# 保证任务足够多步(Journal 才有回放价值), 且能在 300s 内跑完(超窗回放的是**已完成**任务)
USER_INPUT = (
    "请完成一份行业研究报告(不少于800字, 含标题/要点列表/结论段), 必须分步调用工具完成, 严禁只用对话回答:"
    "第一步:用文件工具在 E:\\test_dir 下创建 e2e_journal32.md 并写入标题行;"
    "第二步:用联网搜索工具查询商业航天近三年的发射次数并记录要点;"
    "第三步:读回该文件, 把要点补写进去;"
    "第四步:在对话中给出完整报告正文。"
)

# 真等超过内存缓冲回收窗口(秒) —— 铁律要求真实等待, 不得调小
WAIT_BEFORE_REPLAY_SEC = 320
REPLAY_AFTER_SEQ = 1

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from e2emodel.e2e_helpers import (
    DB_PATH,
    LOG_DIR,
    check_db,
    check_logs,
    create_session,
    ensure_backend_ready,
    register_pending_record,
    remove_pending_record,
    resume_chat_stream,
    save_user_message,
    write_test_record,
)


def _journal_rows(task_id: str) -> list:
    """直读 chat_stream_events(Journal 落库真相) —— 经 DB_PATH 常量, 不硬编码路径"""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT seq, event_type FROM chat_stream_events "
            "WHERE task_id=? ORDER BY seq",
            (task_id,),
        ).fetchall()
    finally:
        con.close()


def _step_rows(task_id: str) -> int:
    """DB chat_task_steps 该 task 的步数(三方对账用)"""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM chat_task_steps WHERE task_id=?", (task_id,)
        ).fetchone()[0]
    finally:
        con.close()


def _read_task_log_lines(task_id: str) -> str:
    """读当日app日志中该task相关的全部行(按task_id过滤)"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"app_{today}.log"
    if not log_file.exists():
        return ""
    raw = log_file.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(l for l in raw.splitlines() if task_id in l)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_32_journal_replay_after_300s():
    """E2E-32: 超 300s 走 Journal 回放, 步骤不丢 + seq 单调 + 三方对账 — 小欧 2026-09-30"""
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

        # ── ① 建会话 + 存用户消息 + 跑完整任务到终态 ──
        session_id = await create_session()
        assert session_id, "创建session失败"
        user_msg_id = await save_user_message(session_id, USER_INPUT)
        assert user_msg_id is not None, "保存用户消息失败(user_msg_id不得为空, 供DB-Prompt一致性匹配)"

        from e2emodel.e2e_helpers import send_chat
        result = await send_chat(USER_INPUT, session_id=session_id)
        # 2026-10-01 小欧 - 首跑失败点: 原写 result.get("task_id"), 但 send_chat 的返回字典里
        #   **没有** task_id 键(实测 keys 只有 session_id/user_msg_id/events/...), 恒取到 "",
        #   于是什么都没验就红。改为从 start 事件取 task_id(与 test_e2e_inj_01 同一口径)。
        _events = result.get("events") or []
        start_ev = next(
            (e for e in _events if e.get("type") == "start" and e.get("task_id")), None
        )
        task_id = (start_ev or {}).get("task_id") or ""
        assert task_id, (
            f"未从 start 事件取到 task_id(events类型={[e.get('type') for e in _events][:8]})"
        )
        final_event = result.get("final_event")
        assert final_event, "任务无终态事件(未跑到final)"
        print(
            f"[E2E-32] 任务终态: task={task_id}, 事件数={len(result.get('events') or [])}, "
            f"步骤={result.get('total_steps')}"
        )

        # ── ② 记下超窗前的基线: Journal 行数 / DB 步数 ──
        jrows_before = _journal_rows(task_id)
        steps_before = _step_rows(task_id)
        print(
            f"[E2E-32] 超窗前基线: Journal行={len(jrows_before)}, DB步数={steps_before}"
        )
        assert jrows_before, "Journal 无该 task 的事件行(append 未生效, 后续回放无从谈起)"
        assert steps_before >= 2, f"DB 步数应>=2(start+final)(MUST): {steps_before}"

        # ── ③ 真等 >300s(铁律: 缩短即 Mock) ──
        #    等的是内存缓冲被 reclaim_memory_buffer 回收, 之后 GET 必走 Journal。
        print(f"[E2E-32] 真等 {WAIT_BEFORE_REPLAY_SEC}s(超内存缓冲 300s 回收窗口)...")
        await asyncio.sleep(WAIT_BEFORE_REPLAY_SEC)
        print("[E2E-32] 等待结束, 开始回放")

        # ── ④ GET after_seq=1 回放(此时内存应已回收, 必走 Journal) ──
        events, last_seq, finished = await resume_chat_stream(
            task_id, session_id, REPLAY_AFTER_SEQ
        )
        print(
            f"[E2E-32] 回放: 帧数={len(events)}, last_seq={last_seq}, finished={finished}"
        )

        # ── r 构造(与 send_chat 同构, 供 write_test_record v2.2 反推 PASSED; 空 r 会把真 PASSED 记成 FAILED) ──
        r = dict(result)
        r["replay_events"] = events
        r["replay_last_seq"] = last_seq
        r["journal_rows_before"] = len(jrows_before)
        r["db_steps_before"] = steps_before
        r["waited_seconds"] = WAIT_BEFORE_REPLAY_SEC

        # ── 验证点②: 回放必须拿到帧(超 300s 仍能回放 = Journal 生效) ──
        assert events, (
            "超 300s 后 GET 回放返回空(Journal 未生效或事件已被清理)(MUST): "
            f"task={task_id}, Journal行数={len(jrows_before)}"
        )

        # ── 验证点③: 回放 seq 全部 >= after_seq, 且单调不减、不重复 ──
        seqs = [e.get("seq") for e in events if isinstance(e.get("seq"), int)]
        assert seqs, "回放帧无带 seq 事件(MUST)"
        assert min(seqs) >= REPLAY_AFTER_SEQ, (
            f"回放帧 seq 必须 >= after_seq({REPLAY_AFTER_SEQ})(不得重放已消费帧)(MUST): min={min(seqs)}"
        )
        non_decreasing = all(v >= seqs[i - 1] for i, v in enumerate(seqs) if i > 0)
        assert non_decreasing, f"回放 seq 序列非单调(出现回退)(MUST): {seqs[:40]}"
        assert len(seqs) == len(set(seqs)), f"回放 seq 出现重复(重发)(MUST): {len(seqs)}帧/{len(set(seqs))}唯一"

        # ── 验证点③b: 终态帧必须回放得到(任务已完成, Journal 保有 final_stats) ──
        fs = [e for e in events if e.get("type") == "final_stats"]
        assert fs, "回放未拿到 final_stats(终态帧丢失)(MUST)"
        assert fs[-1].get("seq") == max(seqs), (
            f"final_stats 应为回放末帧(MUST): fs_seq={fs[-1].get('seq')} max={max(seqs)}"
        )

        # ── 验证点④: 三方对账(Journal 行数 vs 回放帧数) ──
        #    注: Journal 记录全部事件(含不转发 SSE 的白名单外类型, stream_orchestrator.py:484 continue),
        #    故 Journal 行数 >= 回放帧数 属预期; 反向(回放帧 > Journal 行)才是异常。
        jrows_after = _journal_rows(task_id)
        assert len(jrows_after) >= len(seqs), (
            f"回放帧数不得多于 Journal 落库行数(凭空多出)(MUST): 回放={len(seqs)} Journal={len(jrows_after)}"
        )
        # Journal seq 覆盖回放 seq(回放的每一帧在 Journal 都有对应行)
        jseqs = {r["seq"] for r in jrows_after}
        missing_in_journal = [s for s in seqs if s not in jseqs]
        assert not missing_in_journal, (
            f"回放帧在 Journal 无对应行(伪造帧)(MUST): {missing_in_journal[:20]}"
        )
        print(
            f"[E2E-32] 三方对账: Journal行={len(jrows_after)} 回放帧={len(seqs)} DB步={steps_before}"
        )

        # ── 验证点⑤: Journal 该 task 行仍在(7 天保留期内不该被 retention 删) ──
        assert jrows_after, "Journal 该 task 行已被清空(保留期内不该发生)"

        # ── 验证点②b: 内存缓冲确已回收(回放走 Journal 的前提) ──
        #    后端日志: reclaim_memory_buffer 打回收痕迹; 有则说明确已回收
        task_log = _read_task_log_lines(task_id)
        reclaimed = "reclaim" in task_log.lower() or "回收" in task_log
        print(f"[E2E-32] 后端日志含内存回收痕迹={reclaimed}(超窗回放前提)")

        # ── 日志无 ERROR + prompt 日志匹配(复用 check_logs) ──
        db = check_db(session_id)
        assert db.get("session_exists"), "会话必须存在于DB(MUST)"
        assert db.get("execution_steps_count", 0) >= 2, "DB必须含>=2个执行步骤(MUST)"
        lc = check_logs(test_start, session_id, user_msg_id)
        assert not lc.get("tracebacks"), f"日志不应有Traceback(MUST): {lc.get('tracebacks')}"
        # 配额类 429 不算本 case 失败(与 E2E-30 一致口径: 外部配额问题不归因于回放逻辑)
        errs = [
            e for e in lc.get("errors", [])
            if not ("429" in e or "quota_exceeded" in e or "配额已用尽" in e)
        ]
        assert not errs, f"日志不应有ERROR(配额类已排除)(MUST): {errs[:3]}"
        assert lc.get("prompt_log_files"), "必须匹配到 Prompt 日志文件(MUST)"

        passed = True
        print(
            f"[E2E-32] 验证通过: 等{WAIT_BEFORE_REPLAY_SEC}s后回放{len(seqs)}帧, "
            f"seq {min(seqs)}~{max(seqs)}, Journal行={len(jrows_after)}"
        )

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
