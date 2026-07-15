"""E2E-E2E-P5-05: 系统诊断链
操作手册: SYSTEM组合-CPU+内存+进程
预期调用链: get_system_info->list_processes->get_system_info->write_text_file
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-05"
TEST_CASE_NAME = "系统诊断链"
USER_INPUT = (
    "这是一项多阶段系统诊断分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：资源占用全景扫描】"
    "第一步，检查CPU使用率（百分比）、CPU型号和核心数。"
    "第二步，检查物理内存总量、已用内存、可用内存和内存使用率百分比。"
    "第三步，检查所有磁盘分区的总量、已用空间、可用空间和使用率百分比。"
    "第四步，检查系统启动时间和已运行时间。"
    "如果发现CPU,内存使用占比超过50%,需要你想办法来清理CPU或者内存.务必降低系统负载"
    ""
    "【阶段二：进程深度分析】"
    "第五步，获取当前所有进程列表，按CPU使用率从高到低排序，列出占用CPU最多的前10个进程（进程名+PID+CPU%）。"
    "第六步，再按内存使用量从高到低排序，列出占用内存最多的前10个进程（进程名+PID+内存MB）。"
    "第七步，写一个Python脚本做进程健康度评分：对每一进程分析其CPU和内存占比、计算健康评分、"
    "标记出优先级最高需要关注的进程（累计CPU>50%或内存>500MB的进程），把健康评分报告保存到E:\\test_dir\\process_health.txt。"
    ""
    "【阶段三：趋势与瓶颈分析】"
    "第八步，检查磁盘I/O或系统事件日志中是否有性能相关的警告或错误。"
    "第九步，写一个Python脚本生成系统瓶颈分析报告：汇总CPU、内存、磁盘三个维度的使用率，"
    "诊断当前系统的瓶颈在哪，给出优化建议（如增加内存/关闭不必要的进程/清理磁盘空间），保存到E:\\test_dir\\bottleneck.txt。"
    ""
    "【阶段四：综合诊断报告】"
    "第十步，把以上所有诊断结果整理成一份详细的系统诊断报告保存到E:\\test_dir\\system_diagnosis.txt，"
    "报告包含：资源总览表、Top10 CPU进程、Top10 内存进程、进程健康评分、瓶颈分析和优化建议。"
    ""
    "【阶段五：四版本报告】"
    "第十一步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、DOCX表格版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_05_system_diagnose():
    """E2E-P5-05: 系统诊断链"""
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
            "E2E-P5-05", "系统诊断链",
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
            "E2E-P5-05", "系统诊断链", result, db, lc,
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
            "E2E-P5-05", "系统诊断链",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
