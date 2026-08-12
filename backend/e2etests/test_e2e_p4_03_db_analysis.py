"""E2E-P4-03: 数据库分析（DATA多工具）
操作手册:
  用例: E2E-P4-03
  用户输入: 读schema→查sessions→查messages→写报告
  前置数据: chat_history.db存在于用户目录且有数据
  预期调用链: get_db_schema→query_sql(sessions)→query_sql(messages)→write_text_file→list_directory
  通过标准: 报告包含表结构和查询结果
  失败标准: 报告未生成或内容不完整

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P4-03"
TEST_CASE_NAME = "数据库分析"
USER_INPUT = (
    "这是一项多阶段数据库分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：数据库结构探索】"
    "第一步，连接到应用的数据库chat_history.db，获取所有表的列表，展示数据库中共有几张表、表名和每张表的记录数。"
    "第二步，对每张表逐一获取表结构——字段名、数据类型、是否为主键、是否为外键，把完整的数据库模式（schema）整理展示。"
    "第三步，写一个Python脚本来分析表之间的关联关系：识别哪些字段是外键、对应的主表和关联字段是什么，绘制表之间的关联图描述，保存到E:\\test_dir\\db_relations.txt。"
    ""
    "【阶段二：会话数据深度分析】"
    "第四步，查询sessions表中最近10条会话记录，展示每条记录的会话ID、创建时间和当前状态。"
    "第五步，写一个Python脚本做会话时间分析：计算每条会话从创建到最新消息的持续时间、"
    "找出持续时间最长的会话和最短的会话、统计每天的会话创建数量分布，把分析结果保存到E:\\test_dir\\session_analysis.txt。"
    ""
    "【阶段三：消息数据统计】"
    "第六步，查询messages表中消息总数，按角色（user/assistant）分组统计消息数量和占比。"
    "第七步，按会话ID分组统计每个会话中的消息数量，找出消息最多的前5个会话，"
    "计算消息的平均长度和最大长度，把统计结果保存到E:\\test_dir\\message_stats.txt。"
    "第八步，写一个Python脚本分析消息的时间模式：统计一天中每个小时的消息分布（0-23时），找出消息最活跃的时间段，保存到E:\\test_dir\\hourly_trend.txt。"
    ""
    "【阶段四：交叉分析与报告】"
    "第九步，综合会话和消息数据做交叉分析：计算每个会话的平均消息数、最长会话的消息数、消息频率（条/天），找出高频会话和低频会话的特征差异。"
    "第十步，把所有分析结果汇总成数据库分析报告保存到E:\\test_dir\\db_analysis+时间.txt。"
    "第十一步，独立生成四种版本的报告（TXT版本、带表格的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p4_03_db_analysis():
    """P4-03: 数据库分析"""
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
            "E2E-P4-03", "数据库分析",
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
            "E2E-P4-03", "数据库分析", result, db, lc,
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
            "E2E-P4-03", "数据库分析",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
