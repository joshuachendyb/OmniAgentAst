"""E2E-P4-02: 数据分析报告（DATA+DOCUMENT多工具）
操作手册:
  用例: E2E-P4-02
  用户输入: 读csv→统计特征→筛选2026→柱状图→Word报告
  前置数据: data.csv存在于E:\test_dir，含数值列和2026年数据
  预期调用链: read_text_file→analyze_data→filter_data→generate_chart→write_docx
  通过标准: 图表和Word报告都存在
  失败标准: 任意生成文件缺失

-- 小欧 2026-06-27, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P4-02"
TEST_CASE_NAME = "数据分析报告"
USER_INPUT = (
    "这是一项多阶段数据分析任务，请严格按照以下阶段顺序执行。"
    ""
    "【阶段一：数据加载与探索】"
    "第一步，读取E:\\test_dir\\data.csv文件的全部数据，先展示数据集的基本信息——总记录数、列数、列名、每列数据类型和数据样例（前3行）。"
    "第二步，写一个Python脚本来做全面的数据质量检查：统计每列的缺失值数量和比例、检查重复行数、识别异常值（超过3倍标准差的数值），把检查结果保存到E:\\test_dir\\data_quality.txt。"
    ""
    "【阶段二：深度统计分析】"
    "第三步，对所有数值列做描述性统计分析——均值、中位数、标准差、最大值、最小值、四分位数、偏度和峰度，生成统计汇总表。"
    "第四步，对类别列做频数统计和分布分析，识别出最常见的几种类别和占比。"
    "第五步，计算数值列之间的皮尔逊相关系数矩阵，找出相关系数>0.7或<-0.7的强相关列对，把相关性分析结果保存到E:\\test_dir\\correlation.txt。"
    ""
    "【阶段三：时间序列分析】"
    "第六步，筛选出2026年的所有记录，按月份汇总销售额，计算月度销售趋势。"
    "第七步，写一个Python脚本做同比增长分析：对比2025年和2026年同期的销售额，计算同比增长率，标记增长/下降超过20%的月份，把结果保存到E:\\test_dir\\yoy_analysis.txt。"
    ""
    "【阶段四：可视化】"
    "第八步，根据2026年月度销售数据生成一张柱状图，包含月份标签、销售额标注和趋势线，保存到E:\\test_dir\\monthly_sales_chart.png。"
    "第九步，根据相关性矩阵生成一张热力图，保存到E:\\test_dir\\correlation_heatmap.png。"
    ""
    "【阶段五：综合报告】"
    "第十步，把以上所有分析结果整合成一份专业的Word分析报告保存到E:\\test_dir\\sales_report.docx，报告要包含数据质量表、统计特征表、相关系数矩阵、同比增长分析表和嵌入两张图表。"
    "第十一步，独立生成四种版本的报告（TXT精简版、DOCX完整版、带图表的DOCX版、PDF版）存入E:\\test_dir\\report\\目录下你创建于于本次任务相关的目录存放报告。"
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
async def test_e2e_p4_02_data_analysis():
    """P4-02: 数据分析报告"""
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
            "E2E-P4-02", "数据分析报告",
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
            "E2E-P4-02", "数据分析报告", result, db, lc,
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
            "E2E-P4-02", "数据分析报告",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
