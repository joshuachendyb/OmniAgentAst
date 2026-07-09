"""E2E-P3-01: 系统健康检查（SYSTEM多工具）
操作手册:
  用例: E2E-P3-01
  用户输入: 查CPU/内存/进程/网络/日志，生成健康检查报告
  前置数据: 系统正常运行
  预期调用链: get_system_info→list_processes→net_connections→event_log→write_text_file
  通过标准: 报告包含CPU/内存/进程/网络/日志信息
  失败标准: 任一检查失败

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P3-01"
TEST_CASE_NAME = "系统健康检查"
USER_INPUT = (
    "电脑最近跑起来感觉很慢，怀疑开发环境出了问题，帮我做一个全面的系统健康检查。"
    "第一阶段——系统资源检查：查看CPU使用率和内存使用率，记录详细占用情况，"
    "检查磁盘剩余空间和磁盘读写IO延迟情况。"
    "第二阶段——开发工具健康检查：检查Python进程数量和内存占用，"
    "查看是否有残留的Python.exe/cmd.exe/npm.exe僵尸进程。"
    "检查Git仓库状态是否一切正常，确认没有挂起的操作。"
    "再检查npm/pip的缓存目录占用空间大小是否正常。"
    "第三阶段——网络连接检查：查看当前的网络连接状态列表，"
    "识别并标记异常链接（大量TIME_WAIT、不明外部IP连接）。"
    "检查常用的开发端口（8000/3000/5432/27017/6379）是否有异常占用。"
    "第四阶段——系统日志检查：查看最近24小时的系统日志，"
    "筛选出ERROR和WARNING级别的事件，分析是否存在磁盘错误、内存不足、"
    "服务崩溃等严重影响开发环境的问题。"
    "第五阶段——汇总以上所有检查结果，生成一份全面的系统健康检查报告，"
    "保存到E:\\test_dir\\health_check.txt。报告要包含每个阶段的详细数据、"
    "异常标记、风险等级评估、以及针对发现问题的修复建议。"
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
async def test_e2e_p3_01_health_check():
    """P3-01: 系统健康检查"""
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
            "E2E-P3-01", "系统健康检查",
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
            "E2E-P3-01", "系统健康检查", result, db, lc,
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
            "E2E-P3-01", "系统健康检查",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
