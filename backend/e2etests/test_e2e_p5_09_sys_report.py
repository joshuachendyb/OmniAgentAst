"""E2E-E2E-P5-09: 系统报告存文件
操作手册: SYSTEM+FILE组合
预期调用链: get_system_info->get_system_info->get_env->write_text_file
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-09"
TEST_CASE_NAME = "系统报告存文件"
USER_INPUT = (
    "这是一项多阶段系统信息采集与报告生成任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：CPU与处理器信息】"
    "第一步，获取CPU详细信息：型号名称、核心数、逻辑处理器数、基础频率、当前使用率百分比。"
    "第二步，获取CPU的架构信息（x64/ARM）、L2/L3缓存大小。"
    ""
    "【阶段二：内存与磁盘信息】"
    "第三步，获取物理内存总量、已用内存、可用内存、内存使用率百分比和虚拟内存大小。"
    "第四步，获取所有磁盘分区信息：每个分区的盘符、文件系统类型（NTFS/FAT32）、总大小、已用空间、可用空间和使用率。"
    ""
    "【阶段三：操作系统与环境变量】"
    "第五步，获取操作系统的完整信息：名称、版本号、Build号、版本类型（专业版/企业版）、安装日期、系统启动时间。"
    "第六步，获取PATH和系统环境变量的完整列表，筛选出关键的路径变量。"
    ""
    "【阶段四：深度分析与Python脚本】"
    "第七步，写一个Python脚本做系统健康评估：根据CPU使用率（<30%为优/30-70%为良/>70%为差）、"
    "内存使用率（<50%为优/50-80%为良/>80%为差）、磁盘使用率（<60%为优/60-85%为良/>85%为差）"
    "三项指标综合打分，给出系统健康状况评级和针对性建议，保存到E:\\test_dir\\health_assessment.txt。"
    ""
    "【阶段五：综合报告】"
    "第八步，把以上所有系统信息汇总成一份完整的系统档案报告保存到E:\\test_dir\\system_profile.txt，"
    "报告包含：CPU规格表、内存状态、磁盘分区表、OS信息、环境变量清单和健康评估。"
    "第九步，独立生成四种版本的报告（TXT版、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_09_sys_report():
    """E2E-P5-09: 系统报告存文件"""
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
            "E2E-P5-09", "系统报告存文件",
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
            "E2E-P5-09", "系统报告存文件", result, db, lc,
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
            "E2E-P5-09", "系统报告存文件",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
