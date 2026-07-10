"""全链路E2E集成测试 - P0-07: FILE+SHELL+NETWORK混合通路验证

操作手册对照:
   用例: E2E-P0-07
   用户输入: 创建check_network.py脚本+执行+搜索最佳实践+写报告
   通过标准: 流正常结束；创建文件；调用shell；网络搜索；DB记录完整
   失败标准: 流异常中止；DB记录不完整

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-14, 小沈 2026-07-03 rewrite
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
"""

TEST_CASE_ID = "E2E-P0-07"
TEST_CASE_NAME = "FILE+SHELL+NETWORK混合通路验证"
USER_INPUT = (
    "请帮我完成一项多阶段网络诊断脚本任务，严格按照以下步骤执行："
    "第一阶段，在E:\\test_dir\\下创建一个Python脚本network_diag.py，脚本功能包括："
    "用socket库检测本地主机名和IP地址，用requests库尝试访问http://www.baidu.com并记录HTTP状态码和响应时间，"
    "检测8.8.8.8的连通性（ping模拟），将所有检测结果格式化输出。"
    "第二阶段，执行network_diag.py脚本，捕获全部输出。"
    "第三阶段，在网上搜索\"Windows网络诊断最佳实践\"，获取前3条搜索结果的详细内容，"
    "提取出诊断步骤和常用命令行工具.用这些工具编写10个以上不同脚本, 每一个脚本多种组合的的网络诊断代码来测试。"
    "第四阶段，将脚本执行结果与网上搜索到的诊断方法编写的各自脚本进行对比分析，"
    "汇总整理成一份完整的网络诊断报告保存到E:\\test_dir\\network_diagnosis_report.txt。"
    "将本次任务的分析和完成过程总结以4种文档格式写到report目录下自建任务相关的目录下保存。"
)

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    register_pending_record,
    filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_07_file_shell_network():
    """P0-07: FILE+SHELL+NETWORK混合通路"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    try:
        register_pending_record(
            "E2E-P0-07", "FILE+SHELL+NETWORK混合通路(07)",
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

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-07)"

        resp = result["response_text"]
        assert resp, "回复不能为空(MUST)"
        assert len(resp) > 10, f"回复太短(SHOULD): {len(resp)}"

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["execution_steps_count"] >= 2, f"必须有>=2步(MUST)"
        if len(db["step_field_issues"]) > 0:
            print(f"  [WARN] step字段问题(SHOULD): {db['step_field_issues']}")

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        filtered = filter_safety_errors(lc["errors"])
        if filtered["safety_errors"]:
            print(f"  [INFO] Safety checker errors (expected): {len(filtered['safety_errors'])}")
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB-Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-07", "FILE+SHELL+NETWORK混合通路", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names},
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
        write_test_record("E2E-P0-07", "FILE+SHELL+NETWORK混合通路(07)", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)

    if passed:
        print(f"\n  [DONE] E2E-P0-07 PASSED")
