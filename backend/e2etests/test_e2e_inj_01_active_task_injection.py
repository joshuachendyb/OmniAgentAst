"""全链路E2E集成测试 - INJ-01: 活跃任务注入 - 任务loop中追加消息

操作手册对照:
   用例: E2E-INJ-01 (注入专项, 标识 INJ = Injected, 补 PAR 系列的空白)
   场景: 同一会话内, 第一条任务仍在 ReAct loop 中运行时, 用户追加第二条消息
   预期过程: 第二条命中 has_active_task_in_session → inject_message_to_task,
             立即返回 merged 应答并结束, 不新开任务、不打断第一条;
             第一条吸收追加内容后正常完成
   通过标准:
     行为层(MUST)
     1. 第二条首事件 type=merged, content 含"已并入当前执行中的任务", 且携带 merged_into_task_id
     2. 第二条无 error 事件(不出现 500/断流)
     3. 第二条未新开任务(无 start 事件)
     4. 日志无 Traceback、无非安全 ERROR
     数据层(MUST, 记录主体=第一条标准会话)
     5. 第一条流有 final 终态、无 error
     6. session 落库完整, 第一条产生 assistant 回复
     7. 两条 user 消息均在库(第二条确认落库未丢)
   失败标准: 未命中注入 / 应答非 merged / 追加消息丢失 / StreamChunk.encode 类崩溃

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
TEST_CASE_NAME = "活跃任务注入-loop中追加消息返回merged应答"

import asyncio
from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, create_session, send_chat, check_db, check_logs,
    print_report, write_test_record, register_pending_record, filter_safety_errors,
    get_user_message_rows,   # 2026-09-29 小欧: 行级 task_id 读取(验 bind_message_to_task 效果)
)

# 第一条: 多步骤任务(北京老陈 2026-09-29 定) —— 必须多步才能撑起 loop 注入窗口。
#   要求真实检索 + 对比分析 + 三段长文写作 → 强制多轮 LLM 调用与工具调用, 活期显著长于单轮问答。
#   旧写法"写一份两千字报告"可能被一个 LLM 轮直接答完(无工具、无多步), 注入窗口不可靠。
FIRST_INPUT = (
    "【INJ-01 单条注入验证】请完成一个多步骤的研究与写作任务, 每一步都要真实执行, 不要跳过:\n"
    "1. 深度检索最近5年人工智能领域的重要技术发现与技术进展;\n"
    "2. 对比分析 agent(智能体) 技术最近5年的发展演进, 说明与上一代技术的差异;\n"
    "3. 基于以上检索与分析, 写出一份人工智能的详细报告, 覆盖技术原理, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "4. 再写一份 agent 领域的报告, 覆盖应用场景、未来趋势三个部分, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "5. 最后详细说明 agent 未来趋势的应用领域分别是什么, 每一个部分都要详细展开。"
)
# 第二条: 追加指令, 应被注入到第一条的 inbox 而非新开任务
SECOND_INPUT = "在报告里再补充一个量子计算的章节。"

ACTIVE_WAIT_SEC = 25   # 等第一条进入 loop 的等待(秒); 命中与否由第二条断言裁定, 非盲等


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_inj_01_active_task_injection():
    """INJ-01: 任务loop中追加消息, 命中注入路径返回 merged 应答, 追加消息不丢。"""
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

        # ── 第二条同会话追加: 命中则立即返回 merged ─────────────────
        second = await send_chat(SECOND_INPUT, session_id=session_id)
        second_elapsed = second["total_time_ms"] / 1000.0
        types = [e.get("type") for e in second["events"]]
        print(f"[INJ] 第二条 type序列={types}, 耗时={second_elapsed:.2f}s")

        events = second["events"]
        assert events, "第二条无任何 SSE 事件(MUST)"
        first_ev = events[0]
        # 2026-09-28 21:29 小欧 10轮会审 D-05: type retrying→merged + 文案"已注入"→"已并入"
        #   (设计[76] 5.4/6.6: retrying 属重试语义误用)。原断言锁的是被取代的契约, 必然失败
        #   → 测试过时, 随系统更新(不反过来改系统迎合测试)。
        assert first_ev.get("type") == "merged", (
            f"第二条首事件应为 merged(注入应答), 实际 {first_ev.get('type')!r} — "
            "若为 start 说明第一条已结束(未命中活跃态), 场景未复现"
        )
        assert "已并入当前执行中的任务" in str(first_ev.get("content", "")), (
            f"注入文案缺失(MUST): {first_ev.get('content')!r}"
        )
        # 设计[76] 6.6②: merged 须携带被并入的任务id, 供前端提示条 + 高亮左侧目标任务
        # 2026-09-29 小欧: 这里只判非空(快速失败); **取值比对**放到下面 await first_task 之后 ——
        #   send_chat 不返回 task_id(返回 dict 无该键), 第一条 task_id 只能从其 events 的 start 事件取,
        #   而 first 要等第一条跑完才可用。
        _merged_into_tid = first_ev.get("merged_into_task_id")
        assert _merged_into_tid, (
            f"merged 事件缺 merged_into_task_id(前端无法定位目标任务, MUST): {first_ev!r}"
        )
        assert not second["has_error"], f"第二条不应有 error(MUST): {second.get('error_events')}"
        assert "start" not in types, f"注入不应新开任务, 事件序列={types}(MUST)"

        # ── 等第一条跑完(吸收追加内容后完成) ───────────────────────
        first = await first_task
        first_task = None
        elapsed = first["total_time_ms"] / 1000.0
        print(f"[INJ] 第一条完成: steps={first['total_steps']}, tools={len(first['tool_calls'])}")

        # ── 2026-09-29 小欧 加强断言①: merged_into_task_id 必须指向第一条的真实 task_id ──
        #   原断言只判非空 → 返回任意非空串也能过, 而该字段唯一用途就是前端高亮目标任务。
        #   注意: send_chat 的返回 dict **无 task_id 键**, 第一条 task_id 从其 events 的 start 事件取
        #   (后端 start_content_step.py:36 的 to_dict 带 task_id)。
        _first_tid = next((e.get("task_id") for e in first["events"]
                           if e.get("type") == "start" and e.get("task_id")), None)
        assert _first_tid, f"第一条 events 里应能从 start 事件取到 task_id, 实际 events 类型={[e.get('type') for e in first['events']][:8]}"
        assert _merged_into_tid == _first_tid, (
            f"merged_into_task_id 应等于被注入的任务id({_first_tid}), 实际 {_merged_into_tid!r} "
            "(前端据此高亮左侧目标任务, 指向错任务则高亮到别的任务上)")

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
        # 2026-09-29 小欧 加强断言②: 用 == 2 而非 >= 2 —— 被修复的 B-1 根因就是"重复落库"
        #   (API 入口落一行 + agent 侧再落一行 → chat_user_message 出现第 3 行副本),
        #   >= 2 会放行 3 行 = 缺陷复发也测不出。设计[76] 5.7 场景1 同理要求"恰好 1 条(== 而非 >=)"。
        assert db["messages_count"] == 2, \
            f"应恰好 2 条 user 消息(首条+注入条, 多一条即重复落库), 实际 {db['messages_count']} 条(MUST)"

        # ── 2026-09-29 小欧 加强断言③: 注入消息已绑定到目标任务(锁 bind_message_to_task) ──
        #   本轮核心修复: 注入执行期即 UPDATE task_id, 否则执行期/刷新后 list_session_tasks 的
        #   merged_inputs 与 fetch 精确 JOIN 都查不到这条消息。
        #   ⚠ 只校验**注入那条**: 第一条的 task_id 终态才回填, 且有注入时锚在注入行
        #   (update_user_message_final 只 UPDATE 锚所在那一行), 故第一条行的 task_id 允许为 NULL,
        #   断言"两行都有 task_id"会引入错误断言。
        _rows = get_user_message_rows(session_id)
        assert len(_rows) == 2, f"行级读取应得 2 行, 实际 {len(_rows)} 行(与 messages_count 不一致)"
        _inj_row = next((r for r in _rows if r.get("id") == second["user_msg_id"]), None)
        assert _inj_row is not None, (
            f"找不到注入消息行(id={second['user_msg_id']}), 实际行 id={[r.get('id') for r in _rows]}")
        assert _inj_row.get("task_id") == _first_tid, (
            f"注入消息应绑定到目标任务 {_first_tid}, 实际 task_id={_inj_row.get('task_id')!r} "
            "(未绑定则执行期查不到、刷新后丢失归属)")

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
