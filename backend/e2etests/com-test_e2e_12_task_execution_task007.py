"""全链路E2E集成测试 - unit-12: 任务书执行验证(task007)
严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

操作手册对照:
    用例: unit-12
     用户输入: "读取任务书E:\\test_dir\\task\\task007.txt,分析可行性和实施方案,逐一执行全部任务,做任务总结"
      前置数据: E:\test_dir\task\task007.txt存在
     预期过程: 读取任务书→分析任务个数→逐一执行→任务总结
     通过标准: 调用readtext;回复包含任务总结关键词;DB三表完整;日志无ERROR
     失败标准: 未读任务书;无总结;DB记录不完整;日志有ERROR

   铁律:
     1. 一个用例一个脚本,写完跑通再写下一个
     2. 所有验证基于真实在里运行,禁止Mock
     3. 测试前必须重启在里服务(手册6.1)
     4. 禁止在测试代码中使用emoji字符
     5. finally中必须调用write_test_record(手册5.5铁律)
     6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-07-17 (基于 unit-06 复制; 与 case-06 互换读取目标: 本用例读取 task007.txt)
-- 更新: 2026-08-22 - 小欧 - §10.3适配: 本case旧action_tool取数块(type过滤+顶层tool_name+observation字段)收敛为verify_db_tool_usage单点校验(e2e_helpers FUNCTIONS.md九.1), 协议再变只改helper一处
"""

from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db, check_logs,
    print_report, write_test_record,
    assert_stream_ended, verify_consistency, verify_steps, filter_safety_errors,
    register_pending_record,
    verify_db_tool_usage,
)

TASK_FILE = Path("E:/test_dir/task/task007.txt")  # 与user_input读取目标一致(unit-06复制时漏改) - 小欧 2026-07-17


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_unit_12_task_execution():
    """unit-12: 任务书执行 - 读取任务书(task007.txt)逐一执行全部任务"""

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
    user_input = (
        '你需要读取任务书"E:\test_dir\task\task007.txt"的要求,'
        "分析任务的可行性和实施方案,"
        "分析任务书的任务要求是多少个,然后按照任务书的要求逐一执行全部任务!"
        "记录和分析任务的tool调用过程和合理性分析,将分析结果记录到任务执行总结文档中!"
            "完成任务必须做任务总结"
        "将本次任务的工具调用进行合理性分析,甄别工具和工具参数是否合理, 是否无效的重复,并写出本次任务的工具调用分析报告"
        
    )
    try:
        register_pending_record(
            "unit-12", "任务书执行验证",
            user_input, {}, {}, [], [], {"errors":[],"tracebacks":[]}, False,
        )
        assert ensure_backend_ready(), "在里未启动(手册6.1)"
        assert TASK_FILE.exists(), f"任务书不存在: {TASK_FILE}"

        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result

        end_type = assert_stream_ended(result)
        assert end_type == "final", f"任务必须以final正常结束(MUST), actual: {end_type}"

        # unit-10核心: 必须调用readtext读取任务书
        tool_names = [t["tool_name"] for t in result["tool_calls"]]
        file_tools = {"readtext"}
        has_read = any(n in file_tools for n in tool_names)
        assert has_read, f"必须调用readtext(MUST unit-10), 实际: {tool_names}"

        # unit-10核心: 回复应包含任务总结关键词
        resp = result["response_text"]
        assert resp, "回复不能为空(MUST)"
        resp_lower = resp.lower()
        # unit-10任务为调研报告型(task007: 调研opencode/hermes并对比写文档), 关键词需匹配调研类回复 - 小欧 2026-07-17
        task_keywords = {"研究", "文档", "分析", "opencode", "hermes", "借鉴", "技术", "升级", "总结", "完成", "报告"}
        has_task_keyword = any(kw in resp_lower for kw in task_keywords)
        assert has_task_keyword, f"回复应包含任务总结关键词(MUST unit-10), 回复: {resp[:200]}"

        db = check_db(sid)
        # 2026-08-07 小欧: 迁移新版helperAPI(原assert_db_integrity→DB字段显式断言)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], "is_valid必须为true(MUST)"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"DB步骤字段异常(MUST): {db['step_field_issues']}"
        assert db["execution_steps_count"] >= 1, (
            f"execution_steps必须有记录(MUST unit-10), 实际={db['execution_steps_count']}"
        )
        # 2026-08-22 小欧 §10.3适配: 旧action_tool取数块收敛为verify_db_tool_usage单点校验(FUNCTIONS.md 9.1)
        _ti = verify_db_tool_usage(db, expect_any_tools=file_tools)
        assert len(_ti) == 0, f"DB steps中应有readtext操作(MUST unit-10): {_ti}"

        # 2026-08-07 小欧: 原assert_data_consistency→verify_consistency+verify_steps
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"

        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常(MUST): {si}"

        lc = check_logs(test_start, sid)
        # 2026-08-07 小欧: 原assert_log_clean→filter_safety_errors过滤断言
        _safety = filter_safety_errors(lc["errors"])
        assert len(_safety["other_errors"]) == 0, f"日志不应有非安全ERROR(MUST): {_safety['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            "unit-12", "任务书执行验证", result, db, lc,
            ci, si, True, elapsed,
            extra={
                "LLM calls": result["llm_call_count"],
                "Tools": tool_names,
                "DB steps": db["execution_steps_count"],
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
            "unit-12", "任务书执行验证",
            user_input,
            r or {}, db, ci, si, lc, passed, elapsed,
            error_info=error_info,
        )
