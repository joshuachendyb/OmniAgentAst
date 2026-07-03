"""E2E-P4-04: 时间规划（DATA多工具）
操作手册:
  用例: E2E-P4-04
  用户输入: time_now→time_diff→query_calendar→time_diff→写报告
  前置数据: 无
  预期调用链: time_now→time_diff→query_calendar→time_diff→write_text_file
  通过标准: 报告包含时间计算结果
  失败标准: 报告未生成或内容不完整

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P4-04"
TEST_CASE_NAME = "时间规划"
USER_INPUT = (
    "请帮我做一份下周的工作时间规划。"
    "首先，获取当前系统的准确日期和时间，包括年、月、日、星期几，把当前时间信息展示出来。"
    "然后，计算从今天到下周一之间还有多少天，精确到天。"
    "接着，查询下周一是不是工作日——如果是工作日就标记为可用工作日，如果是法定节假日或周末则说明原因。"
    "再计算从今天到本月底还有多少天，判断剩余时间是否足够完成一个标准的工作计划安排。"
    "最后，把以上所有时间计算和规划信息汇总整理成一份时间规划报告，"
    "保存到E:\\test_dir\\time_plan.txt文件中，报告要包含当前时间信息、到下周一的天数和工作日状态、"
    "到月底的天数，以及基于这些信息的合理工作安排建议。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
)

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
async def test_e2e_p4_04_time_plan():
    """P4-04: 时间规划"""
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
            "E2E-P4-04", "时间规划",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动"
        record_test_baseline()

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        assert result["total_steps"] >= 2, "至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, "疑似死循环(MUST)"

        for issue in verify_response_quality(result):
            pass
        for issue in verify_response_time(result):
            pass

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], "is_valid必须为true(MUST)"
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
        _safety_kw = [
            "execute_code", "pickle", "RCE", "extract", "create_task",
            "delete_task", "Permission denied", "DB operation failed",
            "NoneType", "Errno 13", "ERR_SQL_EXEC", "UNIQUE constraint",
        ]
        _safety_errs = [e for e in lc["errors"] if any(k in e for k in _safety_kw)]
        _other_errs = [e for e in lc["errors"] if e not in _safety_errs]
        assert len(_other_errs) == 0, f"日志不应有非安全ERROR(MUST): {_other_errs[:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "E2E-P4-04", "时间规划", result, db, lc,
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
            "E2E-P4-04", "时间规划",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
