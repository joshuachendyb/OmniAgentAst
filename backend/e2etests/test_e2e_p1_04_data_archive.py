"""全链路E2E集成测试 - P1-04: FILE工具多任务场景- 数据归档流程
操作手册对照:
   用例: E2E-P1-04
   用户输入: 执行一个多步骤数据归档操作
   通过标准: 流正常结束；zip/tar/manifest/report存在；DB记录完整
   失败标准: 流异常中止；归档文件缺失

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
    4. 禁止在测试代码中使用emoji字符
    5. finally中必须调用write_test_record(手册5.5铁律)
    6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
 
-- 小健 2026-06-24, 小沈 2026-07-03 rewrite
"""

TEST_CASE_ID = "E2E-P1-04"
TEST_CASE_NAME = "FILE工具多任务场景- 数据归档流程"
USER_INPUT = (
    "请对E:\\test_dir目录下的所有文件执行一次完整的数据归档和项目打包操作。"
    "第一阶段——先列出E:\\test_dir下的完整目录结构，按文件类型分类统计："
    "源代码文件（.py/.js/.ts/.java等）、文档文件（.txt/.md/.docx等）、"
    "数据文件（.csv/.json/.xml等）、配置文件（.yaml/.toml/.ini等）各自的数量和总大小。"
    "第二阶段——读取目录下所有源代码文件的头部注释和文件结构，"
    "分析项目整体架构，识别出核心模块和辅助模块的依赖关系。"
    "生成一份项目结构分析报告。"
    "第三阶段——创建E:\\test_dir\\backup目录，将全部文件分门别类归档："
    "生成archive.zip（包含全部文件的标准ZIP压缩包）、"
    "生成archive.tar（保留文件权限和目录结构的TAR包）。"
    "第四阶段——生成归档清单文件manifest.json，包含每个文件的路径、大小、"
    "修改时间、校验和（SHA256）、文件类型分类。"
    "第五阶段——生成完整的归档报告保存到E:\\test_dir\\archive_report+时间.md，"
    "包含：归档前文件统计、目录结构图、压缩前后大小对比、各类型文件的分布统计、"
    "校验和清单、归档操作的完整日志。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
    "最后:分析本次任务的执行工具实际调用与计划是不是一致,工具使用是不是合理,并形成工具调用合理性及冗余分析报告"
)

from datetime import datetime
import os

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended,
    verify_response_quality,
    verify_db_steps_data_completeness,
    register_pending_record, filter_safety_errors,
)


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p1_04_data_archive():
    """P1-04: FILE工具多任务场景- 数据归档流程"""

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
        register_pending_record(
            "E2E-P1-04", "FILE多任务-数据归档",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"


        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)

        assert result["total_steps"] >= 2, f"至少start+final(MUST)"
        assert result["unique_step_numbers"] < 300, f"疑似死循环(MUST)"

        quality_issues = verify_response_quality(result)
        assert len(quality_issues) == 0, f"回复质量问题: {quality_issues}"
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST)"
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
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "E2E-P1-04", "FILE多任务-数据归档", result, db, lc,
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
            "E2E-P1-04", "FILE多任务-数据归档",
            user_input, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
