"""全链路E2E集成测试 - P1-02: FILE工具多任务场景- 日志分析流程

操作手册对照:
   用例: E2E-P1-02
   用户输入: 对E:\test_dir\test.txt文件进行一次完整的日志内容分析。先读取文件全部内容了解总体情况。然后分四个维度进行分析：按日志级别搜索（error/warning/info/debug）；统计每个级别的出现次数、占比和去重统计；时间序列分析；模式聚合分析。完成后生成三份报告：txt、json、md格式。

-- 小健 2026-06-24, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P1-02"
TEST_CASE_NAME = "FILE工具多任务场景- 日志分析流程"
USER_INPUT = (
    "请对E:\\test_dir\\test.txt文件进行一次完整的日志内容分析。"
    "先读取文件全部内容了解总体情况。"
    "然后分四个维度进行分析："
    "第一维度——按日志级别搜索，找出所有包含error的行标记为ERROR级别，"
    "所有包含warning/warn的行标记为WARNING级别，"
    "所有包含info的行标记为INFO级别，所有包含debug的行标记为DEBUG级别；"
    "第二维度——统计每个日志级别的出现次数、在总行数中的占比、去重统计，"
    "计算error和warning占总日志数的比例并给出严重度评分；"
    "第三维度——时间序列分析，提取每行中的时间戳，按小时维度统计日志分布密度；"
    "第四维度——模式聚合分析，将相同错误/警告消息合并聚类，"
    "找出TOP5最频繁的错误和TOP5最频繁的警告。"
    "完成上述四维分析后，生成三份报告："
    "1) E:\\test_dir\\analysis_report.txt——面向人工阅读的详细分析报告；"
    "2) E:\\test_dir\\analysis_report.json——面向机器处理的JSON格式汇总数据；"
    "3) E:\\test_dir\\analysis_report_summary.md——面向管理者的摘要报告。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
)

import os
import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, record_test_baseline,
    verify_response_quality, verify_response_time,
    verify_db_steps_data_completeness,
    register_pending_record, filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p1_02_log_analysis():
    """P1-02: FILE工具多任务场景- 日志分析流程"""
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
    baseline = {}

    try:
        register_pending_record(
            "E2E-P1-02", "FILE多任务-日志分析",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"
        baseline = record_test_baseline()

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
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "E2E-P1-02", "FILE多任务-日志分析", result, db, lc,
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
            "E2E-P1-02", "FILE多任务-日志分析",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
