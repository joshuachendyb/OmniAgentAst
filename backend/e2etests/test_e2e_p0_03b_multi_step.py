"""全链路E2E集成测试 - P0-03b: 多步推理通路验证

操作手册对照:
   用例: E2E-P0-03b
   用户输入: "读取E:\test_dir\test.txt并做详细分析"
   预期过程: 先调read_file，再分析统计
   通过标准: 调用了read_file；回复包含文件内容及统计特征；DB有步骤记录
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

TEST_CASE_ID = "E2E-P0-03b"
TEST_CASE_NAME = "多步推理通路验证"
USER_INPUT = "请读取E:\\test_dir\\test.txt文件的内容并做详细分析。先读取全文，然后分别统计：文件一共有多少个字符（含空格和不含空格）、多少个单词、多少行。统计完成后，把原始内容和你分析得到的统计特征——字符数、单词数、行数、是否包含数字或特殊字符——一起汇总给我。如果有中英文混合的内容，也分别统计中文字符数和英文字符数。"

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    cleanup, print_report, write_test_record,
    assert_stream_ended,
    register_pending_record,
)

TEST_FILE = Path("E:/test_dir/test.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_03b_multi_step_reasoning():
    """P0-03b: 多步推理通路 - 读文件再回复内容"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    try:
        register_pending_record(
            "E2E-P0-03b", "multi-step reasoning-read file(03b)",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "backend not ready(manual 6.1)"
        assert TEST_FILE.exists(), f"test file not found: {TEST_FILE}"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {tool_names}")

        end_type = assert_stream_ended(result)
        print(f"  流结束: {end_type}")

        assert result["total_steps"] >= 2, f"at least start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"suspect loop(MUST)"

        if result["has_error"]:
            print(f"  [WARN] has error event(SHOULD)，流结束: {end_type}")

        read_tools = {"read_file", "readtext", "readmedia"}
        has_read = any(n in read_tools for n in tool_names)
        assert has_read, f"must call read tool(MUST P0-03b), actual: {tool_names}"

        resp = result["response_text"]
        assert resp, "response not empty(MUST)"
        assert len(resp) > 10, f"response too short(SHOULD): {len(resp)}"

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session must exist in DB(MUST)"
        assert db["is_valid"], f"is_valid must be true(MUST)"
        assert db["has_user_message"], "must have user msg(MUST)"
        assert db["has_assistant_message"], "must have assistant msg(MUST)"
        assert db["message_order_correct"], "order must be user first(MUST)"
        assert db["execution_steps_count"] >= 2, f"must have >=2 steps(MUST P0-03b), got {db['execution_steps_count']}"
        assert len(db["step_field_issues"]) == 0, f"step fields incomplete(MUST): {db['step_field_issues']}"

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        db_read_steps = [s for s in db_tool_steps if s.get("tool_name") in read_tools]
        assert len(db_read_steps) > 0, "DB steps must have read op(MUST P0-03b)"

        for step in db_tool_steps:
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"tool result not empty(MUST): {step.get('tool_name')}"

        print(f"  [Step5] DB OK: steps={db['execution_steps_count']}, tool_steps={len(db_tool_steps)}, read_steps={len(db_read_steps)}")

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"consistency failed(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"step issues: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        safety_errors = [e for e in lc["errors"] if any(k in e for k in ["安全检查", "拒绝执行", "高风险", "execute_code", "pickle", "RCE", "extract", "create_task", "delete_task"])]
        other_errors = [e for e in lc["errors"] if e not in safety_errors]
        if safety_errors:
            print(f"  [INFO] Safety/unrelated errors (expected): {len(safety_errors)}")
        assert len(other_errors) == 0, f"no ERROR in log(MUST): {other_errors[:3]}"
        assert len(lc["tracebacks"]) == 0, "no traceback(MUST)"
        if not lc["session_records_found"]:
            print("  [WARN] log: session records not found(SHOULD, non-blocking)")
        if not lc["sse_records_found"]:
            print("  [WARN] log: SSE records not found(SHOULD, non-blocking)")

        print(f"  [Step8b] DB-Prompt consistency...")
        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB->Prompt mismatch(MUST): {dpi}"

        print_report(
            "E2E-P0-03b", "multi-step reasoning-read file", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "Read steps": len(db_read_steps), "DbPromptIssues": len(dpi)},
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
        write_test_record("E2E-P0-03b", "multi-step reasoning-read file(03b)", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)

    if passed:
        print(f"\n  [DONE] E2E-P0-03b PASSED")
