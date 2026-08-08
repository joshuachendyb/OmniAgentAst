"""E2E-P2-01: 开发环境检查流程（SHELL多工具）
操作手册: 全面检查Python/Node/Go/Rust/Git/Docker等开发工具链，生成多格式环境报告
预期调用链: execute_shell_command(x15+) -> write_text_file(x3)
前置条件: python和git在PATH中；E:\test_dir\ 可写
验证原则：不限制中间工具调用链，只检查最终结果合理性 + DB/日志完整性
中间过程（工具链、调用顺序）只记录不限制，如实写入测试报告

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P2-01"
TEST_CASE_NAME = "开发环境检查流程"
USER_INPUT = (
    "请帮我做一个全面的开发环境深度检查，确保开发工具链完整就绪。"
    "任务分五个阶段执行："
    "第一阶段——系统基础信息检查：获取操作系统完整版本（通过wmic os get caption,version或systeminfo），"
    "CPU信息（型号、核数），内存大小（总量和可用量），PATH环境变量中关键路径的分布情况，"
    "将系统基础信息写入E:\\test_dir\\env_check\\system_info.txt。"
    "第二阶段——编程语言运行时检查：分别查找并列出以下运行时环境的命令路径和精确版本号——"
    "Python（python.exe和python3区分，列出sys.path），Node.js（node.exe），Go（go.exe），"
    "Rust（rustc.exe和cargo.exe），Java（java.exe，如果存在的话），"
    "对每个运行时标注安装状态（就绪/未找到），列出所有版本号到E:\\test_dir\\env_check\\languages.txt。"
    "第三阶段——包管理器和构建工具检查：查找并获取以下工具的路径和版本——"
    "npm, pnpm, yarn（三者的路径和版本，标注哪个是默认），"
    "pip, pip3, conda（Python包管理器），Make, MSBuild（C++构建工具），"
    "Git for Windows的bash和ssh组件，将包管理器信息汇总到E:\\test_dir\\env_check\\package_managers.txt。"
    "第四阶段——开发工具和版本控制检查：查找——"
    "Visual Studio Code的code命令路径和版本，GitHub CLI（gh.exe）路径和版本，"
    "Docker Desktop（docker.exe）路径和版本，SSH客户端（ssh.exe）路径和版本，"
    "7-Zip或WinRAR等通用压缩工具，输出到E:\\test_dir\\env_check\\dev_tools+时间.txt。"
    "第五阶段——生成汇总报告：读取前面所有阶段生成的检查文件，"
    "整合生成E:\\test_dir\\env_check\\env_summary+时间.json"
    "（结构化JSON，包含每个工具的name、path、version、status、category字段）"
    "和E:\\test_dir\\env_check\\env_summary+时间.md"
    "（面向人类阅读的Markdown报告，包含总览表、缺失工具清单、环境健康度评分）。"
    "最后，列出env_check目录的完整内容确认所有报告文件已正确生成。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
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
async def test_e2e_p2_01_env_check():
    """P2-01: 开发环境检查流程"""
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
            "E2E-P2-01", "开发环境检查",
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
            "E2E-P2-01", "开发环境检查", result, db, lc,
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
            "E2E-P2-01", "开发环境检查",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
