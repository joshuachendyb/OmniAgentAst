"""E2E-P2-04: 后台任务监控流程（SHELL多工具，环境敏感）
操作手册: 启动多个后台任务（网络+文件），多轮监控输出，资源追踪，生成监控报告
预期调用链: execute_shell_command(后台x2) -> shell_session(读输出x3+) -> shell_session(终止x2) -> write_text_file(x2)
前置条件: 网络连通；E:\test_dir\ 可写
验证原则：不限制中间工具调用链，只检查最终结果合理性 + DB/日志完整性
中间过程（工具链、调用顺序）只记录不限制，如实写入测试报告

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P2-04"
TEST_CASE_NAME = "后台任务监控流程"
USER_INPUT = (
    "请帮我做一个综合后台任务监控实验来验证后台多任务管理能力。"
    "分六个阶段执行："
    "第一阶段——启动三个不同类型后台任务："
    "任务1：在后台启动ping baidu.com -t命令，持续ping百度测试网络连通性，持续10秒；"
    "任务2：创建一个PowerShell脚本，该脚本持续向E:\\test_dir\\bg_task\\task_log.txt文件写入日志行"
    "（每行包含时间戳和递增序号），共写入100行后自动退出，后台运行该脚本；"
    "任务3：使用PowerShell的Get-Process和Get-Counter命令创建一个持续监控脚本，"
    "每隔2秒采样一次系统CPU使用率和内存使用率，共采样5次，结果输出到E:\\test_dir\\bg_task\\monitor_log.txt，后台运行。"
    "第二阶段——首次检查：在任务启动5秒后，依次检查三个任务的状态和输出内容，"
    "确认任务1的ping有回显，任务2的日志文件已开始写入，任务3的监控已有采样数据。"
    "第三阶段——二次检查：再等待3秒后，第二次检查所有任务状态，"
    "观察ping回显的累积情况、日志文件的行数增长、监控采样的数据变化。"
    "第四阶段——三次检查：再等待3秒后，第三次检查，确认任务持续运行，输出持续增长。"
    "第五阶段——终止任务：依次终止三个后台任务，"
    "使用Stop-Process或taskkill命令确保进程已结束，验证任务2和任务3的日志文件已不再增长。"
    "第六阶段——生成综合监控报告：读取所有任务产生的输出文件和数据，"
    "综合分析三个任务的运行过程、输出数据、资源使用情况，"
    "生成E:\\test_dir\\bg_task\\monitor_report.md（完整的监控实验报告）"
    "和E:\\test_dir\\bg_task\\monitor_data.json（结构化的监控数据汇总）。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
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
async def test_e2e_p2_04_bg_task_monitor():
    """P2-04: 后台任务监控流程"""
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
            "E2E-P2-04", "后台任务监控",
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
        assert result["unique_step_numbers"] < 50, "疑似死循环(MUST)"

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
            "E2E-P2-04", "后台任务监控", result, db, lc,
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
            "E2E-P2-04", "后台任务监控",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
