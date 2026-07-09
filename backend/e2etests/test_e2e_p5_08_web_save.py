"""E2E-E2E-P5-08: 网页存文件
操作手册: NETWORK+FILE组合
预期调用链: search_web(天气)->fetch_webpage->search_web(本周)->fetch_webpage->write_text_file
前置数据: 网络连通
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-08"
TEST_CASE_NAME = "网页存文件"
USER_INPUT = (
    "这是一项多阶段天气查询与报告生成任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：今日天气查询】"
    "第一步，搜索\"北京今天天气\"获取今日天气预报。"
    "第二步，打开今日天气的详细页面，提取以下信息：当前温度、最高/最低温度、天气状况（晴/阴/雨/雪）、"
    "湿度百分比、风力风向、紫外线指数和空气质量指数。"
    "第三步，把提取到的今日天气信息整理成结构化摘要。"
    ""
    "【阶段二：本周天气预报】"
    "第四步，搜索\"北京一周天气预报\"获取未来一周的天气趋势。"
    "第五步，从结果中提取今明后三天的逐日预报：每一天的日期、最高/最低温度、天气状况和风力。"
    ""
    "【阶段三：数据对比分析】"
    "第六步，写一个Python脚本做天气对比分析：比较今明后三天的温度变化趋势（温差大小）、"
    "识别哪天温度最高、哪天温度最低、哪天天气最好（晴天无雨风力小），"
    "如果数据可用则计算本周与上周同期的温度对比，把分析结果保存到E:\\test_dir\\weather_analysis.txt。"
    ""
    "【阶段四：合并报告生成】"
    "第七步，把今日天气详情和本周天气预报合并成一份完整的天气报告保存到E:\\test_dir\\weather_report.txt，"
    "报告包含：报告生成时间、今日天气详情表、今明后逐日预报、温度趋势分析和出行建议。"
    ""
    "【阶段五：四版本报告】"
    "第八步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、带天气表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_08_web_save():
    """E2E-P5-08: 网页存文件"""
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
            "E2E-P5-08", "网页存文件",
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
            "E2E-P5-08", "网页存文件", result, db, lc,
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
            "E2E-P5-08", "网页存文件",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
