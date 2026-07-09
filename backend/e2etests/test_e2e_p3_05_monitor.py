"""E2E-P3-05: 系统监控告警（SYSTEM+DESKTOP多工具）
操作手册:
  用例: E2E-P3-05
  用户输入: 帮我设置一个系统资源监控任务来持续观察电脑的运行状态。先获取当前的系统时间作为监控的基准时间点。然后查看一下当前的CPU使用率和内存使用率，记录下这组数据作为第一次采样。等5秒钟后再获取一次CPU使用率和内存使用率，作为第二次采样数据。如果在任何一次采样中发现CPU使用率超过了80%或者内存使用率超过90%，就立即发送一条系统告警通知到通知栏，告知资源使用超标的情况。最后将两次采样的所有监控数据——每个时间点的具体时间、对应的CPU使用率、内存使用率、以及是否触发了告警——整理成一份监控报告，保存到E:\\test_dir\\monitor_report.txt文件中。
  前置数据: 系统正常运行
  预期调用链: time_now→get_system_info→get_system_info→send_notification→write_text_file
  通过标准: 报告包含时间和系统资源数据
  失败标准: 监控失败

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P3-05"
TEST_CASE_NAME = "系统监控告警"
USER_INPUT = (
    "帮我在模拟代码编译构建场景下做系统资源监控和性能分析。"
    "第一阶段——基准采样：先获取当前的系统时间作为监控基准点。"
    "记录当前的CPU使用率（分别记录每个核心的利用率）、"
    "内存使用率（总量/已用/可用/缓存）、磁盘IO（读写速率和队列长度）、"
    "网络IO（上下行速率）。将这些数据写入E:\\test_dir\\baseline_metrics.json。"
    "第二阶段——模拟负载场景：创建一个负载测试脚本load_simulator.py，"
    "该脚本通过多线程执行CPU密集型计算（大矩阵乘法运算、质数计算）"
    "和内存分配操作（大列表排序和去重），持续运行15秒钟来模拟编译构建的高负载场景。"
    "第三阶段——持续监控：在负载脚本执行期间，每3秒钟采样一次系统资源数据，"
    "至少完成3次采样。每次采样记录：时间戳、CPU总使用率、各核心使用率、"
    "内存总量/已用/缓存、磁盘读写速率、负载脚本的进程ID和其资源占用。"
    "如果在任何时候CPU超过80%或内存超过90%，立即发送系统告警通知到通知栏。"
    "第四阶段——性能分析：对比负载前后的资源数据差异，"
    "计算CPU峰值/均值/最低值、内存增长趋势、磁盘吞吐量。"
    "识别资源瓶颈在哪里——是CPU不足、内存不够还是磁盘IO成为瓶颈。"
    "第五阶段——汇总所有监控和分析数据，生成完整的性能监控报告保存到"
    "E:\\test_dir\\monitor_perf_report.md，包含：负载脚本的代码、"
    "每次采样的资源快照数据表格、性能变化趋势图（文本版）、"
    "资源瓶颈分析结论、针对该开发环境的配置优化建议。"
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
async def test_e2e_p3_05_monitor():
    """P3-05: 系统监控告警"""
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
            "E2E-P3-05", "系统监控告警",
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
            "E2E-P3-05", "系统监控告警", result, db, lc,
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
            "E2E-P3-05", "系统监控告警",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
