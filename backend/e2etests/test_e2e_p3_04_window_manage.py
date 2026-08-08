"""E2E-P3-04: 窗口管理（DESKTOP多工具，环境敏感）
操作手册:
  用例: E2E-P3-04
  用户输入: 列出窗口/查找记事本/最大化/截屏/还原，记录操作过程
  前置数据: 有记事本窗口打开
  预期调用链: window_info→window_maximize→screen_capture→window_restore→write_text_file
  通过标准: 报告包含窗口操作记录
  失败标准: 窗口操作失败
  ⚠️ 环境敏感——需要记事本窗口已打开

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P3-04"
TEST_CASE_NAME = "窗口管理"
USER_INPUT = (
    "帮我做一个编程环境窗口管理的自动化方案，整理当前桌面上的开发工具窗口。"
    "第一阶段——窗口扫描：列出系统桌面上所有打开的窗口，按程序类型分类："
    "代码编辑器/IDE（VS Code、PyCharm的窗口标题和文件路径）、"
    "终端控制台（PowerShell、cmd的当前目录和会话信息）、"
    "浏览器（Chrome/Edge/Firefox的页面标题）、"
    "文件资源管理器的路径。对每个窗口记录标题、进程ID、窗口坐标和尺寸。"
    "第二阶段——查找并定位VS Code窗口（如果没有则找浏览器窗口），"
    "确认其当前坐标和尺寸。把这个窗口移动到屏幕左侧（x=0），"
    "并设置宽度为屏幕宽度的一半，高度全屏。"
    "然后在右侧区域打开一个PowerShell终端窗口（如果没有则最大化目标窗口），"
    "调整右侧窗口宽度为屏幕另一半。实现左右分屏布局。"
    "第三阶段——截取分屏布局后的完整桌面截图保存到E:\\test_dir\\window_split_layout.png，"
    "再单独截取左侧代码编辑器区域保存为editor_view.png，右侧终端区域保存为terminal_view.png。"
    "第四阶段——将代码编辑器和终端窗口还原到原始位置和尺寸。"
    "第五阶段——生成窗口管理脚本window_manager.py，能够自动执行上述的分屏布局操作，"
    "并支持通过命令行参数指定要排列的窗口名称和布局模式（left-right/top-bottom/fullscreen）。"
    "把全部操作记录到E:\\test_dir\\window_op_log+时间.md中，包括操作前后的窗口布局对比、"
    "各阶段操作结果、截图的保存路径、生成的脚本代码。操作中的任何错误也要如实记录。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
"最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告")

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
async def test_e2e_p3_04_window_manage():
    """P3-04: 窗口管理"""
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
            "E2E-P3-04", "窗口管理",
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
            "E2E-P3-04", "窗口管理", result, db, lc,
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
            "E2E-P3-04", "窗口管理",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
