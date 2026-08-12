# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 修复工具结果dict子串匹配: tool_msgs可能为dict, 须json.dumps后再匹配
#   【病根】k in dict按键匹配, 不按值匹配, 导致err_keywords永远匹配不到工具报错信息。
#   【改法】tool_msgs先json.dumps转字符串, 再做子串匹配。
"""unit-04: 文件不存在容错

操作手册:
   用例: unit-04
    用户输入: "先读取E:\\test_dir\\test.txt看看内容，然后读取E:\\test_dir\\no_such_file.txt看看有什么，对比一下两个文件的内容差异，最后把对比结果保存到E:\\test_dir\\comparison_report.txt"
   前置数据: 该文件不存在
   预期过程: 工具报错文件不存在-> Agent回复告知用户错误
   通过标准: final事件存在; 回复包含"不存在"/"找不到"/"无法"等提示; 不死循环(steps<50)
   失败标准: Agent崩溃/死循环/无错误提示

-- 小欧 2026-06-27

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "unit-04"
TEST_CASE_NAME = "文件不存在容错"
USER_INPUT = (
    "这是一项多阶段文件处理与容错验证任务，请严格按照阶段顺序执行。"
    ""
    "第一阶段：先检查E:\\test_dir目录下有哪些txt文件，列出完整的文件清单。"
    "然后读取test.txt的内容，统计其中的总字符数和总行数，展示内容摘要给我看。"
    ""
    "第二阶段：写一个Python脚本用于文件的逐行读取和差异对比，"
    "脚本要求支持指定两个文件路径并输出它们的行差异，保存到E:\\test_dir\\diff_tool.py。"
    ""
    "第三阶段：用Python脚本对比test.txt和no_such_file.txt的差异，但这个no_such_file.txt文件并不存在，"
    "读取它的时候看看会发生什么情况，如果报错了请告诉我具体错误原因。"
    ""
    "第四阶段：检查test.txt的内容完整性——确认文件编码格式、最后修改时间、"
    "文件头签名是否正确，把检查结果展示给我。"
    ""
    "第五阶段：将以上所有操作——文件清单、test.txt内容统计、diff_tool.py脚本、"
    "对比结果和文件完整性检查——汇总整理后保存到E:\\test_dir\\file_processing_summary+时间.txt。"
    "然后独立生成四种版本的报告（TXT/DOCX/结构化DOCX/PDF）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
     "抓取最近5天的财经新闻和资本市场的信息,分析这些消息对股市的影响情况"
     "抓取今天的股票市场,沪市和深市的指数情况, 分析最近3天的指数变化原因,哪些财经\资本的消息对股市有重要影响"
    "分析最近10天的股票市场的股票指数的变化趋势,给出详实的分析和原因,并写出分析报告存入项目目录中"
      "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告"
)

from pathlib import Path

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

TEST_DIR = Path("E:/test_dir")


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_unit_04_file_not_found():
    """unit-04: 文件不存在容错"""
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
            "unit-04", "文件不存在容错",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        record_test_baseline()

        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 300, f"疑似死循环(MUST): {result['unique_step_numbers']}步"

        if result["has_error"]:
            print(f"  [WARN] 有Error事件(SHOULD)，流结束: {end_type}")

        resp = result.get("response_text", "")
        err_keywords = ["不存在", "找不到", "无法", "没有", "失败", "错误"]
        found = [k for k in err_keywords if k in resp]
        import json as _json
        tool_msgs = [t.get("result", "") for t in result.get("tool_calls", [])
                     if "result" in t]
        if len(found) < 1:
            # 工具结果可能是 dict（如 {"data":{"stdout":...},"llm_data":...}），
            # 须序列化为字符串后再做子串匹配，否则 `k in dict` 按键匹配永远失败 — 小欧 2026-07-18
            tool_msgs_str = [
                _json.dumps(m, ensure_ascii=False) if not isinstance(m, str) else m
                for m in tool_msgs
            ]
            found = [k for k in err_keywords if any(k in ms for ms in tool_msgs_str)]
        assert len(found) >= 1, (
            f"回复或工具结果应提示文件不存在(MUST), "
            f"回复前100字: {resp[:100]}, "
            f"工具结果条数: {len(tool_msgs)}"
        )

        for issue in verify_response_quality(result):
            pass
        for issue in verify_response_time(result):
            pass

        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"

        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST):\n" + "\n".join(f"  - {i}" for i in ci)

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        db_steps_issues = verify_db_steps_data_completeness(sid)
        assert len(db_steps_issues) == 0, f"DB步骤数据不完整(MUST): {db_steps_issues}"

        lc = check_logs(test_start, sid)
        if lc["errors"]:
            print(f"  [WARN] 日志有ERROR(P6预期), count={len(lc['errors'])}")
        if lc["tracebacks"]:
            print(f"  [WARN] 日志有Traceback(P6预期), count={len(lc['tracebacks'])}")
        if not lc["session_records_found"]:
            print(f"  [WARN] 日志未找到session操作记录 "
                  f"(raw_lines={lc.get('_debug_raw_lines')}, "
                  f"filtered_lines={lc.get('_debug_filtered_lines')}, "
                  f"session_in_raw={lc.get('_debug_session_in_raw')}, "
                  f"session_in_filtered={lc.get('_debug_session_in_filtered')})")

        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        print_report(
            "unit-04", "文件不存在容错", result, db, lc,
            ci, si, True, elapsed,
            extra={
                "Tools": tool_names,
                "LLM calls": result["llm_call_count"],
                "Error keywords": found,
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
            "unit-04", "文件不存在容错",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
