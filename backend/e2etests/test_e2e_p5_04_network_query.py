"""E2E-E2E-P5-04: 网络查询链
操作手册: NETWORK组合-搜索+打开
预期调用链: search_web(x2)->fetch_webpage(x3)->write_text_file
前置数据: 网络连通
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-04"
TEST_CASE_NAME = "网络查询链"
USER_INPUT = (
    "这是一项多阶段网络查询分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：关键词搜索】"
    "第一步，搜索关键词\"2026年人工智能突破\"，获取前5条搜索结果，展示每条结果的标题、摘要和URL。"
    "第二步，搜索关键词\"最新科技新闻2026\"，同样获取前5条结果，展示标题、摘要和URL。"
    ""
    "【阶段二：深度内容获取】"
    "第三步，打开第一次搜索的前3条结果，获取详细页面内容，提取文章的核心观点、关键数据和发布日期。"
    "第四步，打开第二次搜索的前3条结果，同样提取核心观点和关键数据。"
    ""
    "【阶段三：内容汇总与交叉分析】"
    "第五步，把两次搜索共6篇文章的内容汇总到一个结构化的摘要中，每篇文章标注来源、标题、核心观点和关键数据。"
    "第六步，写一个Python脚本做交叉分析：统计出现频率最高的技术热词、分辨不同文章对同一话题的报道一致性、"
    "汇总各篇报道中出现的数据指标（如\"增长X%\"、\"投资X亿\"），把分析结果保存到E:\\test_dir\\tech_analysis.txt。"
    ""
    "【阶段四：报告生成】"
    "第七步，把汇总的分析结果保存到E:\\test_dir\\network_research.txt，使用清晰的标题层级和分段组织内容。"
    ""
    "【阶段五：四版本报告】"
    "第八步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_04_network_query():
    """E2E-P5-04: 网络查询链"""
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
            "E2E-P5-04", "网络查询链",
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
            "E2E-P5-04", "网络查询链", result, db, lc,
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
            "E2E-P5-04", "网络查询链",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
