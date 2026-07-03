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
    "请帮我全面分析一下应用的数据库。"
    "首先，连接到本地的应用数据库，获取所有表的表结构信息——每个表有哪些字段、字段的数据类型、主键和外键约束，"
    "把这些信息汇总展示出来。"
    "接着，查询sessions表中最近创建的5条会话记录，显示每条记录的会话ID、创建时间和当前状态。"
    "然后，统计messages表中一共有多少条消息记录，再按照消息角色（user/assistant）分组统计各类别有多少条。"
    "最后，把以上全部分析结果——数据库表结构、sessions表最近记录、messages表统计信息——"
    "整理成一份数据库分析报告，保存到E:\\test_dir\\db_analysis.txt文件中，"
    "报告格式要清晰易读，使用分隔线和标题分层组织。"
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
            "execute_code", "pickle", "RCE", "extract", "create_task",
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
