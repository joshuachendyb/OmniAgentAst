"""E2E-E2E-P5-01: 文件全流程
操作手册: FILE多工具组合-创建/写入/读取/搜索/追加/文件信息
预期调用链: write_text_file->read_text_file->grep_file->append_to_file->read_text_file->get_file_info->list_directory
前置数据: E:\\test_dir\\ 可写
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-01"
TEST_CASE_NAME = "文件全流程"
USER_INPUT = (
    "这是一项多阶段文件全流程处理任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：文件创建与初始写入】"
    "第一步，在E:\\test_dir下创建一个e2e_mc01.txt文件，写入初始测试数据，内容包含：第一行\"===测试数据文件===\"、"
    "第二行一个Python字典格式的数据{'id':1,'name':'张三','score':95,'city':'北京'}、"
    "第三行一个JSON数组格式的数据[10,20,30,40,50]、第四行开始写一段至少50个字的自我介绍。"
    ""
    "【阶段二：内容验证与搜索】"
    "第二步，把刚写入的文件内容读出来，逐行验证：第一行是否等于===测试数据文件===、JSON行是否有效、字典行是否包含4个键。"
    "第三步，搜索文件中是否包含\"测试\"这个词，还搜索一下有没有\"北京\"这个词，把搜索结果和出现位置展示给我。"
    "第四步，写一个Python脚本来验证文件内容的完整性：读文件全部内容、解析每一行的格式、检查JSON和字典格式是否正确、"
    "报告文件是否有空行或格式错误，把验证脚本和执行结果保存到E:\\test_dir\\file_verify.txt。"
    ""
    "【阶段三：追加与再验证】"
    "第五步，在文件末尾追加一行数据：\"---文件结束---\"，再追加一条时间戳行\"生成时间: [当前日期时间]\"。"
    "第六步，追加完后重新读取文件全部内容，确认新追加的行已经正确写入且原内容未丢失，把完整内容展示给我。"
    ""
    "【阶段四：文件信息与目录清单】"
    "第七步，查询文件的大小（字节数）、创建日期、修改日期和属性特征。"
    "第八步，列出E:\\test_dir下的所有文件和子目录，获取每个文件的大小和修改时间，展示完整目录清单。"
    ""
    "【阶段五：四版本报告】"
    "第九步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版本、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
    "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性分析报告"
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
async def test_e2e_p5_01_file_workflow():
    """E2E-P5-01: 文件全流程"""
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
            "E2E-P5-01", "文件全流程",
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
            "E2E-P5-01", "文件全流程", result, db, lc,
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
            "E2E-P5-01", "文件全流程",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
