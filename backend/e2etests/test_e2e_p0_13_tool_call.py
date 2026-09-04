"""全链路E2E集成测试 - P0-13: 工具调用通路验证 (模板拷贝)

操作手册对照:
   用例: E2E-P0-13
    用户输入: "创建e2e_test_p0.txt(hello)->读取校验->Shell查属性->汇总report.md(多工具链路)"
   预期过程: Agent调用write_text_file，返回成功
   通过标准: SSE包含action事件；DB有execution_steps记录；文件存在且内容正确
   失败标准: 未调用工具；文件未创建；DB无记录

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-15, 小欧 2026-06-30 renumber
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
-- 更新: 2026-07-14(提升user input复杂度-多工具串联链路) 小欧
-- 更新: 2026-08-22 - 小欧 - §10.3适配: 本case旧action_tool取数块(type过滤+顶层tool_name+observation字段)收敛为verify_db_tool_usage单点校验(e2e_helpers FUNCTIONS.md九.1), 协议再变只改helper一处
"""

TEST_CASE_ID = "E2E-P0-13"
TEST_CASE_NAME = "工具调用通路验证"
USER_INPUT = ("请在E盘根目录创建一个名为e2e_test_p0.txt的文件，文件内容写入hello。"
               "创建完成后读取该文件验证内容是否准确写入，再用Shell执行一条命令查看该文件的属性"
               "（大小与最后修改时间），最后把'创建—读取校验—属性查看'的完整操作过程与结果"
               "汇总写入E:\\test_dir\\e2e_test_p0_report.md。所有步骤必须真实执行并相互对照验证。"
               "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告")

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    cleanup, print_report, write_test_record,
    assert_stream_ended,
    register_pending_record,
    verify_db_tool_usage,
)

TEST_FILE = Path("E:/e2e_test_p0.txt")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_13_tool_call():
    """P0-13: 工具调用通路验证 - 创建文件"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    if TEST_FILE.exists():
        TEST_FILE.unlink(missing_ok=True)

    try:
        register_pending_record(
            "E2E-P0-13", "工具调用通路验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {[t['tool_name'] for t in result['tool_calls']]}")

        # L1 流结束验证
        end_type = assert_stream_ended(result)
        print(f"  流结束: {end_type}")

        # L1 MUST层
        assert result["total_steps"] >= 2, f"至少start+final(MUST)"

        # L2 SHOULD WARN
        if result["has_error"]:
            print(f"  [WARN] 有error事件(SHOULD)，流结束: {end_type}")

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-13)"
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        write_tools = {"writetext"}
        has_write = any(n in write_tools for n in tool_names)
        assert has_write, f"应调用写文件工具(MUST P0-13), 实际: {tool_names}"

        print(f"  [Step5] File check...")
        assert TEST_FILE.exists(), f"文件必须已创建(MUST P0-13): {TEST_FILE}"
        file_content = TEST_FILE.read_text(encoding="utf-8")
        assert "hello" in file_content.lower(), f"文件内容应含'hello'(MUST P0-13)"

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["execution_steps_count"] > 0, f"必须有execution_steps(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"

        # 2026-08-22 小欧 §10.3适配: 旧action_tool取数块收敛为verify_db_tool_usage单点校验(FUNCTIONS.md 9.1)
        _ti = verify_db_tool_usage(db)
        assert len(_ti) == 0, f"DB steps中必须有action步骤(MUST): {_ti}"

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert lc["session_records_found"], (
            f"日志应有session操作记录(SHOULD) "
            f"[raw_lines={lc.get('_debug_raw_lines')} "
            f"filtered_lines={lc.get('_debug_filtered_lines')} "
            f"session_in_raw={lc.get('_debug_session_in_raw')} "
            f"session_in_filtered={lc.get('_debug_session_in_filtered')}]"
        )
        if not lc["sse_records_found"]:
            print("  [WARN] 日志未找到SSE事件记录(SHOULD, non-blocking)")

        print(f"  [Step8b] DB-Prompt consistency...")
        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB->Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-13", "工具调用通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "File": str(TEST_FILE), "DbPromptIssues": len(dpi)},
        )

        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"  [FAIL] 异常: {error_info[:500]}")
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        if TEST_FILE.exists():
            TEST_FILE.unlink(missing_ok=True)
        write_test_record("E2E-P0-13", "工具调用通路验证", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)

    if passed:
        print(f"\n  [DONE] E2E-P0-13 PASSED")
