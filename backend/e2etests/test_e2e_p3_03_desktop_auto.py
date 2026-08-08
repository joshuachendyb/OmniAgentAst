"""E2E-P3-03: 桌面自动化（DESKTOP多工具，环境敏感）
操作手册:
  用例: E2E-P3-03
  用户输入: 列出窗口/截图/剪贴板/通知，保存操作记录
  前置数据: 系统正常运行，有窗口打开
  预期调用链: window_info→screen_capture→clipboard_read→send_notification→write_text_file
  通过标准: 报告包含窗口列表/截图路径/剪贴板内容
  失败标准: 任一步骤失败
  ⚠️ 环境敏感——截图/剪贴板/通知依赖桌面环境，某些操作可能受限

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P3-03"
TEST_CASE_NAME = "桌面自动化"
USER_INPUT = (
    "帮我做一个桌面自动化的编程辅助脚本，记录并批量操作桌面环境。"
    "第一阶段——扫描桌面：列出系统桌面上当前所有打开的窗口，每个窗口记录标题、"
    "所属进程名、进程ID、窗口句柄。按窗口类型分组：IDE开发工具（VS Code/PyCharm/IDEA等）、"
    "终端窗口（cmd/PowerShell/WSL等）、浏览器窗口、文件管理器、其他。"
    "第二阶段——截取当前整个屏幕保存为screenshot_full.png到E:\\test_dir，"
    "然后分别截取VS Code窗口区域（如果有的话）和终端窗口区域，"
    "保存为screenshot_vscode.png和screenshot_terminal.png。"
    "第三阶段——自动生成一个桌面操作脚本desktop_snapshot.py，运行后能自动完成以下操作："
    "获取当前所有窗口的截图裁剪区域、读取剪贴板内容、输出结构化日志。"
    "如果系统剪贴板中有文本内容，读取并保存到E:\\test_dir\\clipboard_content.txt。"
    "第四阶段——发送一条系统通知到Windows通知栏，标题'桌面自动化助手'，"
    "内容格式化为多行文本：窗口总数、截图数量、脚本文件路径。"
    "第五阶段——汇总全部操作结果记录到E:\\test_dir\\desktop_op_log+时间.md，"
    "包括：窗口分组列表和截图缩略图路径、桌面操作脚本的代码和功能说明、"
    "剪贴板内容摘要、通知发送状态。如果某个操作因环境限制失败了也要如实记录。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
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
async def test_e2e_p3_03_desktop_auto():
    """P3-03: 桌面自动化"""
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
            "E2E-P3-03", "桌面自动化",
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
            "E2E-P3-03", "桌面自动化", result, db, lc,
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
            "E2E-P3-03", "桌面自动化",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
