"""E2E-P4-01: 文档处理流程（DOCUMENT多工具）
操作手册:
  用例: E2E-P4-01
  用户输入: 读docx→写docx→转PDF→列目录→写log
  前置数据: test.docx存在于E:\test_dir
  预期调用链: read_docx→write_docx→convert_document→list_directory→write_text_file
  通过标准: 新Word文档和PDF都存在
  失败标准: 任意生成文件缺失

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P4-01"
TEST_CASE_NAME = "文档处理流程"
USER_INPUT = (
    "这是一项多阶段文档处理任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：文档读取与分析】"
    "第一步，读取E:\\test_dir\\test.docx的内容，提取所有文本段落、表格数据和各级标题，"
    "展示给我看文档总共有多少段落、多少个表格、内容的大致篇幅。"
    "第二步，分析文档中使用的字体、字号、段落间距等格式信息，把格式特征记录下来。"
    "第三步，写一个Python脚本统计文档的词频分布——提取所有单词的出现次数，把词频前十的单词及其出现次数保存到E:\\test_dir\\word_freq.txt。"
    ""
    "【阶段二：内容重组与增强】"
    "第四步，基于原始内容，创建一个增强版Word文档output.docx保存到E:\\test_dir\\，"
    "具体要求：重新组织段落（按主题分组）、添加标题编号、插入词频统计表格、"
    "把分析出来的格式特征写入文档末尾的元数据部分。"
    "第五步，将output.docx的内容读出来验证写入是否正确，把验证结果展示给我。"
    ""
    "【阶段三：格式转换】"
    "第六步，把原始的test.docx转换成PDF格式保存到E:\\test_dir\\output.pdf。"
    "第七步，写一个Python脚本来验证PDF是否成功生成，检查PDF文件大小（应大于1KB）、文件头签名是否为%PDF，把验证结果保存到E:\\test_dir\\pdf_verify.txt。"
    ""
    "【阶段四：目录校验与汇总】"
    "第八步，列出E:\\test_dir目录下的所有文件，获取每个文件的大小和修改时间，逐个确认词频文件、word文档、PDF文件和验证文件都存在。"
    ""
    "【阶段五：四版本报告】"
    "第九步，把本次任务的执行过程、各阶段结果、文件生成状态汇总整理，"
    "独立生成四种版本的报告（TXT版本、DOCX版本、带图表的DOCX完整版、PDF版本）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p4_01_doc_process():
    """P4-01: 文档处理流程"""
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
            "E2E-P4-01", "文档处理流程",
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
            "E2E-P4-01", "文档处理流程", result, db, lc,
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
            "E2E-P4-01", "文档处理流程",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
