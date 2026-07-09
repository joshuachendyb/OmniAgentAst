"""全链路E2E集成测试 - P1-04: FILE工具多任务场景- 数据归档流程
操作手册对照:
   用例: E2E-P1-04
   用户输入: 执行一个多步骤数据归档操作
   通过标准: 流正常结束；zip/tar/manifest/report存在；DB记录完整
   失败标准: 流异常中止；归档文件缺失

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
    4. 禁止在测试代码中使用emoji字符
    5. finally中必须调用write_test_record(手册5.5铁律)
    6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
 
-- 小健 2026-06-24, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P1-04"
TEST_CASE_NAME = "FILE工具多任务场景- 数据归档流程"
USER_INPUT = "list files in E:\\test_dir, create archive.zip and archive.tar in E:\\test_dir\\backup, generate manifest and report"

from datetime import datetime
import os

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    verify_response_quality,
    verify_db_steps_data_completeness,
    register_pending_record, filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p1_04_data_archive():
    """P1-04: FILE工具多任务场景- 数据归档流程"""

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
    user_input = USER_INPUT

    try:
        register_pending_record(
            "E2E-P1-04", "FILE多任务-数据归档",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"疑似死循环(MUST)"

        quality_issues = verify_response_quality(result)
        assert len(quality_issues) == 0, f"回复质量问题: {quality_issues}"
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        db_steps_issues = verify_db_steps_data_completeness(sid)
        assert len(db_steps_issues) == 0, f"DB步骤数据不完整(MUST): {db_steps_issues}"

        lc = check_logs(test_start, sid)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "E2E-P1-04", "FILE多任务-数据归档", result, db, lc,
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
            "E2E-P1-04", "FILE多任务-数据归档",
            user_input, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
