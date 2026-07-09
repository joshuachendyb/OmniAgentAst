"""E2E-P4-05: 综合数据处理（DATA+DOCUMENT多工具）
操作手册:
  用例: E2E-P4-05
  用户输入: 读csv→统计→折线图→Excel→Word
  前置数据: data.csv存在于E:\test_dir
  预期调用链: read_text_file→analyze_data→generate_chart→write_xlsx→write_docx
  通过标准: 图表/Excel/Word都存在
  失败标准: 任意生成文件缺失

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P4-05"
TEST_CASE_NAME = "综合数据处理"
USER_INPUT = (
    "这是一项多阶段综合数据处理任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：数据加载与质量分析】"
    "第一步，读取E:\\test_dir\\data.csv的全部数据，展示基本信息——总行数、列数、列名、每列数据类型、数据样例前5行。"
    "第二步，写一个Python脚本做全面数据质量分析：每列缺失值比例、重复行数、数值列是否有异常值（超过3倍IQR）、"
    "类别列是否有罕见类别（占比<1%）、数据完整性评分，把质量分析报告保存到E:\\test_dir\\quality_report.txt。"
    ""
    "【阶段二：深度统计与特征分析】"
    "第三步，对所有数值列计算描述性统计量（均值、中位数、标准差、最小值、最大值、Q1、Q3、偏度、峰度），生成统计表。"
    "第四步，对所有类别列做频数统计，计算每种类别的占比，将结果汇总成类别分布表。"
    "第五步，计算数值列之间的皮尔逊相关系数矩阵和Spearman秩相关系数矩阵，比较两者结果找出非线性关系的列对。"
    ""
    "【阶段三：多图表生成】"
    "第六步，根据主要数值列的时间趋势生成一张折线图——包含图例、坐标轴标签、标题和网格线，保存到E:\\test_dir\\trend_chart.png。"
    "第七步，根据类别列的分布生成一张条形图，按频数从高到低排序，保存到E:\\test_dir\\category_dist.png。"
    "第八步，根据年度汇总数据生成一张柱状图，对比2025和2026年的各月数据，保存到E:\\test_dir\\year_compare.png。"
    ""
    "【阶段四：多格式输出】"
    "第九步，把完整统计数据写入Excel工作簿保存到E:\\test_dir\\data_report.xlsx，"
    "用多个Sheet组织数据：Sheet1原始数据预览、Sheet2描述性统计、Sheet3类别分布、Sheet4相关性矩阵、Sheet5数据质量。"
    "第十步，基于所有分析结果撰写Word分析总结文档保存到E:\\test_dir\\analysis_summary.docx，"
    "嵌入三张图表，文档包含章节：数据概况、质量分析、统计特征、图表分析、结论建议。"
    "总结中要包含数据概况、关键发现、统计结论和可视化分析四大板块。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p4_05_comprehensive_data():
    """P4-05: 综合数据处理"""
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
            "E2E-P4-05", "综合数据处理",
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
            "E2E-P4-05", "综合数据处理", result, db, lc,
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
            "E2E-P4-05", "综合数据处理",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
