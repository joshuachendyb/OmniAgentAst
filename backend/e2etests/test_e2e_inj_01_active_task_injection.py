"""全链路E2E集成测试 - INJ-01: 活跃任务注入 - 任务loop中追加消息

操作手册对照:
   用例: E2E-INJ-01 (注入专项, 标识 INJ = Injected, 补 PAR 系列的空白)
   场景: 同一会话内, 第一条任务仍在 ReAct loop 中运行时, 用户追加第二条消息
   预期过程: 第二条命中 has_active_task_in_session → inject_message_to_task,
             立即返回 retrying 应答并结束, 不新开任务、不打断第一条;
             第一条吸收追加内容后正常完成
   通过标准:
     行为层(MUST)
     1. 第二条首事件 type=retrying, content 含"已注入当前执行中的任务"
     2. 第二条无 error 事件(不出现 500/断流)
     3. 第二条未新开任务(无 start 事件)
     4. 日志无 Traceback、无非安全 ERROR
     数据层(MUST, 记录主体=第一条标准会话)
     5. 第一条流有 final 终态、无 error
     6. session 落库完整, 第一条产生 assistant 回复
     7. 两条 user 消息均在库(第二条确认落库未丢)
   失败标准: 未命中注入 / 应答非 retrying / 追加消息丢失 / StreamChunk.encode 类崩溃

   回归由来(2026-09-28 小欧):
     本用例守护 9-20 新增的「活跃任务注入」功能。该功能曾把 LLM 层 StreamChunk
     数据类直接 yield 给 StreamingResponse, starlette 调 chunk.encode() 抛
     AttributeError 致 ASGI 崩溃。因触发条件苛刻(需任务活跃+注入成功),
     常规"发一条等结果"的 E2E 模式碰不到, 缺陷潜伏 8 天未被任何用例发现。

   设计要点(小欧 2026-09-28 修正):
     首版用 start_chat_stream_async 起第一条, 但它只返回原始 events、不提取
     send_chat 的标准 result 字段(final_event/response_text/tool_calls/...),
     记录主体误用注入应答(无 final 零工具) → 记录判定 FAILED。
     改为第一条也走 send_chat(以 asyncio task 后台跑), 拿到完整标准 result,
     记录主体=第一条(标准完整会话), 注入断言仍独立严格。不改 helper、不复刻提取逻辑。
     并发同步不靠盲等: 第二条命中注入本身即证明第一条处于活跃态
     (has_active_task_in_session 命中才走注入分支)。

   铁律:
     1. 一个用例一个脚本, 一次只跑一个 case
     2. 所有验证基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
     3. 测试前必须重启后端服务
     4. 禁止在测试代码中使用emoji字符
     5. finally中必须调用write_test_record
     6. 严禁在脚本内设任何超时 — 统一由pytest --timeout管理

 -- 小欧 2026-09-28
"""

TEST_CASE_ID = "E2E-INJ-01"
TEST_CASE_NAME = "活跃任务注入-loop中追加消息返回retrying应答"

import asyncio
from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, create_session, send_chat, check_db, check_logs,
    print_report, write_test_record, register_pending_record, filter_safety_errors,
)

# 第一条: 要求长输出(实测跑 100s+), 确保第二条发出时它仍在 loop 中
FIRST_INPUT = ("请写一份关于人工智能技术发展的详细报告, 需要覆盖技术原理、"
               "应用场景、未来趋势三个部分, 每个部分都要展开说明, 总字数不少于两千字。")
# 第二条: 追加指令, 应被注入到第一条的 inbox 而非新开任务
SECOND_INPUT = "在报告里再补充一个量子计算的章节。"

ACTIVE_WAIT_SEC = 25   # 等第一条进入 loop 的等待(秒); 命中与否由第二条断言裁定, 非盲等


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_inj_01_active_task_injection():
    """INJ-01: 任务loop中追加消息, 命中注入路径返回 retrying 应答, 追加消息不丢。"""
    test_start = datetime.now()
    passed = False
    error_info = None
    first = None
    second = None
    db = {}
    ci = []
    si = []
    lc = {"errors": [], "tracebacks": []}
    elapsed = 0.0
    session_id = None
    first_task = None

    try:
        register_pending_record(
            TEST_CASE_ID, TEST_CASE_NAME, FIRST_INPUT, {}, {}, [], [],
            {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        session_id = await create_session()
        assert session_id, "建会话失败"

        # ── 第一条后台跑(标准 send_chat, 拿到完整 result) ─────────────
        first_task = asyncio.create_task(send_chat(FIRST_INPUT, session_id=session_id))
        await asyncio.sleep(ACTIVE_WAIT_SEC)
        print(f"[INJ] 第一条已后台运行 {ACTIVE_WAIT_SEC}s, 发第二条试探活跃态")

        # ── 第二条同会话追加: 命中则立即返回 retrying ─────────────────
        second = await send_chat(SECOND_INPUT, session_id=session_id)
        second_elapsed = second["total_time_ms"] / 1000.0
        types = [e.get("type") for e in second["events"]]
        print(f"[INJ] 第二条 type序列={types}, 耗时={second_elapsed:.2f}s")

        events = second["events"]
        assert events, "第二条无任何 SSE 事件(MUST)"
        first_ev = events[0]
        assert first_ev.get("type") == "retrying", (
            f"第二条首事件应为 retrying(注入应答), 实际 {first_ev.get('type')!r} — "
            "若为 start 说明第一条已结束(未命中活跃态), 场景未复现"
        )
        assert "已注入当前执行中的任务" in str(first_ev.get("content", "")), (
            f"注入文案缺失(MUST): {first_ev.get('content')!r}"
        )
        assert not second["has_error"], f"第二条不应有 error(MUST): {second.get('error_events')}"
        assert "start" not in types, f"注入不应新开任务, 事件序列={types}(MUST)"

        # ── 等第一条跑完(吸收追加内容后完成) ───────────────────────
        first = await first_task
        first_task = None
        elapsed = first["total_time_ms"] / 1000.0
        print(f"[INJ] 第一条完成: steps={first['total_steps']}, tools={len(first['tool_calls'])}")

        # ── 数据层: 第一条是标准完整会话 ────────────────────────────
        assert first["final_event"], "第一条必须有 final 终态(MUST)"
        assert not first["has_error"], f"第一条不应有 error(MUST): {first.get('error_events')}"
        assert len(first["response_text"]) > 50, f"第一条回复过短(MUST): {len(first['response_text'])}字"
        assert first["unique_step_numbers"] < 300, f"第一条疑似死循环(MUST): {first['unique_step_numbers']}步"

        db = check_db(session_id)
        assert db["session_exists"], "session必须落库(MUST)"
        assert db["is_valid"], f"session is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "user消息必须落库(MUST)"
        assert db["has_assistant_message"], "必须有assistant回复(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"
        # 两条 user 消息都在库 = 追加消息未丢
        assert db["messages_count"] >= 2, \
            f"两条user消息都应落库(追加消息不丢), 实际 {db['messages_count']} 条(MUST)"

        # ── 日志校验 ────────────────────────────────────────────────
        lc = check_logs(test_start, session_id)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志有Traceback(MUST): {lc['tracebacks'][:1]}"

        print_report(
            TEST_CASE_ID, "活跃任务注入", first, db, lc, ci, si, True, elapsed,
            extra={"注入首事件": first_ev.get("type"),
                   "第二条耗时": f"{second_elapsed:.2f}s",
                   "第二条事件": types},
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        if first_task is not None and not first_task.done():
            first_task.cancel()
        write_test_record(
            TEST_CASE_ID, TEST_CASE_NAME, FIRST_INPUT,
            first or {}, db, ci, si, lc, passed, elapsed, error_info=error_info,
        )
