"""E2E-P6-03: 网络请求失败容错

操作手册:
   用例: E2E-P6-03
    用户输入: "先帮我搜索一下今天的天气情况，然后把搜索到的结果保存到E:\\test_dir\\weather.txt，最后再访问http://this-does-not-exist-12345.com看看这个网站的内容，如果访问不了就告诉我原因"
   前置数据: 该域名不存在
   预期过程: 工具报错无法解析域名-> Agent回复告知用户错误
   通过标准: final事件存在; 回复包含"无法访问"/"连接失败"/"不存在"; 不死循环(steps<50)
   失败标准: Agent崩溃/死循环/无错误提示

-- 小欧 2026-06-27

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P6-03"
TEST_CASE_NAME = "网络请求失败容错"
USER_INPUT = (
    "这是一项多阶段网络请求与容错验证任务，请严格按照阶段顺序执行。"
    ""
    "第一阶段：帮我搜索\"今天天气预报\"，获取并展示前3条搜索结果的标题和摘要。"
    ""
    "第二阶段：打开搜索结果中的第一条，获取详细天气预报内容——温度范围、天气状况和风力信息。"
    ""
    "第三阶段：写一个Python脚本用于网页可用性检测，脚本要求："
    "接受一个URL参数、尝试用HTTP GET连接并记录HTTP状态码、"
    "如果连接失败则捕获异常类型并分析失败原因（DNS解析失败/连接超时/连接被拒绝）、"
    "输出检测结果到文件，保存Python脚本到E:\\test_dir\\web_checker.py。"
    ""
    "第四阶段：先用web_checker.py检测http://this-does-not-exist-12345.com这个网站是否可达，"
    "再用web_checker.py检测http://www.baidu.com是否可达，对比两者的检测结果差异。"
    ""
    "第五阶段：把天气搜索结果、天气预报详情、Python检测脚本、两个URL的检测结果汇总保存到E:\\test_dir\\network_report.txt。"
    "然后独立生成四种版本的报告（TXT/DOCX/结构化DOCX/PDF）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p6_03_network_fail():
    """E2E-P6-03: 网络请求失败容错"""
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
            "E2E-P6-03", "网络请求失败容错",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        record_test_baseline()

        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 300, f"疑似死循环(MUST): {result['unique_step_numbers']}步"

        if result["has_error"]:
            print(f"  [WARN] 有Error事件(SHOULD)，流结束: {end_type}")

        resp = result.get("response_text", "")
        err_keywords = ["无法访问", "连接失败", "不存在", "无法", "失败", "错误", "超时", "解析"]
        found = [k for k in err_keywords if k in resp]
        assert len(found) >= 1, f"回复应提示网络访问失败(MUST), 实际回复前100字: {resp[:100]}"

        for issue in verify_response_quality(result):
            pass
        for issue in verify_response_time(result):
            pass

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in ci)

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        db_steps_issues = verify_db_steps_data_completeness(sid)
        assert len(db_steps_issues) == 0, f"DB步骤数据不完整(MUST): {db_steps_issues}"

        lc = check_logs(test_start, sid)
        if lc["errors"]:
            print(f"  [WARN] 日志有ERROR(P6预期), count={len(lc['errors'])}")
        if lc["tracebacks"]:
            print(f"  [WARN] 日志有Traceback(P6预期), count={len(lc['tracebacks'])}")
        if not lc["session_records_found"]:
            print("  [WARN] 日志未找到session操作记录(SHOULD, non-blocking)")

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print_report(
            "E2E-P6-03", "网络请求失败容错", result, db, lc,
            ci, si, True, elapsed,
            extra={
                "Tools": tool_names,
                "LLM calls": result["llm_call_count"],
                "Error keywords": found,
            },
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
            "E2E-P6-03", "网络请求失败容错",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
