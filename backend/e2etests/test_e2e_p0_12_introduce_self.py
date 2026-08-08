"""全链路E2E集成测试 - P0-12: 自我介绍通路验证

操作手册对照:
   用例: E2E-P0-12
    用户输入: "Multi-dimensional self-intro (file/code/web/system/data), tech, capability boundary table; conversation only, no tools"
   通过标准: 流正常结束；不调工具；回复包含能力描述
   失败标准: 流异常中止；调用了工具

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-14, 小沈 2026-07-03 rewrite
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
-- 更新: 2026-07-14(提升user input复杂度-多维度LLM提问,保持禁工具) 小欧
"""

TEST_CASE_ID = "E2E-P0-12"
TEST_CASE_NAME = "自我介绍通路验证"
USER_INPUT = ("Tell me about yourself in depth. Please cover: "
               "(1) your full capability spectrum across file operations, coding/execution, web search, "
               "system administration and data analysis, with 2 concrete examples each; "
               "(2) the underlying technology and how streaming responses work; "
               "(3) which file types and data formats you support; "
               "(4) scenarios where you will refuse or ask for confirmation. "
               "End with a comparison table of 'can do / cannot do / needs confirmation'. "
               "Note: answer by conversation only, do not invoke any tools."
               "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告")

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    register_pending_record,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_12_introduce_self():
    """P0-12: 自我介绍"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    try:
        register_pending_record(
            "E2E-P0-12", "自我介绍通路验证(12)",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")
        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {tool_names}")

        end_type = assert_stream_ended(result)
        print(f"  流结束: {end_type}")

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 300, f"疑似死循环(MUST)"

        if result["has_error"]:
            print(f"  [WARN] 有Error事件(SHOULD)，流结束: {end_type}")

        # MUST P0-12: 纯对话不应调工具
        tool_calls = result.get("tool_calls", [])
        assert len(tool_calls) == 0, f"纯问答不应调工具(MUST P0-12), 实际: {[t['tool_name'] for t in tool_calls]}"

        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["assistant", "AI", "can", "help", "capable", "助手", "可以", "能够"]
        assert any(t.lower() in resp.lower() for t in key_terms), "回复与自我介绍无关(SHOULD)"

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB-Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-12", "自我介绍通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
        )

        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"  [FAIL] 异常: {error_info[:500]}")
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        write_test_record("E2E-P0-12", "自我介绍通路验证(12)", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)

    if passed:
        print(f"\n  [DONE] E2E-P0-12 PASSED")
