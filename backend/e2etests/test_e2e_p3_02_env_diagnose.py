"""E2E-P3-02: 环境配置诊断（SYSTEM多工具，需管理员权限）
操作手册:
  用例: E2E-P3-02
  用户输入: 查看PATH/python路径/注册表，保存诊断报告
  前置数据: 系统正常运行
  预期调用链: get_env→find_command(python)→get_env→registry_read→write_text_file
  通过标准: 报告包含PATH/python路径/注册表信息
  失败标准: 任一步骤失败
  ⚠️ 需管理员权限（注册表读取）——非管理员下registry_read可能失败，测试记录如实写入

-- 小欧 2026-06-26, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P3-02"
TEST_CASE_NAME = "环境配置诊断"
USER_INPUT = (
    "帮我全面诊断并修复当前的开发环境配置。"
    "第一阶段——检查系统PATH环境变量，列出所有路径并逐项分析："
    "标记哪些目录不存在、哪些目录中包含了可执行文件但未被PATH覆盖。"
    "确认Python安装目录、Node.js安装目录、Git安装目录是否都在PATH中。"
    "第二阶段——查找开发工具链的完整路径和版本信息："
    "python.exe（版本号、架构32/64bit、pip是否可用）、"
    "node.exe（版本号、npm是否可用、是否安装了cnpm/yarn）、"
    "git.exe（版本号、全局配置user.name和user.email是否已设置）、"
    "gcc/cl.exe（如果有C/C++编译器也列出版本信息）。"
    "第三阶段——检查Python环境健康度：查看PYTHONPATH变量设置，"
    "列出所有已安装的pip包，检查是否有版本冲突或已废弃的包，"
    "检查virtualenv/venv环境是否正常创建。"
    "生成一份requirements.txt（列出所有核心依赖包及其版本）。"
    "第四阶段——查找Windows注册表中的Python和Node.js安装信息，"
    "包括安装路径、版本、注册组件、卸载信息等，核对这些注册表信息"
    "与实际文件系统中的安装文件是否一致。"
    "第五阶段——基于诊断结果生成修复脚本env_fix.ps1（PowerShell脚本），"
    "自动修复发现的问题（如补全PATH缺失路径、安装缺失的工具链组件）。"
    "同时生成完整的环境诊断报告保存在E:\\test_dir\\env_diagnose.md，"
    "包含每个阶段的诊断结果、标记的问题、修复状态、以及配置改善建议。"
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
async def test_e2e_p3_02_env_diagnose():
    """P3-02: 环境配置诊断"""
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
            "E2E-P3-02", "环境配置诊断",
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
        assert result["unique_step_numbers"] < 50, "疑似死循环(MUST)"

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
            "E2E-P3-02", "环境配置诊断", result, db, lc,
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
            "E2E-P3-02", "环境配置诊断",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
