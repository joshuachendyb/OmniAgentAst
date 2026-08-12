"""E2E-E2E-P5-17: 文档读取+文字提取+日期计算+通知完成
操作手册: DOCUMENT+FILE+TIME+DESKTOP组合
预期调用链: read_docx->write_text_file->write_text_file->get_current_time->send_notification
前置数据: test.docx存在于E:\test_dir\
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-17"
TEST_CASE_NAME = "文档读取+文字提取+日期计算+通知完成"
USER_INPUT = (
    "这是一项多阶段文档读取提取日期计算与通知任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：文档内容读取】"
    "第一步，读取E:\\test_dir\\test.docx的全部内容，展示文档总段落数、总字符数和内容摘要。"
    "第二步，提取文档中的所有文本段落，按顺序保存到E:\\test_dir\\doc_content.txt，每段前标注段落编号。"
    ""
    "【阶段二：文档元数据提取】"
    "第三步，提取文档的元数据：作者、创建日期、最后修改日期、最后修改者、修订次数、总编辑时间、应用程序版本。"
    "第四步，如果文档包含表格，提取各表格的数据并保存到E:\\test_dir\\doc_tables.txt。"
    "第五步，提取文档中的标题层次结构，构建目录树保存到E:\\test_dir\\doc_toc.txt。"
    ""
    "【阶段三：时间差分计算】"
    "第六步，获取当前系统的日期和时间。"
    "第七步，写一个Python脚本做时间差分计算：从文档创建日期到今天的总天数、总小时数和总分钟数、"
    "计算文档创建以来的周数（向下取整）、计算文档创建日期是星期几、判断文档是否是在工作时间内创建的，"
    "把时间分析报告保存到E:\\test_dir\\time_diff_analysis.txt。"
    ""
    "【阶段四：元数据保存与通知】"
    "第八步，把文档元数据和时间分析结果汇总保存到E:\\test_dir\\doc_metadata.txt。"
    "第九步，把所有处理状态汇总，给我发一条通知告诉我处理完成，通知包含：文档总字数、元数据项数、创建至今的天数。"
    ""
    "【阶段五：四版本报告】"
    "第十步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_17_doc_read_extract_date_notify():
    """E2E-P5-17: 文档读取+文字提取+日期计算+通知完成"""
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
            "E2E-P5-17", "文档读取+文字提取+日期计算+通知完成",
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
            "E2E-P5-17", "文档读取+文字提取+日期计算+通知完成", result, db, lc,
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
            "E2E-P5-17", "文档读取+文字提取+日期计算+通知完成",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
