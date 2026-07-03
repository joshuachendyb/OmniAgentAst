"""全链路E2E集成测试 - P0-08: FILE+DATA+DOCUMENT混合通路验证

操作手册对照:
   用例: E2E-P0-08
   用户输入: 读取data.csv+统计分析+生成analysis.docx报告
   通过标准: 流正常结束；调用文件读取；DB记录完整
   失败标准: 流异常中止；DB记录不完整

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-14, 小沈 2026-07-03 rewrite
-- 更新: 2026-07-03(铁律5: 超时统一管理) 小欧
"""

TEST_CASE_ID = "E2E-P0-08"
TEST_CASE_NAME = "FILE+DATA+DOCUMENT混合通路验证"
USER_INPUT = "read E:\\test_dir\\data.csv, do full statistical analysis, generate analysis.docx professional report"

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, verify_db_prompt_consistency, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    register_pending_record,
    filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_08_file_data_document():
    """P0-08: FILE+DATA+DOCUMENT混合通路"""

    test_start = datetime.now()
    passed = False; r = {}; sid = None; db = {}; ci = []; si = []; dpi = []; lc = {"errors":[],"tracebacks":[]}; error_info = None
    user_input = USER_INPUT

    try:
        register_pending_record(
            "E2E-P0-08", "FILE+DATA+DOCUMENT混合通路(08)",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")
        result = await send_chat(user_input)
        r = result
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print(f"  [Step3-4] SSE: {result['total_steps']} events, tools: {tool_names}")

        end_type = assert_stream_ended(result)
        print(f"  流结束: {end_type}")

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, f"疑似死循环(MUST)"

        if result["has_error"]:
            print(f"  [WARN] 有Error事件(SHOULD)，流结束: {end_type}")

        assert len(result["tool_calls"]) > 0, "必须调用工具(MUST P0-08)"

        resp = result["response_text"]
        assert resp, "回复不能为空(MUST)"
        assert len(resp) > 10, f"回复太短(SHOULD): {len(resp)}"

        print(f"  [Step5] DB check...")
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert db["execution_steps_count"] >= 2, f"必须有>=2步(MUST)"
        if len(db["step_field_issues"]) > 0:
            print(f"  [WARN] step字段问题(SHOULD): {db['step_field_issues']}")

        print(f"  [Step6] SSE-DB consistency...")
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        print(f"  [Step7] Step reasonableness...")
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        print(f"  [Step8] Log check...")
        lc = check_logs(test_start, sid, result.get("user_msg_id"))
        safety_errors, other_errors = filter_safety_errors(lc["errors"])
        if safety_errors:
            print(f"  [INFO] Safety checker errors (expected): {len(safety_errors)}")
        assert len(other_errors) == 0, f"日志不应有非安全ERROR(MUST): {other_errors[:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        dpi = verify_db_prompt_consistency(sid, result.get("user_msg_id"))
        assert len(dpi) == 0, f"DB-Prompt不一致(MUST): {dpi}"

        print_report(
            "E2E-P0-08", "FILE+DATA+DOCUMENT混合通路", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "Tools": tool_names},
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
        write_test_record("E2E-P0-08", "FILE+DATA+DOCUMENT混合通路(08)", user_input, r, db, ci, si, lc, passed, r.get("total_time_ms", 0)/1000.0 if r else 0, dpi=dpi, error_info=error_info)

    if passed:
        print(f"\n  [DONE] E2E-P0-08 PASSED")
