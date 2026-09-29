"""全链路E2E集成测试 - INJ-03: 活跃任务注入 - loop 中间隔插入三条新消息

操作手册对照:
   用例: E2E-INJ-03 (注入专项, 设计文档[76] 6.15 场景2 多条注入的 N=3 扩展)
   场景: 同一会话内, 第一条任务仍在 ReAct loop 中运行时, 用户**间隔**插入三条新消息
   预期过程: 第二/三/四条各自命中 has_active_task_in_session → inject_message_to_task,
             各自立即返回 merged 应答并结束, 都不新开任务、都不打断第一条;
             第一条把三条追加内容吸收入上下文后正常完成
   通过标准:
     行为层(MUST)
     1. 第二/三/四条首事件均为 type=merged, content 含"已并入当前执行中的任务"
     2. 三条的 merged_into_task_id **均等于**第一条的真实 task_id(仅判非空是弱断言, 不可)
     3. 三条均无 error 事件, 均未新开任务(无 start 事件)
     数据层(MUST, 记录主体=第一条标准会话)
     4. 恰好 4 条 user 消息(首条+注入3条); 多一条即重复落库(B-1 根因), 少一条即丢消息
     5. 三条注入行 task_id **均等于**第一条 task_id —— 锁 bind_message_to_task 执行期绑定
     6. 锚不被覆盖: 答案落在**最后一条注入行**, 首条行无 response
     日志层(MUST)
     7. 日志无 Traceback、无非安全 ERROR
   失败标准: 任一条未命中注入 / 应答非 merged / 指向错误任务 / 重复落库 / 追加消息丢失
             / 锚被首条覆盖 / StreamChunk.encode 类崩溃

   设计要点(小欧 2026-09-29):
     沿用 INJ-02 结构, 不重造。三点差异:
       ① 主消息加 【INJ-03 三条注入验证】 前缀 —— INJ-01/02 去掉前缀后在界面无法区分,
          曾因此把 INJ-01 的会话误当 INJ-02 排查(北京老陈 2026-09-29);
       ② 同一段注入断言复用 3 次 → 全部收口 e2emodel.e2e_helpers 共享函数(assert_injection_ack 等),
          case 只留"发消息+编排"(北京老陈 2026-09-29 裁定: 能放共享 helper 的都剥离到 helper);
       ③ 三条注入的 task_id 归属与锚校验用循环, 不逐条手写。
     沿用的关键前提(勿改):
       - 记录主体=第一条(标准 send_chat 拿完整 result), 注入断言独立严格;
       - 命中注入本身即证明第一条活跃, 不靠盲等;
       - 任务id 从第一条 events 的 start 事件取 —— send_chat 返回 dict **无 task_id 键**;
       - 锚取本次 drain 最后一条 uid, 终态只 UPDATE 锚那一行 → 有注入时**首条行 task_id 恒 NULL**,
         故只断言"注入行已绑 + 最后一条注入行持有答案", **禁止**断言"首条行也有 task_id"(会假红)。
     **不假设**三条一定合并成同一轮 LLM 输入: 合并与否取决于是否被同一次 _absorb_inbox 取走, 属时序,
     断言只锁确定性部分(归属一致 / 恰好 N 行 / 锚不漂), LLM 是否照做只作证据记录(避免 flaky)。

   铁律:
     1. 一个用例一个脚本, 一次只跑一个 case
     2. 所有验证基于真实后端+真实LLM+真实工具+真实SQLite, 禁止Mock
     3. 测试前必须重启后端服务
     4. 禁止在测试代码中使用emoji字符
     5. finally中必须调用write_test_record
     6. 严禁在脚本内设任何超时 — 统一由pytest --timeout管理

 -- 小欧 2026-09-29
"""

TEST_CASE_ID = "E2E-INJ-03"
TEST_CASE_NAME = "活跃任务注入-loop中间隔插入三条消息同任务合并且锚不漂"

import asyncio
from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, create_session, send_chat, check_db, check_logs,
    print_report, write_test_record, register_pending_record, filter_safety_errors,
    get_user_message_rows, extract_task_id, assert_injection_ack, assert_merged_point_to,
    assert_injected_rows_bound, assert_injection_anchor_not_drifted, injection_llm_evidence,
)

# 第一条: 多步骤任务(检索+对比+三段长文写作) → 强制多轮 LLM 与工具调用, 撑起 loop 注入窗口。
#   前缀用于界面区分(见设计要点①)。实测 INJ-02 同款主消息活期 329~362s。
FIRST_INPUT = (
    "【INJ-03 三条注入验证】请完成一个多步骤的研究与写作任务, 每一步都要真实执行, 不要跳过:\n"
    "1. 深度检索最近5年人工智能领域的重要技术发现与技术进展;\n"
    "2. 对比分析 agent(智能体) 技术最近5年的发展演进, 说明与上一代技术的差异;\n"
    "3. 基于以上检索与分析, 写出一份人工智能的详细报告, 覆盖技术原理, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "4. 再写一份 agent 领域的报告, 覆盖应用场景、未来趋势三个部分, "
    "每个部分都要展开说明, 总字数不少于两千字;\n"
    "5. 最后详细说明 agent 未来趋势的应用领域分别是什么, 每一个部分都要详细展开。"
)
# 三条追加指令(内容互不相同, 便于事后核对 LLM 是否都吸收)
SECOND_INPUT = "在报告里再补充一个量子计算的章节。"
THIRD_INPUT = "另外请增加一章讨论人工智能在医疗领域的应用。"
FOURTH_INPUT = "再补充一一个文档说明agent的最新架构模型有几种最新进展。"

FIRST_WAIT_SEC = 25   # 等第一条进入 loop(命中与否由断言裁定, 非盲等)
INTERVAL_SEC = 20     # 相邻两条注入的间隔(实测任务活期 300s+, 三条落在 25/45/65s 均在 loop 内)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_inj_03_triple_injection():
    """INJ-03: 任务loop中间隔插入三条消息, 均命中注入、归同一任务、锚不漂。"""
    test_start = datetime.now()
    passed = False
    error_info = None
    first = None
    injs = []          # 三次 send_chat 结果, 顺序 = 注入顺序
    acked_tids = []    # 三次应答的 merged_into_task_id
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
        print(f"[INJ3] 第一条已后台运行 {FIRST_WAIT_SEC}s, 发第二条")

        # ── 间隔插入三条: 第二 → 第三 → 第四条 ─────────────────────
        for i, (text, label) in enumerate((
            (SECOND_INPUT, "第二条"),
            (THIRD_INPUT, "第三条"),
            (FOURTH_INPUT, "第四条"),
        )):
            if i:
                await asyncio.sleep(INTERVAL_SEC)
                print(f"[INJ3] 间隔 {INTERVAL_SEC}s 后发{label}")
            res = await send_chat(text, session_id=session_id)
            injs.append(res)
            acked_tids.append(assert_injection_ack(res, label))

        # ── 等第一条跑完(吸收三条追加内容后完成) ──────────────────
        first = await first_task
        first_task = None
        elapsed = first["total_time_ms"] / 1000.0
        print(f"[INJ3] 第一条完成: steps={first['total_steps']}, tools={len(first['tool_calls'])}")

        # ── 三条 merged 都必须指向第一条的真实 task_id(共享 helper) ──
        _first_tid = extract_task_id(first)
        _labels = ("第二条", "第三条", "第四条")
        assert_merged_point_to(acked_tids, _first_tid, _labels)

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
        # 恰好 4 条(首条+注入3条): == 而非 >=, 多一条即重复落库(B-1 根因), 少一条即丢消息
        assert db["messages_count"] == 4, \
            f"应恰好 4 条 user 消息(首条+三条注入), 实际 {db['messages_count']} 条(MUST)"

        # ── 三条注入行绑定 + 锚不漂(共享 helper) ──
        _rows = get_user_message_rows(session_id)
        assert len(_rows) == 4, f"行级读取应得 4 行, 实际 {len(_rows)} 行(与 messages_count 不一致)"
        _by_id = {r.get("id"): r for r in _rows}
        _inj_rows = assert_injected_rows_bound(
            _rows, [r["user_msg_id"] for r in injs], _first_tid, _labels)
        assert_injection_anchor_not_drifted(
            _by_id.get(first["user_msg_id"]), _inj_rows[-1])

        # ── LLM 是否真吸收三条追加内容(共享 helper, 只记录不断言) ──
        _evid = injection_llm_evidence(
            str(_inj_rows[-1].get("response") or ""),
            ["量子计算", "医疗", "架构模型"])
        print(f"[INJ3] LLM吸收证据: {_evid}")

        # ── 日志校验 ───────────────────────────────────────────────
        lc = check_logs(test_start, session_id)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志有Traceback(MUST): {lc['tracebacks'][:1]}"

        print_report(
            TEST_CASE_ID, "活跃任务注入-三条", first, db, lc, ci, si, True, elapsed,
            extra={"注入首事件": "merged/merged/merged",
                   "目标任务": _first_tid,
                   "三条耗时": [f"{r['total_time_ms'] / 1000.0:.2f}s" for r in injs],
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
            # 注入行(注入消息数/落库行数)由 write_test_record 自推导(/tasks 的 merged_inputs), case 零传参
        )
