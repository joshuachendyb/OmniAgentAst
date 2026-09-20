"""全链路E2E集成测试 - PAR-01: 并行会话多任务执行 - 3会话并发纯LLM对话

操作手册对照:
   用例: E2E-PAR-01 (并行专项, 标识 PAR = Parallel)
   用户输入: 3个不同会话同时发起纯LLM对话(禁工具), 每会话输入含唯一关键词
     S1关键词"青花瓷" / S2关键词"光合作用" / S3关键词"丝绸之路"
   前置数据: 无(后端已按手册6.1启动)
   预期过程: 3会话并发执行互不干扰; 每会话流独立完整; 第二阶段S1追加一轮对话正常
   通过标准:
     1. 3个session_id两两不同, user_msg_id两两不同
     2. 每会话收到final事件且无error; 回复含本会话唯一关键词(防串流)
     3. 每会话DB校验全过(session/消息/顺序/步骤字段/时间)
     4. SSE-DB一致性/步骤合理性全过; 日志无Traceback、无非安全ERROR
     5. S1第二轮对话正常, DB内user消息顺序正确
   失败标准: 任一会话串流/丢终态/报错; session或消息id重复; 日志有Traceback

 针对今日(2026-09-20)并行相关修复:
   E-1 stream_reader锁内不yield / D-2 allocator读写锁 / B机制注入串行守卫 /
   P5 LLM软配额信号量 / D-8取消帧去重 / C-1共享池快照 / D-1注入消息DB补配对

 铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端运行, 禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-09-20
"""

TEST_CASE_ID = "E2E-PAR-01"
TEST_CASE_NAME = "并行会话多任务执行-3会话并发纯LLM对话"
USER_INPUT = "PAR-01三会话并发: 青花瓷/光合作用/丝绸之路(各禁工具)"

import asyncio
from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

PAR_INPUTS = [
    ("E2E-PAR-01-S1", "青花瓷",
     "请用三句话介绍青花瓷是什么, 包括它的釉色特点和代表性产地。注意: 本次只用对话回答, 不要调用任何工具。"),
    ("E2E-PAR-01-S2", "光合作用",
     "请用三句话解释光合作用的基本过程, 包括原料和产物。注意: 本次只用对话回答, 不要调用任何工具。"),
    ("E2E-PAR-01-S3", "丝绸之路",
     "请用三句话介绍丝绸之路的起点和主要意义。注意: 本次只用对话回答, 不要调用任何工具。"),
]

FOLLOW_UP_S1 = "用一句话总结你刚才的回答。注意: 只用对话回答, 不要调用任何工具。"


def _check_one(tag, keyword, user_input, result, test_start):
    """单会话断言包(MUST全量): 流终态/关键词归属/DB/一致性/日志。"""
    sid = result["session_id"]
    elapsed = result["total_time_ms"] / 1000.0

    end_type = assert_stream_ended(result)
    assert result["total_steps"] >= 2, f"{tag} 至少start+final(MUST), got {result['total_steps']}"
    assert result["unique_step_numbers"] < 300, f"{tag} 疑似死循环(MUST): {result['unique_step_numbers']}步"
    assert len(result.get("tool_calls", [])) == 0, f"{tag} 纯问答不应调工具(MUST)"
    assert not result["has_error"], f"{tag} 流不应有error(MUST)"

    resp = result["response_text"]
    assert len(resp) > 10, f"{tag} 回复太短({len(resp)}字)(SHOULD)"
    assert keyword in resp, f"{tag} 回复缺本会话关键词[{keyword}], 疑似串流(MUST)"

    db = check_db(sid)
    assert db["session_exists"], f"{tag} session必须保存到DB(MUST)"
    assert db["is_valid"], f"{tag} is_valid必须为true(MUST), got {db['is_valid']}"
    assert db["has_user_message"], f"{tag} 必须有user消息(MUST)"
    assert db["has_assistant_message"], f"{tag} 必须有assistant消息(MUST)"
    assert db["message_order_correct"], f"{tag} 消息顺序必须user在前(MUST)"
    assert len(db["step_field_issues"]) == 0, f"{tag} step字段不完整(MUST): {db['step_field_issues']}"
    assert len(db["time_issues"]) == 0, f"{tag} 时间异常(MUST): {db['time_issues']}"

    ci = verify_consistency(result, sid)
    assert len(ci) == 0, f"{tag} 一致性验证失败(MUST): {ci}"

    si = verify_steps(result, sid)
    assert len(si) == 0, f"{tag} 步骤合理性异常: {si}"

    lc = check_logs(test_start, sid)
    filtered = filter_safety_errors(lc["errors"])
    assert len(filtered["other_errors"]) == 0, f"{tag} 日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
    assert len(lc["tracebacks"]) == 0, f"{tag} 日志不应有Traceback(MUST)"

    print_report(
        tag, f"并行会话-{keyword}", result, db, lc,
        ci, si, True, elapsed,
        extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
    )
    return sid, db, ci, si, lc, elapsed


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_par_01_concurrent_sessions():
    """PAR-01: 3会话并发纯LLM对话, 互不干扰; S1再追加一轮。"""
    test_start = datetime.now()
    passed = False
    per_session = {}  # tag -> (result, db, ci, si, lc, elapsed)
    sids = []
    error_info = None

    try:
        register_pending_record(
            "E2E-PAR-01", "并行会话多任务执行-3会话并发纯LLM对话",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # 第一阶段: 3会话真正并行发起(同事件循环gather, 各自独立session)
        results = await asyncio.gather(*[
            send_chat(user_input) for _, _, user_input in PAR_INPUTS
        ])

        # 跨会话隔离断言(MUST): session与user消息id全局唯一, 防分配器竞态重号
        sids = [r["session_id"] for r in results]
        assert len(set(sids)) == 3, f"3会话session_id必须两两不同(MUST), got {sids}"
        msg_ids = [r["user_msg_id"] for r in results]
        assert len(set(msg_ids)) == 3, f"3会话user_msg_id必须两两不同(MUST), got {msg_ids}"

        for (tag, keyword, user_input), result in zip(PAR_INPUTS, results):
            per_session[tag] = (result, *_check_one(tag, keyword, user_input, result, test_start)[1:])

        # 第二阶段: S1会话内追加一轮(验证D-1配对/B机制常规路径并发后正常)
        sid_s1 = sids[0]
        r2 = await send_chat(FOLLOW_UP_S1, session_id=sid_s1)
        assert r2["session_id"] == sid_s1, "追加轮必须落回S1会话(MUST)"
        end2 = assert_stream_ended(r2)
        assert not r2["has_error"], "S1追加轮不应有error(MUST)"
        db2 = check_db(sid_s1)
        assert db2["has_user_message"] and db2["has_assistant_message"], "S1追加后消息必须完整(MUST)"
        assert db2["message_order_correct"], "S1追加后消息顺序必须正确(MUST)"
        ci2 = verify_consistency(r2, sid_s1)
        assert len(ci2) == 0, f"S1追加轮一致性失败(MUST): {ci2}"

        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        for tag, _, user_input in PAR_INPUTS:
            if tag not in per_session:
                continue
            _r, _db, _ci, _si, _lc, _el = per_session[tag]
            write_test_record(
                tag, f"并行会话多任务-{tag}",
                user_input,
                _r or {}, _db, _ci, _si, _lc, passed, _el,
                error_info=error_info,
            )
        # 主记录: 覆盖register_pending_record留下的空占位, 汇总三会话结论
        # 2026-09-21 小欧
        if per_session:
            _m = per_session[PAR_INPUTS[0][0]]
            write_test_record(
                "E2E-PAR-01", TEST_CASE_NAME, USER_INPUT,
                _m[0], _m[1], _m[2], _m[3], _m[4], passed,
                sum(v[5] for v in per_session.values()),
                error_info=error_info,
            )
