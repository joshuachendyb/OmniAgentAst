"""E2E-E2E-P5-18: 计时+网络搜索+系统监控+文件汇总+通知完成
操作手册: NETWORK+SYSTEM+FILE+DESKTOP组合
预期调用链: get_current_time->search_web(x2)->fetch_webpage(x3)->get_system_info->write_text_file->send_notification
前置数据: 网络连通；系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-18"
TEST_CASE_NAME = "计时+网络搜索+系统监控+文件汇总+通知完成"
USER_INPUT = (
    "这是一项多阶段日报生成任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：时间信息采集】"
    "第一步，获取当前日期和精确时间（到秒），显示年/月/日/时/分/秒/星期几/今年的第几天。"
    ""
    "【阶段二：多关键词新闻搜索】"
    "第二步，搜索\"今日科技新闻\"，获取前5条最新结果，展示标题和摘要。"
    "第三步，搜索\"最新技术动态2026\"，获取前5条结果。"
    "第四步，打开前3条最有价值的搜索结果，提取每篇文章的核心要点和关键数据。"
    ""
    "【阶段三：系统状态监控】"
    "第五步，获取当前CPU使用率百分比。"
    "第六步，获取物理内存使用情况：总量、已用、可用和使用率。"
    "第七步，获取所有磁盘分区的使用情况：盘符、总量、可用空间。"
    "第八步，获取系统运行时间（已开机多久）。"
    ""
    "【阶段四：Python日报组装脚本】"
    "第九步，写一个Python脚本做日报的自动化组装：从前面获取的数据中提取关键指标生成日报模板、"
    "计算今日系统资源平均使用率、计算新闻中各主题的分布比例、"
    "将时间信息、新闻摘要和系统状态三部分合并成一份格式化的日报内容，保存到E:\\test_dir\\daily_report.txt。"
    ""
    "【阶段五：通知与四版本报告】"
    "第十步，给我发一条通知告诉我日报已生成，通知包含日报日期和主要内容摘要。"
  "第十一步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_18_time_search_sys_file_notify():
    """E2E-P5-18: 计时+网络搜索+系统监控+文件汇总+通知完成"""
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
            "E2E-P5-18", "计时+网络搜索+系统监控+文件汇总+通知完成",
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
            "E2E-P5-18", "计时+网络搜索+系统监控+文件汇总+通知完成", result, db, lc,
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
            "E2E-P5-18", "计时+网络搜索+系统监控+文件汇总+通知完成",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
