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
    "然后分六个阶段完成任务："
    "第一阶段——日志清洗和解析：扫描原始日志，自动识别日志行格式，"
    "去除空行和格式异常的噪音行。按日志级别搜索：找出所有包含error的行标记为ERROR级别，"
    "所有包含warning/warn的行标记为WARNING级别，"
    "所有包含info的行标记为INFO级别，所有包含debug的行标记为DEBUG级别。"
    "第二阶段——统计分析：统计每个日志级别的出现次数、在总行数中的占比、去重统计，"
    "计算error和warning占总日志数的比例并给出严重度评分。"
    "第三阶段——时间序列分析：提取每行中的时间戳，按小时维度统计日志分布密度，"
    "识别异常峰值时段和高频错误时段。"
    "第四阶段——模式聚合分析：将相同错误/警告消息合并聚类，"
    "找出TOP5最频繁的错误和TOP5最频繁的警告。对每个高频错误分析其根因模式。"
    "第五阶段——编写日志分析脚本：基于上述分析逻辑，生成一个可复用的Python脚本"
    "log_analyzer.py保存到E:\\test_dir。该脚本应支持命令行参数："
    "-i input_file（指定输入日志文件）、-o output_dir（指定输出目录）、"
    "--level（按级别筛选）、--top（指定TOP N数量，默认5）。"
    "脚本应包含完整的函数定义和类型注解，并能独立运行输出JSON格式的分析结果。"
    "第六阶段——生成三份分析报告："
    "1) E:\\test_dir\\analysis_report+时间.txt——面向人工阅读的详细分析报告；"
    "2) E:\\test_dir\\analysis_report+时间.json——面向机器处理的JSON格式汇总数据；"
    "3) E:\\test_dir\\analysis_report_summary+时间.md——面向管理者的摘要报告。"  
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
    "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告"
)

import os
from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    verify_response_quality,
    verify_db_steps_data_completeness,
    register_pending_record, filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p1_02_log_analysis():
    """P1-02: FILE工具多任务场景- 日志分析流程"""
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
            "E2E-P1-02", "FILE多任务-日志分析",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        assert result["total_steps"] >= 2, "至少start+final(MUST)"
        assert result["unique_step_numbers"] < 300, "疑似死循环(MUST)"

        quality_issues = verify_response_quality(result)
        # 日志分析任务中回复必然包含"错误/超时/failed"等域名关键词；MUST级仅检查空/过短，
        # MAY级关键词检查在此类任务属合理内容，降为告警不阻断 — 小欧 2026-07-16
        must_issues = [i for i in quality_issues if "(MUST)" in i]
        may_issues = [i for i in quality_issues if "(MAY)" in i]
        if may_issues:
            print(f"  [QUALITY WARN] MAY级关键词(日志分析合理内容): {may_issues}")
        assert len(must_issues) == 0, f"回复质量MUST问题: {must_issues}"

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
