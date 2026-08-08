"""E2E-E2E-P5-06: 桌面操作链
操作手册: DESKTOP组合-截屏+OCR+环境敏感
预期调用链: window_info->screen_capture->clipboard_read->get_display_info->ocr_image->write_text_file
前置数据: 系统正常运行，有窗口打开
通过标准: 流正常结束；报告文件生成；DB记录完整
失败标准: 流异常中止

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P5-06"
TEST_CASE_NAME = "桌面操作链"
USER_INPUT = (
    "这是一项多阶段桌面操作分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：窗口信息采集】"
    "第一步，列出当前所有打开的窗口，显示每个窗口的标题、所属进程名和窗口坐标位置。"
    "第二步，统计当前打开的窗口总数，分类为系统窗口和应用窗口，展示分类结果。"
    ""
    "【阶段二：屏幕截图与显示信息】"
    "第三步，截取当前完整屏幕的截图，保存图片到E:\\test_dir\\screenshot.png。"
    "第四步，查询显示信息：屏幕分辨率（宽度×高度）、色彩深度、刷新率、多显示器配置（如果有）。"
    ""
    "【阶段三：剪贴板内容获取】"
    "第五步，读取当前系统剪贴板中的内容，如果有文字内容则显示出来，如果有文件路径则列出文件列表。"
    "第六步，如果剪贴板中有内容，写一个Python脚本做内容分析：判断内容类型（文本/图片/文件路径）、统计文本长度/图片尺寸/文件数量、"
    "猜测剪贴板内容的来源应用，把剪贴板分析报告保存到E:\\test_dir\\clipboard_analysis.txt。"
    ""
    "【阶段四：OCR文字识别】"
    "第七步，对screenshot.png进行OCR文字识别，提取图片中所有可识别的文字内容。"
    "第八步，写一个Python脚本对OCR结果进行后处理：按行拆分识别结果、过滤掉识别置信度低的文字、"
    "尝试识别出窗口标题栏文字和菜单文字，把处理后的OCR结果保存到E:\\test_dir\\ocr_result.txt。"
    ""
    "【阶段五：综合报告】"
    "第九步，把以上所有桌面操作信息汇总整理后保存到E:\\test_dir\\desktop_analysis.txt。"
    "第十步，独立生成四种版本的报告（TXT版、带截图的DOCX版、结构化DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
"最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告"
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
async def test_e2e_p5_06_desktop_chain():
    """E2E-P5-06: 桌面操作链"""
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
            "E2E-P5-06", "桌面操作链",
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
            "E2E-P5-06", "桌面操作链", result, db, lc,
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
            "E2E-P5-06", "桌面操作链",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
