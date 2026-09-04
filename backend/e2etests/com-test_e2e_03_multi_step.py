"""全链路E2E集成测试 - P0-03: 多步推理通路验证
严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

 操作手册对照:
   用例: E2E-P0-03
    用户输入: 综合能力验证-报告能力/网络状态/天气/多类工具操作验证(文档/文件/网络/代码/系统/监控)/清理目录/工具调用合理性分析
    预期过程: 执行读取类工具(文本/媒体/文档任一)验证文档文件读取能力,再完成其余操作
    通过标准: 调用了读取类工具(文本/媒体/文档任一);回复完整;DB有>=2条steps
    失败标准: 未调用任何读取类工具;回复为空;DB无步骤记录

 铁律:
   1. 一个用例一个脚本,写完跑通再写下一个
   2. 所有验证基于真实在里运行,禁止Mock
   3. 测试前必须重启在里服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-14
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
-- 更新: 2026-08-22 - 小欧 - §10.3适配: 本case旧action_tool取数块(type过滤+顶层tool_name+observation字段)收敛为verify_db_tool_usage单点校验(e2e_helpers FUNCTIONS.md九.1), 协议再变只改helper一处
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db, check_logs,
    verify_db_prompt_consistency,
    print_report, write_test_record,
    assert_stream_ended, verify_consistency, verify_steps, filter_safety_errors,
    register_pending_record,
    verify_db_tool_usage,
)

TEST_FILE = Path("E:/test_dir/test.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_03_multi_step_reasoning():
    """P0-03: 多步推理通路 - 读文件再回复内容"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = ("首先告诉我你有哪些能力?"
        "获取本机的IP地址,详细的网络信息,网络联通状况,并报告."
        "分析当地城市是哪个?获取当地城市的最近20天的天气趋势并报告"
        "然后针对那些能力,你自己执行从file 网络 获取和网络测试 代码执行 系统管理 监控等都执行一系列操作 "
        "shell工具不要频繁使用,做好每一个tool都验证一下,重点验证文档文件网络的操作能力是不是达到日常业务处理的能力"
        "检查实际的操作能力是什么样, 然在 讲这些能力情况的检查分析结果 汇总到报告中"
        "清理目录下的10日前的目录和文件"
        "清理目录下的大小超过50M的文件"
        "将本次任务的工具调用进行合理性分析,甄别工具和工具参数是否合理, 是否无效的重复,并写出本次任务的工具调用分析报告"
        )

    try:
        register_pending_record(
            "unit-03", "多步推理通路验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "backend not ready(manual 6.1)"
        assert TEST_FILE.exists(), f"test file not found: {TEST_FILE}"


        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]

        end_type = assert_stream_ended(result)
        assert end_type == "final", f"任务必须以final正常结束(MUST), actual: {end_type}"

        read_tools = {"readtext", "readmedia", "read_pdf", "read_docx", "read_pptx", "read_xlsx"}
        has_read = any(n in read_tools for n in tool_names)
        assert has_read, f"must call read tool(文本/媒体/文档任一读取,MUST P0-03), actual: {tool_names}"

        resp = result["response_text"]
        assert resp, "response not empty(MUST)"
        assert len(resp) > 10, f"response too short(SHOULD): {len(resp)}"

        db = check_db(sid)
        # 2026-08-07 小欧: 迁移新版helperAPI(原assert_db_integrity→DB字段显式断言)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], "is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"DB步骤字段异常(MUST): {db['step_field_issues']}"
        assert db["execution_steps_count"] >= 2, f"must have >=2 steps(MUST P0-03), got {db['execution_steps_count']}"

        # 2026-08-22 小欧 §10.3适配: 旧action_tool取数块收敛为verify_db_tool_usage单点校验(FUNCTIONS.md 9.1)
        _ti = verify_db_tool_usage(db, expect_any_tools=read_tools)
        assert len(_ti) == 0, f"DB steps must have read op(MUST P0-03): {_ti}"

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
            "unit-03", "multi-step reasoning-read file", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "DbPromptIssues": len(dpi)},
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
        write_test_record("unit-03", "multi-step reasoning-read file", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)
