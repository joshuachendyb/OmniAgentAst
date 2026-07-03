"""E2E-P6-01: 文件不存在容错

操作手册:
   用例: E2E-P6-01
    用户输入: "先读取E:\\test_dir\\test.txt看看内容，然后读取E:\\test_dir\\no_such_file.txt看看有什么，对比一下两个文件的内容差异，最后把对比结果保存到E:\\test_dir\\comparison_report.txt"
   前置数据: 该文件不存在
   预期过程: 工具报错文件不存在-> Agent回复告知用户错误
   通过标准: final事件存在; 回复包含"不存在"/"找不到"/"无法"等提示; 不死循环(steps<50)
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

TEST_CASE_ID = "E2E-P6-01"
TEST_CASE_NAME = "文件不存在容错"
USER_INPUT = "先读取E:\\test_dir\\test.txt看看内容，然后读取E:\\test_dir\\no_such_file.txt看看有什么，对比一下两个文件的内容差异，最后把对比结果保存到E:\\test_dir\\comparison_report.txt"

from pathlib import Path

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

TEST_DIR = Path("E:/test_dir")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p6_01_file_not_found():
    """E2E-P6-01: 文件不存在容错"""
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
            "E2E-P6-01", "文件不存在容错",
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
        assert result["unique_step_numbers"] < 50, f"疑似死循环(MUST): {result['unique_step_numbers']}步"

        if result["has_error"]:
            print(f"  [WARN] 有Error事件(SHOULD)，流结束: {end_type}")

        resp = result.get("response_text", "")
        err_keywords = ["不存在", "找不到", "无法", "没有", "失败", "错误"]
        found = [k for k in err_keywords if k in resp]
        assert len(found) >= 1, f"回复应提示文件不存在(MUST), 实际回复前100字: {resp[:100]}"

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
            "E2E-P6-01", "文件不存在容错", result, db, lc,
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
            "E2E-P6-01", "文件不存在容错",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
