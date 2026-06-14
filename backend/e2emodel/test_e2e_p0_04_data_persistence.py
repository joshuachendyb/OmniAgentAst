"""全链路E2E集成测试 - P0-04: 数据持久化通路验证

操作手册对照:
  用例: E2E-P0-04
  用户输入: "列出E:\test_dir下的所有文件"
  预期过程: 调用list_directory，返回文件列表
  通过标准: sessions表有记录；messages表有user+assistant；execution_steps有步骤记录
  失败标准: 任一表无记录；记录不完整

铁律:
  1. 一个用例一个脚本，写完跑通再写下一个
  2. 所有验证基于真实后端运行，禁止Mock
  3. 测试前必须重启后端服务(手册6.1)
  4. 禁止在测试代码中使用emoji字符

-- 小健 2026-06-14
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    cleanup, print_report,
    get_security_enabled, set_security_enabled,
)

TEST_DIR = Path("E:/test_dir")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_04_data_persistence():
    """P0-04: 数据持久化通路 - 列目录验证三张表"""

    test_start = datetime.now()

    orig_security = get_security_enabled()
    set_security_enabled(False)

    try:
        # 步骤1
        assert ensure_backend_ready(), "后端未启动(手册6.1)"
        assert TEST_DIR.exists(), f"测试目录不存在: {TEST_DIR}"

        user_input = "列出E:\\test_dir下的所有文件"
        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        # 步骤2-3
        result = await send_chat(user_input)
        session_id = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {[t['tool_name'] for t in result['tool_calls']]}")

        # ── L1 MUST层 ──
        assert not result["has_error"], "不应有error(MUST)"
        assert result["final_event"] is not None, "必须有final(MUST)"
        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"疑似死循环: {result['unique_step_numbers']}步(MUST)"

        # P0-04核心: 必须调用list_directory
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        list_tools = {"list_directory", "list_files"}
        has_list = any(n in list_tools for n in tool_names)
        assert has_list, f"必须调用list_directory(MUST P0-04), 实际: {tool_names}"

        # P0-04核心: 回复应包含文件名
        resp = result["response_text"]
        assert resp, "回复不能为空(MUST)"
        resp_lower = resp.lower()
        has_test_file = "test.txt" in resp_lower or "test_dir" in resp_lower
        assert has_test_file, f"回复应包含文件名(MUST P0-04), 回复: {resp[:200]}"
        print(f"  [Step4] Response: {resp[:150]}...")

        # 步骤5: DB记录完整性 (P0-04核心验证)
        print(f"  [Step5] DB check - 三表验证...")
        db = check_db(session_id)

        # 验证sessions表
        assert db["session_exists"], "sessions表必须有记录(MUST P0-04)"
        assert db["is_valid"], f"sessions.is_valid必须为true(MUST P0-04), got {db['is_valid']}"
        print(f"  [Step5] sessions表: OK (id={session_id[:16]}..., is_valid=true)")

        # 验证messages表
        assert db["has_user_message"], "messages表必须有user消息(MUST P0-04)"
        assert db["has_assistant_message"], "messages表必须有assistant消息(MUST P0-04)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST P0-04)"
        print(f"  [Step5] messages表: OK (user+assistant, order correct)")

        # 验证execution_steps
        assert db["execution_steps_count"] >= 1, (
            f"execution_steps必须有记录(MUST P0-04), 实际={db['execution_steps_count']}"
        )
        assert len(db["step_field_issues"]) == 0, (
            f"step字段不完整(MUST P0-04): {db['step_field_issues']}"
        )

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        db_list_steps = [s for s in db_tool_steps if s.get("tool_name") in list_tools]
        assert len(db_list_steps) > 0, "DB steps中应有list操作(MUST P0-04)"

        # 验证工具结果字段完整
        for step in db_tool_steps:
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"工具结果不能为空(MUST): {step.get('tool_name')}"

        print(f"  [Step5] execution_steps表: OK (total={db['execution_steps_count']}, list_steps={len(db_list_steps)})")

        # 步骤6: SSE vs DB一致性
        print(f"  [Step6] SSE-DB consistency...")
        consistency_issues = verify_consistency(result, session_id)
        assert len(consistency_issues) == 0, (
            f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in consistency_issues)
        )
        print(f"  [Step6] Consistency: OK")

        # 步骤7: 步骤合理性
        print(f"  [Step7] Step reasonableness...")
        step_issues = verify_steps(result, session_id)
        assert len(step_issues) == 0, f"步骤合理性异常: {step_issues}"
        print(f"  [Step7] Steps: OK")

        # 步骤8: 日志检查
        print(f"  [Step8] Log check...")
        log_check = check_logs(test_start, session_id)
        assert len(log_check["errors"]) == 0, f"日志不应有ERROR(MUST): {log_check['errors'][:3]}"
        assert len(log_check["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert log_check["session_records_found"], "日志应有session操作记录(SHOULD)"
        if not log_check["sse_records_found"]:
            print("  [WARN] 日志未找到SSE事件记录(SHOULD, non-blocking)")

        # 步骤9: 报告
        print_report(
            "E2E-P0-04", "数据持久化通路验证", result, db, log_check,
            consistency_issues, step_issues, True, elapsed,
            extra={
                "LLM calls": result["llm_call_count"],
                "Tools": tool_names,
                "DB steps": db["execution_steps_count"],
                "DB tool_steps": len(db_tool_steps),
            },
        )

    finally:
        if orig_security is not None:
            set_security_enabled(orig_security)
        cleanup(session_id=session_id)

    print(f"\n  [DONE] E2E-P0-04 PASSED")
