"""全链路E2E集成测试 - P0-03: FILE+SHELL混合通路验证

操作手册对照:
   用例: E2E-P0-03
   用户输入: "帮我创建一个E:\test_dir\run_python.py文件，内容是print('test')，然后执行它看看输出"
   前置数据: E:\test_dir\可写；python在PATH中
   预期调用链: write_text_file->execute_shell_command(python)
   通过标准: 文件存在；执行输出包含"test"
   失败标准: 任一步骤失败

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小沈 2026-06-22
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
"""

TEST_CASE_ID = "E2E-P0-03a"
TEST_CASE_NAME = "FILE+SHELL混合通路验证"
USER_INPUT = "帮我完成以下多步骤任务：第一步，在E:\\test_dir\\目录下创建一个Python脚本文件run_python.py，脚本内容应该包含导入sys和datetime模块、获取当前系统时间、打印一条带有时间戳的测试消息、打印Python版本信息。第二步，使用python命令执行这个脚本，捕获所有输出。第三步，把执行输出的内容保存到E:\\test_dir\\script_output.txt文件中。第四步，读取这个输出文件确认内容正确完整。每一步完成都告诉我当前进展。"

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

TEST_FILE = Path("E:/test_dir/run_python.py")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_03a_file_shell():
    """P0-03a: FILE+SHELL混合通路 - 创建Python脚本并执行"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    if TEST_FILE.exists():
        TEST_FILE.unlink(missing_ok=True)

    try:
        # 提前注册待写入记录，确保中断时也能生成记录 -- 小沈 2026-07-01
        register_pending_record(
            "E2E-P0-03a", "FILE+SHELL混合通路验证(03a)",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"疑似死循环(MUST)"

        if result["has_error"]:
            pass

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-03)"

        write_tools = {"writetext"}
        has_write = any(n in write_tools for n in tool_names)
        assert has_write, f"应调用写文件工具(MUST P0-03), 实际: {tool_names}"

        shell_tools = {"shell"}
        has_shell = any(n in shell_tools for n in tool_names)
        assert has_shell, f"应调用Shell执行工具(MUST P0-03), 实际: {tool_names}"

        assert TEST_FILE.exists(), f"文件必须已创建(MUST P0-03): {TEST_FILE}"
        file_content = TEST_FILE.read_text(encoding="utf-8")
        has_print = "print(" in file_content
        has_import = "import" in file_content
        assert has_print and has_import, f"文件应包含import和print语句(MUST P0-03), content: {file_content[:200]}"

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["execution_steps_count"] >= 2, f"必须有>=2步(MUST P0-03)"

        db_tool_steps = [s for s in db["execution_steps"] if s.get("type") == "action_tool"]
        assert len(db_tool_steps) >= 2, "DB steps中必须有写文件和执行命令两步(MUST)"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB-Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-03", "FILE+SHELL混合通路验证", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names, "DbPromptIssues": len(dpi)},
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
        if TEST_FILE.exists():
            TEST_FILE.unlink(missing_ok=True)
        write_test_record("E2E-P0-03a", "FILE+SHELL混合通路验证(03a)", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)
