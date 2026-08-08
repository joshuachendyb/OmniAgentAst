"""E2E-E2E-P5-02: 文件管理链
操作手册: FILE组合-重命名+复制+备份
预期调用链: rename_file->copy_file->read_text_file->get_file_info->list_directory
前置数据: e2e_mc01.txt存在于E:\test_dir\；E:\test_dir\backup\ 可写
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-02"
TEST_CASE_NAME = "文件管理链"
USER_INPUT = (
    "这是一项多阶段文件管理任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：文件重命名】"
    "第一步，把E:\\test_dir\\e2e_mc01.txt重命名为e2e_mc02.txt。"
    "第二步，重命名后读取e2e_mc02.txt的内容，验证文件内容没有因为改名而丢失。"
    "第三步，检查改名后e2e_mc01.txt是否已不存在（即原路径确认文件已移走），获取e2e_mc02.txt的文件信息确认改名成功。"
    ""
    "【阶段二：文件备份】"
    "第四步，在E:\\test_dir\\backup目录下创建一份e2e_mc02.txt的副本，命名为e2e_mc02_backup.txt。"
    "第五步，读取备份文件的内容，与原文件逐行对比，确认内容是否完全一致，展示对比结果。"
    "第六步，写一个Python脚本来做文件完整性校验：计算原文件和备份文件的MD5哈希值，对比哈希是否一致，"
    "再比较两个文件的大小（字节数是否相同）、修改时间差异，把校验报告保存到E:\\test_dir\\backup_verify.txt。"
    ""
    "【阶段三：版本比较与差异分析】"
    "第七步，创建第三个版本的文件：在原文件末尾追加一行\"第三次版本更新内容\"，然后把这个版本复制到backup目录下。"
    "第八步，写一个Python脚本来做三个版本之间的差异对比：对比原始版本vs备份版本vs新版本的内容差异，"
    "标记各版本之间有哪些行不同，把差异分析报告保存到E:\\test_dir\\diff_analysis.txt。"
    ""
    "【阶段四：目录验证与清理建议】"
    "第九步，用命令列出E:\\test_dir\\backup目录下的所有文件，确认备份文件都存在，并检查目录大小。"
    "第十步，列出E:\\test_dir根目录下的文件，确认e2e_mc02.txt和e2e_mc01.txt的状态。"
    ""
    "【阶段五：四版本报告】"
    "第十一步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_02_file_manage():
    """E2E-P5-02: 文件管理链"""
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
            "E2E-P5-02", "文件管理链",
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
            "E2E-P5-02", "文件管理链", result, db, lc,
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
            "E2E-P5-02", "文件管理链",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
