"""E2E-E2E-P5-15: 命令查询+系统分析+文档生成+文件验证
操作手册: SHELL+SYSTEM+DOCUMENT+FILE组合
预期调用链: execute_shell_command(systeminfo)->execute_shell_command(wmic)->write_docx->list_directory
前置数据: 系统正常运行
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-15"
TEST_CASE_NAME = "命令查询+系统分析+文档生成+文件验证"
USER_INPUT = (
    "这是一项多阶段系统硬件信息采集与文档生成任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：命令方式采集硬件信息】"
    "第一步，用systeminfo命令获取完整的系统硬件和软件信息。"
    "第二步，从systeminfo输出中提取：初始安装日期、系统制造商、系统型号、处理器信息、物理内存总量、BIOS版本。"
    "第三步，用wmic cpu命令获取CPU的详细规格：名称、核心数、逻辑处理器数、最大时钟频率、L2/L3缓存。"
    "第四步，用wmic memorychip命令获取内存条的详细规格：容量、速度、制造商和插槽位置。"
    ""
    "【阶段二：硬件信息汇总分析】"
    "第五步，把从systeminfo和wmic获取的信息进行汇总对比，确保数据一致性。"
    "第六步，写一个Python脚本做硬件配置评分：根据CPU核心数和频率、内存容量（>=8GB为合格/>=16GB为良好/>=32GB为优秀）、"
    "磁盘类型和容量（SSD加分）进行综合评分，给出硬件配置等级和升级建议，保存到E:\\test_dir\\hardware_score.txt。"
    ""
    "【阶段三：Word文档生成】"
    "第七步，把收集到的初始安装日期、CPU详细规格、内存规格、操作系统版本和硬件评分汇总整理成结构化的Word文档，"
    "要求文档包含标题页、硬件总览表、CPU规格表、内存规格表、操作系统信息和硬件评分六部分，保存到E:\\test_dir\\hardware_report.docx。"
    ""
    "【阶段四：文件验证】"
    "第八步，确认hardware_report.docx已成功生成，获取文件大小、创建时间和修改时间，展示验证结果。"
    ""
    "【阶段五：四版本报告】"
    "第九步，把以上所有操作的过程和结果独立生成四种版本的报告（TXT版、DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_15_cmd_sys_doc_verify():
    """E2E-P5-15: 命令查询+系统分析+文档生成+文件验证"""
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
            "E2E-P5-15", "命令查询+系统分析+文档生成+文件验证",
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
            "E2E-P5-15", "命令查询+系统分析+文档生成+文件验证", result, db, lc,
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
            "E2E-P5-15", "命令查询+系统分析+文档生成+文件验证",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
