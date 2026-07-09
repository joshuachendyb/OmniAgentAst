"""E2E-E2E-P5-16: 网络搜索+文件保存+时间记录+通知提醒
操作手册: NETWORK+FILE+TIME+DESKTOP组合
预期调用链: search_web(x2)->fetch_webpage(x3)->write_text_file->get_current_time->send_notification
前置数据: 网络连通
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-16"
TEST_CASE_NAME = "网络搜索+文件保存+时间记录+通知提醒"
USER_INPUT = (
    "这是一项多阶段搜索保存时间通知一站式任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：多关键词并发搜索】"
    "第一步，搜索\"AI行业热点今天\"，获取前5条结果，展示标题、摘要和来源。"
    "第二步，搜索\"人工智能新闻今日\"，获取前5条结果。"
    "第三步，搜索\"大模型最新动态\"，获取前3条结果。"
    ""
    "【阶段二：深度内容打开与分析】"
    "第四步，打开第一次搜索的前3条结果的详细内容，从每篇文章中提取：核心新闻事件、涉及的公司、影响范围。"
    "第五步，打开第二次搜索的前3条结果的详细内容，同样提取核心要点。"
    "第六步，打开第三次搜索的前2条结果的详细内容，提取大模型更新要点。"
    ""
    "【阶段三：新闻汇总与Python分析】"
    "第七步，把8篇文章的要点汇总成结构化的新闻摘要，按主题分组（技术突破/商业动态/政策法规）。"
    "第八步，写一个Python脚本做新闻热点分析：从摘要文本中提取高频关键词（排除停用词后统计词频）、"
    "识别出出现频率最高的公司名和人物名、计算不同主题的文章数量占比，把分析结果保存到E:\\test_dir\\news_analysis.txt。"
    ""
    "【阶段四：保存与通知】"
    "第九步，把完整的新闻摘要保存到E:\\test_dir\\ai_news.txt，包含报告生成时间、主题分类和各主题下的新闻条目。"
    "第十步，获取当前时间作为所有操作完成的时间记录，追加写入文件末尾。"
    "第十一步，给我发一条桌面通知告诉我所有操作已完成，通知内容包含摘要总条数和生成的文件路径。"
    ""
    "【阶段五：四版本报告】"
    "第十二步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_16_search_save_time_notify():
    """E2E-P5-16: 网络搜索+文件保存+时间记录+通知提醒"""
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
            "E2E-P5-16", "网络搜索+文件保存+时间记录+通知提醒",
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
            "E2E-P5-16", "网络搜索+文件保存+时间记录+通知提醒", result, db, lc,
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
            "E2E-P5-16", "网络搜索+文件保存+时间记录+通知提醒",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
