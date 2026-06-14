"""全链路E2E集成测试 - P0-01: 核心链路验证 - 自我介绍

操作手册对照:
  用例: E2E-P0-01
  用户输入: "详细介绍一下你自己，你能做什么"
  预期过程: LLM直接回复，不调用工具
  通过标准: 收到final事件；回复语义完整；无error事件
  失败标准: 超时未收到final；回复为空或胡言乱语；收到error

铁律:
  1. 一个用例一个脚本，写完跑通再写下一个
  2. 所有验证基于真实后端运行，禁止Mock
  3. 测试前必须重启后端服务(手册6.1)
  4. 禁止在测试代码中使用emoji字符

-- 小健 2026-06-14
"""

from datetime import datetime

import pytest
from e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    cleanup, print_report,
    get_security_enabled, set_security_enabled,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_01_introduce_self():
    """P0-01: 核心链路验证 - 详细介绍自己"""

    test_start = datetime.now()

    # ── 安全配置: 保存+关闭 ──
    orig_security = get_security_enabled()
    set_security_enabled(False)

    try:
        # 步骤1: 检查后端就绪
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        user_input = "详细介绍一下你自己，你能做什么"
        print(f"\n  [Step1] T0={test_start.strftime('%H:%M:%S')}, input: {user_input}")

        # 步骤2-3: 发送请求+接收SSE
        result = await send_chat(user_input)
        session_id = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0

        print(f"  [Step3-4] SSE: {result['total_steps']} events, {result['logical_step_count']} logical")

        # ── L1 MUST层 ──
        assert not result["has_error"], "不应有error事件(MUST)"
        assert result["final_event"] is not None, "必须收到final事件(MUST)"
        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 50, f"疑似死循环: {result['unique_step_numbers']}步(MUST)"

        # ── L2 SHOULD层: 回复语义 ──
        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["助手", "AI", "可以", "能够", "帮助"]
        assert any(t in resp for t in key_terms), "回复与自我介绍无关(SHOULD)"

        # 步骤5: DB记录完整性
        print(f"  [Step5] DB check...")
        db = check_db(session_id)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"

        # 步骤6: SSE vs DB一致性
        print(f"  [Step6] SSE-DB consistency...")
        consistency_issues = verify_consistency(result, session_id)
        assert len(consistency_issues) == 0, (
            f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in consistency_issues)
        )

        # 步骤7: 步骤合理性
        print(f"  [Step7] Step reasonableness...")
        step_issues = verify_steps(result, session_id)
        # P0-01无工具调用, step_issues应为空
        assert len(step_issues) == 0, f"步骤合理性异常: {step_issues}"

        # 步骤8: 日志检查
        print(f"  [Step8] Log check...")
        log_check = check_logs(test_start, session_id)
        assert len(log_check["errors"]) == 0, f"日志不应有ERROR(MUST): {log_check['errors'][:3]}"
        assert len(log_check["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert log_check["session_records_found"], "日志应有session操作记录(SHOULD)"
        if not log_check["sse_records_found"]:
            print("  [WARN] 日志未找到SSE事件记录(SHOULD, non-blocking)")

        # 步骤9: 报告+清理
        print_report(
            "E2E-P0-01", "核心链路验证-自我介绍", result, db, log_check,
            consistency_issues, step_issues, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
        )

        print(f"  [Step9] Cleanup...")

    finally:
        # 步骤9: 恢复security.enabled
        if orig_security is not None:
            set_security_enabled(orig_security)
        cleanup()

    print(f"\n  [DONE] E2E-P0-01 PASSED")
