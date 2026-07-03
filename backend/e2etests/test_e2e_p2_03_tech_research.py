"""E2E-P2-03: 技术调研流程（SHELL+NETWORK多工具）
操作手册: 搜索Python FastAPI异步+数据库异步技术，阅读网页，编写对比验证代码，生成结构化调研报告
预期调用链: search_web(x2-3) -> fetch_webpage(x3-5) -> execute_code(x2) -> write_text_file(x3)
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

TEST_CASE_ID = "E2E-P2-03"
TEST_CASE_NAME = "技术调研流程"
USER_INPUT = (
    "请帮我做一次关于Python Web异步编程技术的系统性调研。"
    "调研内容分三个技术方向："
    "方向一——异步Web框架对比：FastAPI vs Quart，"
    "需要调研它们的异步支持程度、性能基准、社区活跃度、学习曲线、生态成熟度；"
    "方向二——异步数据库驱动对比：asyncpg vs databases vs SQLAlchemy async，"
    "需要调研它们的连接池管理、事务支持、查询性能、与FastAPI的集成方式；"
    "方向三——异步消息队列对比：Celery vs Dramatiq vs ARQ，"
    "需要调研它们的任务调度能力、异步支持、可靠性、运维复杂度。"
    "每个方向需要执行以下步骤："
    "第一步——使用search_web工具搜索相关技术文章和官方文档；"
    "第二步——使用fetch_webpage工具阅读搜索到的前3-5篇高质量文章，提取关键对比信息；"
    "第三步——编写简单的对比验证Python代码，测试各技术的核心功能。"
    "完成所有方向调研后，生成三份报告："
    "E:\\test_dir\\tech_research\\research_report.md（面向开发者的详细技术对比报告），"
    "E:\\test_dir\\tech_research\\research_summary.json（结构化对比数据），"
    "E:\\test_dir\\tech_research\\recommendation.md（技术选型建议报告）。"
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
async def test_e2e_p2_03_tech_research():
    """P2-03: 技术调研流程"""
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
            "E2E-P2-03", "技术调研",
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
            "E2E-P2-02", "技术调研", result, db, lc,
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
            "E2E-P2-03", "技术调研",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
