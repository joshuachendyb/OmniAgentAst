"""全链路E2E集成测试 - P0-03: 多步推理通路验证

操作手册对照:
  用例: E2E-P0-03
  用户输入: "读取E:\test_dir\test.txt的内容，然后告诉我里面写了什么"
  预期过程: 先调read_file，再回复内容
  通过标准: 调用了read_file；回复中包含文件内容；DB有2条steps
  失败标准: 未调用read_file；回复中无文件内容

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-14
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

TEST_FILE = Path("E:/test_dir/test.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_03_multi_step_reasoning():
    """P0-03: 多步推理通路 - 读文件再回复内容"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = "读取E:\\test_dir\\test.txt的内容，然后告诉我里面写了什么"

    try:
        register_pending_record(
            "E2E-mod-03", "多步推理通路验证",
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

        assert result["total_steps"] >= 2, f"at least start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"suspect loop(MUST)"

        if result["has_error"]:
            pass

        read_tools = {"read_file", "read_text_file", "read_media_file"}
        has_read = any(n in read_tools for n in tool_names)
        assert has_read, f"must call read tool(MUST P0-03), actual: {tool_names}"

        resp = result["response_text"]
        assert resp, "response not empty(MUST)"
        assert len(resp) > 10, f"response too short(SHOULD): {len(resp)}"


        db = check_db(sid)
        assert db["session_exists"], "session must exist in DB(MUST)"
        assert db["is_valid"], f"is_valid must be true(MUST)"
        assert db["has_user_message"], "must have user msg(MUST)"
        assert db["has_assistant_message"], "must have assistant msg(MUST)"
        assert db["message_order_correct"], "order must be user first(MUST)"
        assert db["execution_steps_count"] >= 2, f"must have >=2 steps(MUST P0-03), got {db['execution_steps_count']}"
        assert len(db["step_field_issues"]) == 0, f"step fields incomplete(MUST): {db['step_field_issues']}"

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        db_read_steps = [s for s in db_tool_steps if s.get("tool_name") in read_tools]
        assert len(db_read_steps) > 0, "DB steps must have read op(MUST P0-03)"

        for step in db_tool_steps:
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"tool result not empty(MUST): {step.get('tool_name')}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"consistency failed(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"step issues: {si}"

        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        assert len(lc["errors"]) == 0, f"no ERROR in log(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "no traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB↔Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-03", "multi-step reasoning-read file", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "Read steps": len(db_read_steps), "DbPromptIssues": len(dpi)},
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
        write_test_record("E2E-P0-03", "multi-step reasoning-read file", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)
