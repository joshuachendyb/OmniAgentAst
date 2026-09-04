"""全链路E2E集成测试 - P0-02: 工具调用通路验证

操作手册对照:
  用例: E2E-P0-02
  用户输入: "在E盘创建一个e2e_test_p0.txt，内容为hello"
  预期过程: Agent调用writetext，返回成功
  通过标准: SSE包含action事件；DB有execution_steps记录；文件存在且内容正确
  失败标准: 未调用工具；文件未创建；DB无记录

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-15
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
-- 更新: 2026-08-22 - 小欧 - §10.3适配: 本case旧action_tool取数块(type过滤+顶层tool_name+observation字段)收敛为verify_db_tool_usage单点校验(e2e_helpers FUNCTIONS.md九.1), 协议再变只改helper一处
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
    verify_db_tool_usage,
)

TEST_FILE = Path("E:/e2e_test_p0.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_02_tool_call():
    """P0-02: 工具调用通路验证 - 创建文件"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = "在E盘创建一个e2e_test_p0.txt，内容为hello"

    if TEST_FILE.exists():
        TEST_FILE.unlink(missing_ok=True)

    try:
        register_pending_record(
            "E2E-mod-02", "工具调用通路验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"


        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"

        if result["has_error"]:
            pass

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-02)"
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        write_tools = {"writetext"}
        has_write = any(n in write_tools for n in tool_names)
        assert has_write, f"应调用写文件工具(MUST P0-02), 实际: {tool_names}"


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

        # 2026-08-22 小欧 §10.3适配: 旧action_tool取数块收敛为verify_db_tool_usage单点校验(FUNCTIONS.md 9.1)
        _ti = verify_db_tool_usage(db)
        assert len(_ti) == 0, f"DB steps中必须有action步骤(MUST): {_ti}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert lc["session_records_found"], "日志应有session操作记录(SHOULD)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB↔Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-02", "工具调通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "File": str(TEST_FILE), "DbPromptIssues": len(dpi)},
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
        if TEST_FILE.exists():
            TEST_FILE.unlink(missing_ok=True)
        write_test_record("E2E-P0-02", "工具调用通路验证", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)
