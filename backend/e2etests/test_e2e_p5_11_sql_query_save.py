"""E2E-E2E-P5-11: SQL结果存文件
操作手册: DATAANALYSIS+FILE组合
预期调用链: get_db_schema->query_sql(sessions)->query_sql(messages)->write_text_file
前置数据: chat_history.db存在于用户目录且有数据
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-11"
TEST_CASE_NAME = "SQL结果存文件"
USER_INPUT = (
    "这是一项多阶段数据库查询与分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：数据库结构探索】"
    "第一步，连接到应用数据库chat_history.db，获取所有表的列表，显示表名和每张表的记录数。"
    "第二步，获取sessions表的完整结构：所有字段名、数据类型、是否允许NULL、主键信息。"
    "第三步，获取messages表的完整结构同样展示。"
    ""
    "【阶段二：会话数据查询】"
    "第四步，查询sessions表中最近10条会话记录，显示会话ID、创建时间、更新时间、会话状态。"
    "第五步，查询sessions表按创建日期统计每天的会话数量，显示最近7天的会话分布。"
    ""
    "【阶段三：消息数据统计】"
    "第六步，查询messages表的总记录数。"
    "第七步，按角色（user/assistant）分组统计消息数量和占比。"
    "第八步，按会话ID分组统计每个会话的消息数量，找出消息最多的前5个会话和最少的5个会话。"
    ""
    "【阶段四：Python交叉分析】"
    "第九步，写一个Python脚本做会话与消息的交叉分析：对每个会话计算其持续时长（从创建到最后一条消息的时间差）、"
    "平均每会话的消息数、消息频率（条/天/会话），分析会话时长与消息数量的相关性，"
    "找出活跃度最高的会话特征，把交叉分析报告保存到E:\\test_dir\\db_cross_analysis.txt。"
    ""
    "【阶段五：综合报告】"
    "第十步，把所有查询结果和分析内容汇总保存到E:\\test_dir\\db_query_report.txt，"
    "报告包含：数据库结构总览、会话列表和分布、消息统计、交叉分析和结论。"
    "第十一步，独立生成四种版本的报告（TXT版、DOCX表格版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p5_11_sql_query_save():
    """E2E-P5-11: SQL结果存文件"""
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
            "E2E-P5-11", "SQL结果存文件",
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
            "E2E-P5-11", "SQL结果存文件", result, db, lc,
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
            "E2E-P5-11", "SQL结果存文件",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
