"""全链路E2E集成测试 - P0-01: 核心链路验证 - 自我介绍
严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

操作手册对照:
  用例: E2E-P0-01
   用户输入: "系统介绍自己能力范围+实际操作验证能力+写两个报告"
   前置数据: 无
   预期过程: LLM调用工具进行实际操作验证
  通过标准: 收到final事件;回复语义完整;无error事件
  失败标准: 超时未收到final;回复为空或胡言乱语;收到error

铁律:
   1. 一个用例一个脚本,写完跑通再写下一个
   2. 所有验证基于真实在里运行,禁止Mock
   3. 测试前必须重启在里服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 
-- 小健 2026-06-15
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
"""

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db, check_logs,
    print_report, write_test_record,
    assert_stream_ended, verify_consistency, verify_steps, filter_safety_errors,
    register_pending_record,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_01_introduce_self():
    """P0-01: 核心链路验证 - 详细介绍自己"""

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
    user_input = (
        "作为一名AI助手,请系统地介绍你的能力范围.请从以下几个维度详细说明:"
        "文件操作——读写,编辑,搜索文件的能力如何;"
        "代码执行——能否直接运行脚本或编译程序;"
        "网络功能——搜索,抓取网页从何做起;"
        "系统管理——查看系统资源,监控性能"
    )

    try:
        register_pending_record(
            "unit-01", "核心链路验证-自我介绍",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "在里未启动(手册6.1)"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        assert end_type == "final", f"任务必须以final正常结束(MUST), actual: {end_type}"

        # ── L2 SHOULD层: 回复语义 ──
        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["能力", "工具", "文件", "系统", "网络", "代码", "执行", "支持", "AI", "助手", "可以", "能够", "帮助"]
        assert any(t in resp for t in key_terms), "回复与自我介绍无关(SHOULD)"

        db = check_db(sid)
        # 2026-08-07 小欧: 迁移新版helperAPI(原assert_db_integrity→DB字段显式断言)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], "is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"DB步骤字段异常(MUST): {db['step_field_issues']}"

        # 2026-08-07 小欧: 原assert_data_consistency→verify_consistency+verify_steps
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        lc = check_logs(test_start, sid)
        # 2026-08-07 小欧: 原assert_log_clean→filter_safety_errors过滤断言
        _safety = filter_safety_errors(lc["errors"])
        assert len(_safety["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {_safety['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "unit-01", "核心链路验证-自我介绍", result, db, lc,
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
            "unit-01", "核心链路验证-自我介绍",
            user_input,
            r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
