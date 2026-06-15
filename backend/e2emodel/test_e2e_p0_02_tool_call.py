"""全链路E2E集成测试 - P0-02: 工具调用通路验证

操作手册对照:
  用例: E2E-P0-02
  用户输入: "在E盘创建一个e2e_test_p0.txt，内容为hello"
  预期过程: Agent调用write_text_file，返回成功
  通过标准: SSE包含action事件；DB有execution_steps记录；文件存在且内容正确
  失败标准: 未调用工具；文件未创建；DB无记录

铁律:
  1. 一个用例一个脚本，写完跑通再写下一个
  2. 所有验证基于真实后端运行，禁止Mock
  3. 测试前必须重启后端服务(手册6.1)
  4. 禁止在测试代码中使用emoji字符

-- 小健 2026-06-15
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    cleanup, print_report, write_test_record,
    get_security_enabled, set_security_enabled,
    assert_stream_ended,
)

TEST_FILE = Path("E:/e2e_test_p0.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_02_tool_call():
    """P0-02: 工具调用通路验证 - 创建文件"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}
    user_input = "在E盘创建一个e2e_test_p0.txt，内容为hello"

    if TEST_FILE.exists():
        TEST_FILE.unlink(missing_ok=True)

    orig_security = get_security_enabled()
    set_security_enabled(False)

    try:
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {[t['tool_name'] for t in result['tool_calls']]}")

        # ── L1 流结束验证(所有方式有效，不阻断) ──
        end_type = assert_stream_ended(result)
        print(f"  流结束: {end_type}")

        # ── L1 MUST层 ──
        assert result["total_steps"] >= 2, f"至少start+final(MUST)"

        # ── L2 SHOULD WARN: has_error降级 ──
        if result["has_error"]:
            print(f"  [WARN] 有error事件(SHOULD)，流结束: {end_type}")

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-02)"
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        write_tools = {"write_text_file", "write_file", "file_operation", "create_file"}
        has_write = any(n in write_tools for n in tool_names)
        assert has_write, f"应调用写文件工具(MUST P0-02), 实际: {tool_names}"

        print(f"  [Step5] File check...")
        assert TEST_FILE.exists(), f"文件必须已创建(MUST P0-02): {TEST_FILE}"
        file_content = TEST_FILE.read_text(encoding="utf-8")
        assert "hello" in file_content.lower(), f"文件内容应含'hello'(MUST P0-02)"

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["execution_steps_count"] > 0, f"必须有execution_steps(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        assert len(db_tool_steps) > 0, "DB steps中必须有action_tool(MUST)"
        for step in db_tool_steps:
            assert step.get("tool_name"), f"tool_name不能为空(MUST)"
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"工具结果不能为空(MUST): {step.get('tool_name')}"

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert lc["session_records_found"], "日志应有session操作记录(SHOULD)"
        if not lc["sse_records_found"]:
            print("  [WARN] 日志未找到SSE事件记录(SHOULD, non-blocking)")

        print(f"  [Step8b] DB-Prompt consistency...")
        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB↔Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-02", "工具调通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "File": str(TEST_FILE), "DbPromptIssues": len(dpi)},
        )

        passed = True

    finally:
        if TEST_FILE.exists():
            TEST_FILE.unlink(missing_ok=True)
        write_test_record("E2E-P0-02", "工具调用通路验证", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi)
        if orig_security is not None:
            set_security_enabled(orig_security)
        cleanup(session_id=sid)

    if passed:
        print(f"\n  [DONE] E2E-P0-02 PASSED")
