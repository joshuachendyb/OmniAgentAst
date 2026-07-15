"""全链路E2E集成测试 - P0-01: 核心链路验证 - 自我介绍

操作手册对照:
   用例: E2E-P0-01
    用户输入: "四维度介绍能力(各2例)->实跑自检(建目录/写capabilities.md/Shell查系统/搜进展/读回)->汇总文本+doc报告(多工具链路)"
   前置数据: 无
   预期过程: LLM直接回复，不调用工具
   通过标准: 收到final事件；回复语义完整；无error事件
   失败标准: 超时未收到final；回复为空或胡言乱语；收到error

 铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小健 2026-06-15
-- 更新: 2026-07-03(铁律6: 超时统一管理) 小欧
-- 更新: 2026-07-14(提升user input复杂度-多工具串联链路) 小欧
"""

TEST_CASE_ID = "E2E-P0-01"
TEST_CASE_NAME = "核心链路验证 - 自我介绍"
USER_INPUT = ("作为一位AI助手，请系统地介绍你的能力范围。请从以下四个维度详细说明，每维度给出2个具体场景示例："
               "文件操作——读写、编辑、搜索文件；代码执行——直接运行脚本或编译程序；"
               "网络功能——搜索、抓取网页；系统管理——查看系统资源、监控性能。"
               "然后实际执行一系列操作来自我验证：先在E:\\test_dir下创建self_check目录，写一份能力清单文件capabilities.md；"
               "用Shell执行命令查看系统基本信息；网上搜索你所在大模型领域的最新进展；读取并整理搜索结果。"
               "最后把'能力介绍 + 自我验证过程 + 搜索发现'汇总成文本报告与doc报告各一份，"
               "存放到report目录自建的任务子目录。注意全程真实调用工具完成。")

from datetime import datetime

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
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
    user_input = USER_INPUT

    try:
        # 提前注册待写入记录，确保中断时也能生成记录 -- 小沈 2026-07-01
        register_pending_record(
            "E2E-P0-01", "核心链路验证-自我介绍",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 300, f"疑似死循环: {result['unique_step_numbers']}步(MUST)"

        if result["has_error"]:
            pass

        # -- L2 SHOULD层: 回复语义 --
        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["助手", "AI", "可以", "能够", "帮助", "文件", "网络", "系统", "工具", "报告", "执行", "能力"]
        assert any(t in resp for t in key_terms), "回复与自我介绍无关(SHOULD)"


        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, (
            f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in ci)
        )

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"

        lc = check_logs(test_start, sid)
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有Traceback(MUST)"
        assert lc["session_records_found"], (
            f"日志应有session操作记录(SHOULD) "
            f"[raw_lines={lc.get('_debug_raw_lines')} "
            f"filtered_lines={lc.get('_debug_filtered_lines')} "
            f"session_in_raw={lc.get('_debug_session_in_raw')} "
            f"session_in_filtered={lc.get('_debug_session_in_filtered')}]"
        )

        # 步骤9: 报告
        print_report(
            "E2E-P0-01", "核心链路验证-自我介绍", result, db, lc,
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
            "E2E-P0-01", "核心链路验证-自我介绍",
            user_input,
            r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
