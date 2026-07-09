"""全链路E2E集成测试 - P0-04: 数据持久化通路验证

操作手册对照:
  用例: E2E-P0-04
  用户输入: "列出E:\test_dir下的所有文件"
  前置数据: E:\test_dir\目录存在且有文件(test.txt等)
  预期过程: 调用listdir，返回文件列表
  通过标准: sessions表有记录；messages表有user+assistant；execution_steps有步骤记录
  失败标准: 任一表无记录；记录不完整

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-15
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

TEST_DIR = Path("E:/test_dir")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_04_data_persistence():
    """P0-04: 数据持久化通路 - 列目录验证三张表"""

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
    user_input = "列出E:\\test_dir下的所有文件"

    try:
        register_pending_record(
            "E2E-mod-04", "数据持久化通路验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"
        assert TEST_DIR.exists(), f"测试目录不存在: {TEST_DIR}"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 300, f"疑似死循环: {result['unique_step_numbers']}步(MUST)"

        if result["has_error"]:
            pass

        # P0-04核心: 必须调用listdir
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        list_tools = {"listdir"}
        has_list = any(n in list_tools for n in tool_names)
        assert has_list, f"必须调用listdir(MUST P0-04), 实际: {tool_names}"

        # P0-04核心: 回复应包含文件名
        resp = result["response_text"]
        assert resp, "回复不能为空(MUST)"
        resp_lower = resp.lower()
        has_test_file = "test.txt" in resp_lower or "test_dir" in resp_lower
        assert has_test_file, f"回复应包含文件名(MUST P0-04), 回复: {resp[:200]}"

        db = check_db(sid)

        assert db["session_exists"], "sessions表必须有记录(MUST P0-04)"
        assert db["is_valid"], f"sessions.is_valid必须为true(MUST P0-04), got {db['is_valid']}"

        assert db["has_user_message"], "messages表必须有user消息(MUST P0-04)"
        assert db["has_assistant_message"], "messages表必须有assistant消息(MUST P0-04)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST P0-04)"

        assert db["execution_steps_count"] >= 1, (
            f"execution_steps必须有记录(MUST P0-04), 实际={db['execution_steps_count']}"
        )
        assert len(db["step_field_issues"]) == 0, (
            f"step字段不完整(MUST P0-04): {db['step_field_issues']}"
        )

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        db_list_steps = [s for s in db_tool_steps if s.get("tool_name") in list_tools]
        assert len(db_list_steps) > 0, "DB steps中应有list操作(MUST P0-04)"

        for step in db_tool_steps:
            obs = step.get("observation") or step.get("execution_result")
            assert obs, f"工具结果不能为空(MUST): {step.get('tool_name')}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, (
            f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in ci)
        )

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        lc = check_logs(test_start, sid)
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert lc["session_records_found"], "日志应有session操作记录(SHOULD)"

        print_report(
            "E2E-P0-04", "数据持久化通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={
                "LLM calls": result["llm_call_count"],
                "Tools": tool_names,
                "DB steps": db["execution_steps_count"],
                "DB tool_steps": len(db_tool_steps),
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
            "E2E-P0-04", "数据持久化通路验证",
            user_input,
            r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
