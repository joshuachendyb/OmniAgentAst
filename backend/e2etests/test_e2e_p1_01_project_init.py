"""全链路E2E集成测试 - P1-01: FILE工具多任务场景- 项目初始化流程

操作手册对照:
   用例: E2E-P1-01
   用户输入: 请帮我完成一个完整的React前端项目的初始化搭建。项目名称newproject-react，放在E:\test_dir\new01-react下，要求严格按照标准的React项目结构来创建。需要完成以下全部步骤：第一步——创建项目根目录和所有子目录结构，包括src/components、src/pages、src/styles、src/utils、public共6个目录；第二步——在public目录下创建index.html文件，内容为标准HTML5模板，标题为'MyProject React'，包含div#root挂载点；第三步——在src目录下创建index.js作为入口文件，内容需包含ReactDOM.createRoot挂载App组件的标准代码；第四步——在src目录下创建App.js作为主组件，实现一个简单的计数器功能（useState管理count状态，包含显示和按钮）；第五步——在src/styles目录下创建App.css文件，写入基本的样式（居中布局、按钮样式、字体设置）；第六步——在src/components目录下创建一个Header.jsx导航栏组件；第七步——在src/pages目录下创建一个Home.jsx首页组件；第八步——在项目根目录创建package.json文件，包含项目名、版本1.0.0、描述、依赖（react 18, react-dom 18, react-scripts 5）和scripts（start/build/test）；第九步——在项目根目录创建.gitignore文件，排除node_modules、build、.env等目录；第十步——在项目根目录创建README.md文件，写入详细的项目说明文档，包含项目简介、技术栈、目录结构说明、快速开始指南（安装依赖->启动开发服务器->构建生产版本）四个部分。最后——列出整个项目的完整目录树结构（tree格式）确认所有文件和目录都已正确创建，并生成一份完整的项目初始化报告保存到E:\test_dir\new01-react\report\init_report.md文件中。注意：所有文件内容必须是完整且有实际意义的，不能只是骨架或占位符。

-- 小健 2026-06-24, 小沈 2026-07-03 rewrite

铁律:
   1. 一个用例一个脚本，写完跑通再写下一个
   2. 所有验证基于真实后端运行，禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理
"""

TEST_CASE_ID = "E2E-P1-01"
TEST_CASE_NAME = "FILE工具多任务场景- 项目初始化流程"
USER_INPUT = (
    "请帮我完成一个完整的React前端项目的初始化搭建。"
    "项目名称newproject-react，放在E:\\test_dir\\new01-react下，"
    "要求严格按照标准的React项目结构来创建。"
    "需要完成以下全部步骤："
    "第一步——创建项目根目录和所有子目录结构，包括src/components、src/pages、src/styles、src/utils、public共6个目录；"
    "第二步——在public目录下创建index.html文件；"
    "第三步——在src目录下创建index.js作为入口文件；"
    "第四步——在src目录下创建App.js作为主组件，实现计数器功能；"
    "第五步——在src/styles目录下创建App.css文件；"
    "第六步——在src/components目录下创建Header.jsx导航栏组件；"
    "第七步——在src/pages目录下创建Home.jsx首页组件；"
    "第八步——在项目根目录创建package.json文件（react 18, react-dom 18, react-scripts 5）；"
    "第九步——创建.gitignore文件；"
    "第十步——创建README.md文件。"
    "最后——列出完整目录树结构，生成init_report.md保存到report目录。"
    "注意：所有文件内容必须是完整且有实际意义的，不能只是骨架或占位符。"
    "把本次任务的分析实施过程和分析结果独立生成四种版本的报告存入report目录下。"
)

import os
from datetime import datetime

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
async def test_e2e_p1_01_project_init():
    """P1-01: FILE工具多任务场景- 项目初始化流程"""
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
            "E2E-P1-01", "FILE多任务-项目初始化",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        result = await send_chat(USER_INPUT)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        assert result["total_steps"] >= 2, "至少start+final(MUST)"
        assert result["unique_step_numbers"] < 50, "疑似死循环(MUST)"

        quality_issues = verify_response_quality(result)
        assert len(quality_issues) == 0, f"回复质量问题: {quality_issues}"

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
        filtered = filter_safety_errors(lc["errors"])
        assert len(filtered["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "E2E-P1-01", "FILE多任务-项目初始化", result, db, lc,
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
            "E2E-P1-01", "FILE多任务-项目初始化",
            USER_INPUT, r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
