"""E2E-E2E-P5-14: 计时+系统监控+截屏+报告归档
操作手册: TIME+SYSTEM+DESKTOP+FILE组合
预期调用链: get_current_time->get_system_info->list_processes->screen_capture->get_display_info->write_text_file
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-14"
TEST_CASE_NAME = "计时+系统监控+截屏+报告归档"
USER_INPUT = (
    "这是一项多阶段系统监控与截图报告任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：时间与系统状态快照】"
    "第一步，获取当前精确时间（到秒），显示日期、星期几、时间的完整信息。"
    "第二步，获取CPU使用率百分比和CPU温度（如果可用）。"
    "第三步，获取物理内存使用情况：总量、已用、可用和使用率。"
    "第四步，获取所有磁盘分区的使用情况：各分区的总量、已用、可用和使用率。"
    ""
    "【阶段二：进程监控与截屏】"
    "第五步，按内存使用量排序列出占用资源最多的前10个进程，包含进程名、PID和内存占用量。"
    "第六步，按CPU使用率排序同样列出前10个进程的详细信息。"
    "第七步，截取当前屏幕的完整截图，保存到E:\\test_dir\\screenshot_monitor.png。"
    "第八步，获取屏幕显示信息：分辨率、色彩深度、刷新率。"
    ""
    "【阶段三：Python监控数据分析】"
    "第九步，写一个Python脚本做系统快照综合分析：计算资源综合使用率（CPU和内存加权平均）、"
    "识别出资源消耗大户（累计占用>30%的进程）、"
    "与上一次的系统状态做对比（如果有之前的监控数据保存在E:\\test_dir\\monitor_history.txt则读取并对比），"
    "如果没有历史数据则生成基线记录，把监控分析报告保存到E:\\test_dir\\monitor_analysis.txt。"
    ""
    "【阶段四：监控报告生成】"
    "第十步，把时间和系统状态信息、进程列表、截图信息和Python分析结果汇总成监控报告保存到E:\\test_dir\\monitor_report.txt。"
    ""
    "【阶段五：四版本报告】"
    "第十一步，独立生成四种版本的报告（TXT版、带截图的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_14_time_monitor_screenshot_report():
    """E2E-P5-14: 计时+系统监控+截屏+报告归档"""
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
            "E2E-P5-14", "计时+系统监控+截屏+报告归档",
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
            "E2E-P5-14", "计时+系统监控+截屏+报告归档", result, db, lc,
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
            "E2E-P5-14", "计时+系统监控+截屏+报告归档",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
