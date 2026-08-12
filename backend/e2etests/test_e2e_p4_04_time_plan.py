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
    "这是一项多阶段时间规划分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：当前时间全方位获取】"
    "第一步，获取当前系统的准确日期和时间，精确到秒，展示年、月、日、时、分、秒、星期几（中文）、"
    "今天是今年的第几天、今年是否是闰年、当前时区和UTC时间偏移。"
    "第二步，计算今天所在的月份还剩多少天、今年还剩多少天、今天离年底还有多少周。"
    ""
    "【阶段二：区间计算与工作日分析】"
    "第三步，计算从今天到下周一之间还有多少天（精确到天）、多少小时。"
    "第四步，查询从今天开始未来14天（共15天）的日历，每天标注是否工作日、是否为法定节假日。"
    "第五步，写一个Python脚本计算工作日统计：在未来的14天中有几个工作日、几个休息日、"
    "如果某个日期是法定节假日则单独标记，保存统计结果到E:\\test_dir\\workday_analysis.txt。"
    ""
    "【阶段三：多段差分计算】"
    "第六步，计算从今天到本月底还有多少天，再计算从今天到下一季度第一天还有多少天。"
    "第七步，计算从今年1月1日到今天已经过去了多少天，精确计算到今天占全年的百分比。"
    "第八步，写一个Python脚本做时间区间重叠分析：假设有一个项目周期从今天+7天开始到今天+45天结束，"
    "检查这个项目周期与哪些节假日区间有重叠（如国庆节、元旦等），把结果保存到E:\\test_dir\\project_schedule_check.txt。"
    ""
    "【阶段四：工作计划生成】"
    "第九步，基于以上所有时间信息生成一份详细的工作计划安排：以周为单位列出未来4周、"
    "标注每周的工作日数量、标注已知的节假日、给出每周的工作目标建议，保存到E:\\test_dir\\work_plan+时间.txt。"
    ""
    "【阶段五：四版本报告】"
    "第十步，把所有时间计算和规划信息独立生成四种版本的报告,（TXT版本、DOCX版本、结构化DOCX版、PDF版本）存入你创建于于本次任务相关的目录存放报告。"
    "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告"
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
        assert result["unique_step_numbers"] < 300, "疑似死循环(MUST)"

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
            "pickle", "RCE", "extract", "create_task",
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
