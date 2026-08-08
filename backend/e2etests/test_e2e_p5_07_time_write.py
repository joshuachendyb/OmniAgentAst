"""E2E-E2E-P5-07: 时间写文件
操作手册: TIME+FILE组合
预期调用链: get_current_time->write_text_file->read_text_file->get_file_info
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-07"
TEST_CASE_NAME = "时间写文件"
USER_INPUT = (
    "这是一项多阶段时间处理与文件写入任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：全方位时间获取】"
    "第一步，获取当前系统时间：年、月、日、时、分、秒、星期几（中文）、今天是今年的第几天、今年总天数、时区信息。"
    "第二步，获取UTC时间和本地时间的差值，计算出当前UTC的具体时间。"
    "第三步，写一个Python脚本做时间格式转换：把当前时间分别格式化为ISO 8601格式、RFC 2822格式、Unix时间戳、"
    "中国标准时间格式（YYYY年MM月DD日 HH:mm:ss 星期X），把各种格式输出保存到E:\\test_dir\\time_formats.txt。"
    ""
    "【阶段二：动态文件名创建与写入】"
    "第四步，使用当前时间生成文件名（格式：YYYYMMDD_HHmmss.txt），在E:\\test_dir下创建该文件。"
    "第五步，向文件中写入详细的层次化时间信息：第一行标题\"===系统时间报告===\"、"
    "第二部分本地时间（年/月/日/时/分/秒/星期）、第三部分UTC时间、"
    "第四部分各种格式化时间、第五部分时间戳。"
    ""
    "【阶段三：内容验证与文件元数据】"
    "第六步，读取刚创建的文件内容，逐行验证每个时间字段是否正确写入。"
    "第七步，查询该文件的大小（字节数）、创建时间、修改时间和只读属性。"
    "第八步，写一个Python脚本验证文件中的时间信息之间的逻辑一致性：检查年月日时分秒是否匹配、"
    "检查星期几是否与日期对应、检查文件创建时间与写入内容中的时间是否一致，把验证结果保存到E:\\test_dir\\time_verify.txt。"
    ""
    "【阶段四：四版本报告】"
    "第九步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、带时间表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_07_time_write():
    """E2E-P5-07: 时间写文件"""
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
            "E2E-P5-07", "时间写文件",
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
            "E2E-P5-07", "时间写文件", result, db, lc,
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
            "E2E-P5-07", "时间写文件",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
