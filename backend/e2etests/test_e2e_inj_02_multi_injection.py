"""全链路E2E集成测试 - INJ-02: 活跃任务注入 - loop 中间隔插入两条新消息

操作手册对照:
   用例: E2E-INJ-02 (注入专项, 设计文档[76] 6.15 场景2 多条注入)
   场景: 同一会话内, 第一条任务仍在 ReAct loop 中运行时, 用户**间隔**插入两条新消息
   预期过程: 第二、三条各自命中 has_active_task_in_session → inject_message_to_task,
             各自立即返回 merged 应答并结束, 都不新开任务、都不打断第一条;
             第一条把两条追加内容吸收入上下文后正常完成
   通过标准:
     行为层(MUST)
     1. 第二条与第三条首事件均为 type=merged, content 含"已并入当前执行中的任务"
     2. 两条的 merged_into_task_id **均等于第一条的真实 task_id**(非空即过是弱断言, 不可)
     3. 两条均无 error 事件, 均未新开任务(无 start 事件)
     数据层(MUST, 记录主体=第一条标准会话)
     4. 恰好 3 条 user 消息(首条+注入2条); 多一条即重复落库(B-1 根因), 少一条即丢消息
     5. 两条注入行 task_id **均等于**第一条 task_id —— 锁 bind_message_to_task 执行期绑定
     6. 锚不被覆盖(设计[76] 6.15 场景2③): 答案落在**最后一条注入行**, 首条行无 response
     日志层(MUST)
     7. 日志无 Traceback、无非安全 ERROR
   失败标准: 任一条未命中注入 / 应答非 merged / 指向错误任务 / 重复落库 / 追加消息丢失
             / 锚被首条覆盖 / StreamChunk.encode 类崩溃

   设计要点(小欧 2026-09-29):
     沿用 INJ-01 的结构与取舍, 不重造:
       ① 记录主体=第一条(标准 send_chat 拿完整 result), 注入断言独立严格;
       ② 第二/第三条命中注入本身即证明第一条活跃, 不靠盲等;
       ③ 任务id 从第一条 events 的 start 事件取 —— send_chat 返回 dict **无 task_id 键**;
       ④ 锚语义(2026-09-28 10轮会审 D-02 实证): 锚取本次 drain 的最后一条 uid, 终态
          update_user_message_final 只 UPDATE 锚所在那一行 → 有注入时**首条行 task_id 恒 NULL**。
          故只断言"注入行已绑 + 最后一条注入行持有答案", **禁止**断言"首条行也有 task_id"
          (INJ-01 实测首条 task_id=None, 那样写会假红)。
     本用例与 INJ-01 的分工: INJ-01 钉单条注入的 SSE 契约(merged 必须是字符串, 防 starlette
     chunk.encode() 崩溃); 本用例钉多条注入的归属一致性(同任务、恰好 N 行、锚不漂)。
     间隔取 20s: 既让两次插入落在不同的 drain 周期(覆盖"两条各自成轮"), 又确保第一条未跑完
     (实测长报告 100s+)。**不假设两条一定合并成同一轮** —— 合并与否取决于两条是否被同一次
     _absorb_inbox 取走, 属时序, 断言只锁确定性的部分。

   铁律:
     1. 一个用例一个脚本, 一次只跑一个 case
     2. 所有验证基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
     3. 测试前必须重启后端服务
     4. 禁止在测试代码中使用emoji字符
     5. finally中必须调用write_test_record
     6. 严禁在脚本内设任何超时 — 统一由pytest --timeout管理

 -- 小欧 2026-09-29
"""

TEST_CASE_ID = "E2E-INJ-02"
TEST_CASE_NAME = "活跃任务注入-loop中间隔插入两条消息同任务合并且锚不漂"

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
    "【INJ-02 多条注入验证】请完成一个多步骤的研究与写作任务, 每一步都要真实执行, 不要跳过:\n"
    "1. 深度检索最近5年人工智能领域的重要技术发现与技术进展;\n"
    "2. 对比分析 agent(智能体) 技术最近5年的发展演进, 说明与上一代技术的差异;\n"
    "3. 基于以上检索与分析, 写出一份人工智能的详细报告, 覆盖技术原理, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "4. 再写一份 agent 领域的报告, 覆盖应用场景、未来趋势三个部分, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "5. 最后详细说明 agent 未来趋势的应用领域分别是什么, 每一个部分都要详细展开。"
)
# 第二条: 追加指令一
SECOND_INPUT = "在报告里再补充一个量子计算的章节。"
# 第三条: 追加指令二(与第二条间隔 INTERVAL_SEC 发出)
THIRD_INPUT = "另外请增加一章讨论人工智能在医疗领域的应用。"

FIRST_WAIT_SEC = 25   # 等第一条进入 loop 的等待(秒); 命中与否由断言裁定, 非盲等
INTERVAL_SEC = 20     # 两条注入之间的间隔(秒)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_inj_02_multi_injection():
    """INJ-02: 任务loop中间隔插入两条消息, 均命中注入、归同一任务、锚不漂。"""
    test_start = datetime.now()
    passed = False
    error_info = None
    first = None
    second = None
    third = None
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

        # ── 第一条后台跑(标准 send_chat, 拿完整 result) ─────────────
        first_task = asyncio.create_task(send_chat(FIRST_INPUT, session_id=session_id))
        await asyncio.sleep(FIRST_WAIT_SEC)
        print(f"[INJ2] 第一条已后台运行 {FIRST_WAIT_SEC}s, 发第二条")

        # ── 第二条: 间隔插入的第一条 ──────────────────────────────
        second = await send_chat(SECOND_INPUT, session_id=session_id)
        second_types = [e.get("type") for e in second["events"]]
        print(f"[INJ2] 第二条 type序列={second_types}, 耗时={second['total_time_ms']/1000.0:.2f}s")

        assert second["events"], "第二条无任何 SSE 事件(MUST)"
        _ev2 = second["events"][0]
        assert _ev2.get("type") == "merged", (
            f"第二条首事件应为 merged(注入应答), 实际 {_ev2.get('type')!r} — "
            "若为 start 说明第一条已结束(未命中活跃态), 场景未复现"
        )
        assert "已并入当前执行中的任务" in str(_ev2.get("content", "")), \
            f"第二条注入文案缺失(MUST): {_ev2.get('content')!r}"
        _tid2 = _ev2.get("merged_into_task_id")
        assert _tid2, f"第二条 merged 缺 merged_into_task_id(MUST): {_ev2!r}"
        assert not second["has_error"], f"第二条不应有 error(MUST): {second.get('error_events')}"
        assert "start" not in second_types, f"第二条注入不应新开任务, 事件序列={second_types}(MUST)"

        # ── 间隔 INTERVAL_SEC 后发第三条 ──────────────────────────
        await asyncio.sleep(INTERVAL_SEC)
        print(f"[INJ2] 间隔 {INTERVAL_SEC}s 后发第三条")
        third = await send_chat(THIRD_INPUT, session_id=session_id)
        third_types = [e.get("type") for e in third["events"]]
        print(f"[INJ2] 第三条 type序列={third_types}, 耗时={third['total_time_ms']/1000.0:.2f}s")

        assert third["events"], "第三条无任何 SSE 事件(MUST)"
        _ev3 = third["events"][0]
        assert _ev3.get("type") == "merged", (
            f"第三条首事件应为 merged(注入应答), 实际 {_ev3.get('type')!r} — "
            "若为 start 说明第一条已结束(未命中活跃态), 场景未复现"
        )
        assert "已并入当前执行中的任务" in str(_ev3.get("content", "")), \
            f"第三条注入文案缺失(MUST): {_ev3.get('content')!r}"
        _tid3 = _ev3.get("merged_into_task_id")
        assert _tid3, f"第三条 merged 缺 merged_into_task_id(MUST): {_ev3!r}"
        assert not third["has_error"], f"第三条不应有 error(MUST): {third.get('error_events')}"
        assert "start" not in third_types, f"第三条注入不应新开任务, 事件序列={third_types}(MUST)"

        # ── 等第一条跑完(吸收两条追加内容后完成) ──────────────────
        first = await first_task
        first_task = None
        elapsed = first["total_time_ms"] / 1000.0
        print(f"[INJ2] 第一条完成: steps={first['total_steps']}, tools={len(first['tool_calls'])}")

        # ── 加强断言①: 两条 merged 都必须指向第一条的真实 task_id ──
        _first_tid = next((e.get("task_id") for e in first["events"]
                           if e.get("type") == "start" and e.get("task_id")), None)
        assert _first_tid, (
            "第一条 events 里应能从 start 事件取到 task_id, 实际类型="
            f"{[e.get('type') for e in first['events']][:8]}")
        assert _tid2 == _first_tid, (
            f"第二条 merged_into_task_id 应等于 {_first_tid}, 实际 {_tid2!r}")
        assert _tid3 == _first_tid, (
            f"第三条 merged_into_task_id 应等于 {_first_tid}, 实际 {_tid3!r}")

        # ── 第一条自身健康度 ─────────────────────────────────────
        assert first["final_event"], "第一条必须有 final 终态(MUST)"
        assert not first["has_error"], f"第一条不应有 error(MUST): {first.get('error_events')}"
        assert len(first["response_text"]) > 50, \
            f"第一条回复过短(MUST): {len(first['response_text'])}字"
        assert first["unique_step_numbers"] < 300, \
            f"第一条疑似死循环(MUST): {first['unique_step_numbers']}步"

        # ── 数据层聚合校验 ───────────────────────────────────────
        db = check_db(session_id)
        assert db["session_exists"], "session必须落库(MUST)"
        assert db["is_valid"], f"session is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "user消息必须落库(MUST)"
        assert db["has_assistant_message"], "必须有assistant回复(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"
        # 恰好 3 条(首条+注入2条): == 而非 >=, 多一条即重复落库(B-1 根因), 少一条即丢消息
        assert db["messages_count"] == 3, \
            f"应恰好 3 条 user 消息(首条+两条注入), 实际 {db['messages_count']} 条(MUST)"

        # ── 加强断言②: 两条注入行 task_id 均等于目标任务(锁 bind_message_to_task) ──
        #   注意: **不**断言首条行也有 task_id —— 有注入时锚在最后一条注入行, 首条行 task_id 恒 NULL
        #   (update_user_message_final 只 UPDATE 锚所在那一行; INJ-01 实测首条 task_id=None)
        _rows = get_user_message_rows(session_id)
        assert len(_rows) == 3, f"行级读取应得 3 行, 实际 {len(_rows)} 行(与 messages_count 不一致)"
        _by_id = {r.get("id"): r for r in _rows}
        _row_first = _by_id.get(first["user_msg_id"])
        _row_2 = _by_id.get(second["user_msg_id"])
        _row_3 = _by_id.get(third["user_msg_id"])
        assert _row_first is not None, f"找不到首条消息行(id={first['user_msg_id']})"
        assert _row_2 is not None, f"找不到第二条注入行(id={second['user_msg_id']})"
        assert _row_3 is not None, f"找不到第三条注入行(id={third['user_msg_id']})"
        assert _row_2.get("task_id") == _first_tid, \
            f"第二条注入行应绑定 {_first_tid}, 实际 {_row_2.get('task_id')!r}"
        assert _row_3.get("task_id") == _first_tid, \
            f"第三条注入行应绑定 {_first_tid}, 实际 {_row_3.get('task_id')!r}"

        # ── 加强断言③: 锚不被覆盖(设计[76] 6.15 场景2③) ──────────
        #   锚取本次 drain 的最后一条 uid → 答案落在最后一条注入行; 首条行不应持有 response。
        #   若首条被当锚回填, 说明锚漂到了旧首轮消息, 本用例即红。
        _resp_2 = str(_row_2.get("response") or "")
        _resp_3 = str(_row_3.get("response") or "")
        assert not str(_row_first.get("response") or ""), (
            "首条行不应持有 response —— 答案应落在最后一条注入行(锚取最后一条 uid), "
            "首条持有即锚漂到旧首轮消息")
        assert _resp_3, "最后一条注入行应持有 assistant 答案(锚取最后一条 uid)"

        # ── LLM 是否真吸收两条追加内容: 只作证据记录, 不硬断言 ──
        #   依赖 LLM 是否照做, 非机制本身, 硬断言会 flaky(设计[76] 决策: 机制测机制)
        _evid = {
            "含量子计算(第二条)": "量子计算" in _resp_3,
            "含医疗(第三条)": "医疗" in _resp_3,
            "答案字数": len(_resp_3),
        }
        print(f"[INJ2] LLM吸收证据: {_evid}")

        # ── 日志校验 ───────────────────────────────────────────────
        lc = check_logs(test_start, session_id)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志有Traceback(MUST): {lc['tracebacks'][:1]}"

        print_report(
            TEST_CASE_ID, "活跃任务注入-多条", first, db, lc, ci, si, True, elapsed,
            extra={"注入首事件(第二/第三)": f"{_ev2.get('type')}/{_ev3.get('type')}",
                   "目标任务": _first_tid,
                   "第二条耗时": f"{second['total_time_ms']/1000.0:.2f}s",
                   "第三条耗时": f"{third['total_time_ms']/1000.0:.2f}s",
                   "user消息行数": db["messages_count"],
                   "LLM吸收证据": _evid},
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
