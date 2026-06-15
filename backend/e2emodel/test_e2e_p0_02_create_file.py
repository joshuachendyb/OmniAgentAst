"""E2E-P0-02: tool call path - create file

Manual ref: E2E-P0-02
Input: "create e2e_test_p0.txt on E: with content hello"
Expected: Agent calls write_text_file, returns success
Pass: SSE has action event; DB has execution_steps; file exists with correct content
Fail: no tool call; file not created; no DB record

Rules:
  1. one case one script, pass then next
  2. real backend, no mock
  3. restart backend before test (manual 6.1)
  4. no emoji in test code

-- xiaojian 2026-06-14
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    cleanup, print_report, write_test_record,
    get_security_enabled, set_security_enabled,
)

TARGET_FILE = Path("E:/e2e_test_p0.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_02_create_file():
    """P0-02: tool call path - create file"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; lc = {"errors":[],"tracebacks":[]}
    user_input = "在E盘创建一个e2e_test_p0.txt，内容为hello"

    orig_security = get_security_enabled()
    set_security_enabled(False)

    try:
        assert ensure_backend_ready(), "backend not ready(manual 6.1)"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {[t['tool_name'] for t in result['tool_calls']]}")

        assert not result["has_error"], "no error(MUST)"
        assert result["final_event"] is not None, "must have final(MUST)"
        assert result["total_steps"] >= 2, f"at least start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"suspect loop(MUST)"

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        write_tools = {"write_text_file", "write_file", "file_operation"}
        has_write = any(n in write_tools for n in tool_names)
        assert has_write, f"must call write tool(MUST P0-02), actual: {tool_names}"

        assert TARGET_FILE.exists(), f"file must exist(MUST P0-02): {TARGET_FILE}"
        content = TARGET_FILE.read_text(encoding="utf-8", errors="ignore").strip()
        assert "hello" in content.lower(), f"file must contain hello(MUST P0-02), got: {content[:100]}"

        resp = result["response_text"]
        assert resp, "response not empty(MUST)"

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session must exist in DB(MUST)"
        assert db["is_valid"], f"is_valid must be true(MUST)"
        assert db["has_user_message"], "must have user msg(MUST)"
        assert db["has_assistant_message"], "must have assistant msg(MUST)"
        assert db["message_order_correct"], "order must be user first(MUST)"
        assert db["execution_steps_count"] >= 1, f"must have steps(MUST P0-02), got {db['execution_steps_count']}"
        assert len(db["step_field_issues"]) == 0, f"step fields incomplete(MUST): {db['step_field_issues']}"

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"consistency failed(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"step issues: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid)
        assert len(lc["errors"]) == 0, f"no ERROR in log(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "no traceback(MUST)"
        if not lc["session_records_found"]:
            print("  [WARN] log: session records not found(SHOULD, non-blocking)")
        if not lc["sse_records_found"]:
            print("  [WARN] log: SSE records not found(SHOULD, non-blocking)")

        print_report(
            "E2E-P0-02", "tool call path-create file", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "File": str(TARGET_FILE)},
        )

        passed = True

    finally:
        write_test_record("P0-02", "tool call path-create file", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0)
        if orig_security is not None:
            set_security_enabled(orig_security)
        if TARGET_FILE.exists():
            try:
                TARGET_FILE.unlink(missing_ok=True)
            except PermissionError:
                print(f"  [WARN] cannot delete {TARGET_FILE}(PermissionError)")
        cleanup(session_id=sid)

    if passed:
        print(f"\n  [DONE] E2E-P0-02 PASSED")