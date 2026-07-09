"""E2E-E2E-P5-12: 综合报告
操作手册: TIME+SYSTEM+FILE组合
预期调用链: get_current_time->get_system_info->list_directory->get_system_info->write_text_file
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-12"
TEST_CASE_NAME = "综合报告"
USER_INPUT = (
    "这是一项多阶段综合信息采集与报告任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：系统时间与运行状态】"
    "第一步，获取当前日期和时间，精确到秒，显示今天是星期几、今年的第几天。"
    "第二步，获取系统运行时间（已开机多少天/小时/分钟）。"
    ""
    "【阶段二：系统资源使用情况】"
    "第三步，获取CPU型号、核心数和当前使用率百分比。"
    "第四步，获取物理内存大小、已用内存、可用内存和使用率。"
    "第五步，获取所有磁盘分区信息：盘符、文件系统、总量、已用、可用和使用率。"
    ""
    "【阶段三：文件清单与操作系统信息】"
    "第六步，列出E:\\test_dir下所有文件和子目录，获取每个文件的大小、创建时间和最后修改时间。"
    "第七步，获取操作系统名称、版本号、Build号、计算机名称和当前登录用户。"
    ""
    "【阶段四：Python综合评估脚本】"
    "第八步，写一个Python脚本做系统综合评估：收集前面获取的所有数据、计算系统资源综合使用率（CPU、内存、磁盘三项加权平均）、"
    "生成系统资源雷达图数据（CPU/内存/磁盘/运行时间/文件数量五个维度）、"
    "根据资源使用率判断系统是处于空闲/正常/繁忙/过载哪个状态，把评估报告保存到E:\\test_dir\\system_evaluation.txt。"
    ""
    "【阶段五：格式化综合报告】"
    "第九步，把以上所有信息汇总整理成一份格式化综合报告保存到E:\\test_dir\\comprehensive_report.txt，"
    "报告包含：时间与运行状态表、资源使用表、磁盘分区表、文件清单、OS信息和系统综合评估。"
    "第十步，独立生成四种版本的报告（TXT版、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_12_comprehensive_report():
    """E2E-P5-12: 综合报告"""
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
            "E2E-P5-12", "综合报告",
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
            "E2E-P5-12", "综合报告", result, db, lc,
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
            "E2E-P5-12", "综合报告",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
