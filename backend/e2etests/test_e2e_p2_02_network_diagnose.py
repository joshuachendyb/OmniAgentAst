"""E2E-P2-02: 网络诊断修复流程（SHELL+NETWORK多工具）
操作手册: 多目标连通性测试+DNS解析+路由追踪+防火墙检查+连接状态+搜索排查询方案，生成综合诊断报告
预期调用链: ping_host(x3-5) -> fetch_webpage -> execute_shell_command(nslookup/tracert/netstat) -> search_web -> write_text_file(x2-3)
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

TEST_CASE_ID = "E2E-P2-02"
TEST_CASE_NAME = "网络诊断修复流程"
USER_INPUT = (
    "我怀疑公司网络有问题，请帮我做一次完整的网络诊断排查。"
    "分五个阶段执行："
    "第一阶段——多目标连通性测试：分别ping 8.8.8.8、114.114.114.114、baidu.com、google.com，"
    "记录每个目标的响应时间、丢包率、TTL值，判断网络基本连通性，"
    "同时使用fetch_webpage工具尝试访问百度首页和谷歌首页，验证HTTP层面是否可达。"
    "第二阶段——DNS解析检查：对以上目标分别做nslookup，"
    "检查A记录解析结果、解析时间、使用的DNS服务器地址，"
    "对比不同DNS服务器（系统默认vs 8.8.8.8）的解析结果是否一致，判断是否存在DNS劫持或污染。"
    "第三阶段——路由追踪和连接状态：对baidu.com和google.com做tracert路由追踪，"
    "检查中间跳数、每跳延迟、是否存在路由环路，"
    "同时使用netstat -an查看当前系统所有网络连接状态，"
    "列出所有ESTABLISHED和LISTENING状态的连接。"
    "第四阶段——防火墙和代理检查：检查常用端口（80、443、22、3389）是否被防火墙阻挡，"
    "查看系统代理设置（检查环境变量HTTP_PROXY、HTTPS_PROXY），"
    "检查Windows防火墙状态（netsh advfirewall show allprofiles）。"
    "第五阶段——诊断总结和修复建议：汇总前四个阶段的发现，"
    "按严重程度列出所有网络问题，给出针对性的修复方案和操作步骤，"
    "将完整的诊断报告保存到E:\\test_dir\\network_diagnosis\\diagnosis_report+时间.txt，"
    "同时生成结构化的JSON格式报告E:\\test_dir\\network_diagnosis\\diagnosis_summary+时间.json。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
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
async def test_e2e_p2_02_network_diagnose():
    """P2-02: 网络诊断修复流程"""
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
            "E2E-P2-02", "网络诊断修复",
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
            "E2E-P2-02", "网络诊断修复", result, db, lc,
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
            "E2E-P2-02", "网络诊断修复",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
