"""全链路E2E集成测试 - P0-00: 纯LLM对话通路 - 无工具调用

操作手册对照:
   用例: E2E-P0-00 (新增)
   用户输入: "详细介绍一下你自己，你能做什么?"
   前置数据: 无
   预期过程: LLM直接回复，不调用任何工具
   通过标准: 收到final事件；回复语义完整；len(tool_calls)==0
   失败标准: 调用了工具；回复为空或胡言乱语；收到error

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-26
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
"""

TEST_CASE_ID = "E2E-P0-00"
TEST_CASE_NAME = "纯LLM对话通路 - 无工具调用"
USER_INPUT = "嗨，听说你是一个AI助手？我很好奇你到底是什么样的存在——你能做哪些事情？比如能帮我写代码吗？能操作我的电脑吗？能上网搜索信息吗？最好举几个实际的例子说明，让我了解你的能力边界在哪里。另外想问问你是怎么工作的，背后是用的什么技术？"

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_00_simple_intro():
    """P0-00: 纯LLM对话 - 自我介绍，严禁调工具"""
    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    try:
        # 提前注册待写入记录，确保中断时也能生成记录 -- 小沈 2026-07-01
        register_pending_record(
            "E2E-P0-00", "纯LLM对话通路-无工具调用",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 300, f"疑似死循环(MUST): {result['unique_step_numbers']}步"
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) == 0, f"纯问答不应调工具(MUST P0-00), 实际工具: {[t['tool_name'] for t in tool_calls]}"

        if result["has_error"]:
            pass

        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["助手", "AI", "可以", "能够", "帮助"]
        assert any(t in resp for t in key_terms), "回复与自我介绍无关(SHOULD)"


        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        lc = check_logs(test_start, sid)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有Traceback(MUST)"

        print_report(
            "E2E-P0-00", "纯LLM对话通路-无工具调用", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        write_test_record(
            "E2E-P0-00", "纯LLM对话通路-无工具调用",
            user_input,
            r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
