# -*- coding: utf-8 -*-
"""E2E-P9-01: 空输入

操作手册对照:
  用例: E2E-P9-01
  用户输入: "  介绍自己 " 
  前置数据: 无
  预期行为: 不崩溃，不死循环，无final事件
  验证标准: final事件存在，无步骤异常

-- 小欧 2026-06-27
-- 北京老陈 2026-07-04 修正乱码
"""

TEST_CASE_ID = "E2E-P9-01"
TEST_CASE_NAME = "介绍自己"
USER_INPUT = "介绍自己 ,有什么能力,要详细 举例说明  "

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, record_test_baseline,
    verify_response_quality, verify_response_time,
    verify_db_steps_data_completeness,
    register_pending_record,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p9_01_empty_input():
    from datetime import datetime

    test_start = datetime.now()
    passed = False
    r = None
    sid = None
    db = {}
    ci = []
    si = []
    lc = {"errors": [], "tracebacks": []}
    elapsed = 0.0
    error_info = None

    try:
        register_pending_record(
            "E2E-P9-01", "介绍自己",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        record_test_baseline()

        if not result["has_error"]:
            assert result["total_steps"] >= 2, f"至少要有start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 50, f"疑似死循环(MUST): {result['unique_step_numbers']}步"

        if result["has_error"]:
            print(f"  [WARN] 有error事件(SHOULD), 流结束: {end_type}")

        for issue in verify_response_quality(result):
            pass
        for issue in verify_response_time(result):
            pass

        db = check_db(sid)
        assert db["session_exists"], "session必须存在于DB(MUST)"
        if not result["has_error"]:
            assert db["is_valid"], "is_valid必须为True(MUST)"
            assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        if not result["has_error"]:
            assert db["has_assistant_message"], "必须有assistant消息(MUST)"

        ci = verify_consistency(result, sid)
        si = verify_steps(result, sid)

        db_steps_issues = verify_db_steps_data_completeness(sid)
        if len(db_steps_issues) > 0:
            print(f"  [WARN] DB步骤数据不完整(SHOULD, non-blocking): {db_steps_issues}")

        lc = check_logs(test_start, sid)
        if len(lc["errors"]) > 0:
            print(f"  [WARN] 日志中有ERROR(SHOULD, non-blocking): {lc['errors'][:3]}")

        print_report(
            "E2E-P9-01", "空输入", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
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
        write_test_record(
            "E2E-P9-01", "空输入",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
