"""全链路E2E集成测试 - P0-02: 工具调用通路验证
严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

操作手册对照:
  用例: E2E-P0-02
  用户输入: "在E盘创建一个e2e_test_p0.txt,内容为hello"
  预期过程: Agent调用writetext,返回成功
  通过标准: SSE包含action事件;DB有execution_steps记录;文件存在且内容正认
  失败标准: 未调用工具;文件未创建;DB无记录

铁律:
   1. 一个用例一个脚本,写完跑通再写下一个
   2. 所有验证基于真实在里运行,禁止Mock
   3. 测试前必须重启在里服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-15
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
"""

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db, check_logs,
    verify_db_prompt_consistency,
    print_report, write_test_record,
    assert_stream_ended, verify_consistency, verify_steps, filter_safety_errors,
    register_pending_record,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_02_tool_call():
    """P0-02: 工具调用通路验证 - 创建文件"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = ("系统的每个维度最好给出具体的功能描述和适用场景,让我对你能做什么,不能做什么有个清晰的预期."
    "获取本机的IP地址,详细的网络信息,内外网状态,并报告.分析当地城市是哪个?获取当地城市的最近10天的天气趋势并报告"
        "另外你的回复机制是什么样的——能流式输出吗?"
        "讲能力汇总写两个报告一个文本报告一个是doc报告"
        "将本次任务的工具调用进行合理性分析,甄别工具和工具参数是否合理, 是否无效的重复,并写出本次任务的工具调用分析报告"
        )

    try:
        register_pending_record(
            "unit-02", "工具调用通路验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "在里未启动(手册6.1)"


        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        end_type = assert_stream_ended(result)
        assert end_type == "final", f"任务必须以final正常结束(MUST), actual: {end_type}"

        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["功能", "描述", "场景", "报告", "助手", "AI", "可以", "能够"]
        assert any(t in resp for t in key_terms), "回复与功能描述无关(SHOULD)"

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-02)"

        db = check_db(sid)
        # 2026-08-07 小欧: 迁移新版helperAPI(原assert_db_integrity→DB字段显式断言)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], "is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"DB步骤字段异常(MUST): {db['step_field_issues']}"
        assert db["execution_steps_count"] > 0, f"必须有execution_steps(MUST P0-02)"
        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        assert len(db_tool_steps) > 0, "DB steps中必须有action_tool(MUST P0-02)"
        for step in db_tool_steps:
            assert step.get("tool_name"), f"tool_name不能为空(MUST)"
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"工具结果不能为空(MUST): {step.get('tool_name')}"

        # 2026-08-07 小欧: 原assert_data_consistency→verify_consistency+verify_steps
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        # 2026-08-07 小欧: 原assert_log_clean→filter_safety_errors过滤断言
        _safety = filter_safety_errors(lc["errors"])
        assert len(_safety["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {_safety['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB↔Prompt不一致(MUST): {dpi}"

        print_report(
            "unit-02", "工具调通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "DbPromptIssues": len(dpi)},
        )

        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        write_test_record("unit-02", "工具调用通路验证", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)
