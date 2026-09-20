"""全链路E2E集成测试 - PAR-04: 并行会话多任务执行 - 5会话并发行业研究报告(联网搜索+写报告)

操作手册对照:
   用例: E2E-PAR-04 (并行专项, 标识 PAR = Parallel, 方法A)
   用户输入: 5个不同会话同时发起5个不同主题的研究报告任务, 每会话专属目录+专属关键词
     R1 AI行业研究      E:\\test_dir\\par4_r1 关键词"人工智能" : 联网多轮搜索+研究报告+读回核对
     R2 钢铁行业发展    E:\\test_dir\\par4_r2 关键词"钢铁"     : 联网多轮搜索+研究报告+读回核对
     R3 Agent技术行业   E:\\test_dir\\par4_r3 关键词"Agent"    : 联网多轮搜索+研究报告+读回核对
     R4 厄尔尼诺现象    E:\\test_dir\\par4_r4 关键词"厄尔尼诺" : 联网多轮搜索+研究报告+读回核对
     R5 物业领域法律    E:\\test_dir\\par4_r5 关键词"物业"     : 联网多轮搜索+研究报告+读回核对
   前置数据: E:\\test_dir\\par4_r1~r5 空目录已预建(仅目录, 报告必须由任务执行创建)
   预期过程: 5会话并发执行互不干扰; 每会话多轮搜索(≥2次)+写报告+读回核对; 报告标题含关键词
   通过标准:
     1. 5个session_id两两不同, user_msg_id两两不同
     2. 每会话工具调用数>=4(含≥2次搜索), LLM调用>=2轮, 无error, 收到final
     3. 每会话回复含本会话关键词(防串流, 关键词取词根防意译)
     4. 磁盘实证: 研究报告真实存在、内容含关键词且长度>500字(防幻觉/防空报告)
     5. 每会话DB校验/一致性/步骤合理性全过; 日志无Traceback、无非安全ERROR
   失败标准: 任一会话串流/搜索不足/报告缺失或过短/报错; 日志有Traceback

 铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端运行, 禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律, 5份子记录+1份主记录)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-09-21
"""

TEST_CASE_ID = "E2E-PAR-04"
TEST_CASE_NAME = "并行会话多任务执行-5会话并发行业研究报告"
USER_INPUT = "PAR-04五会话并发研究报告: r1人工智能/r2钢铁/r3Agent/r4厄尔尼诺/r5物业"

import asyncio
import time as _time
from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

MIN_TOOL_CALLS = 4     # 每任务至少4次工具调用(含≥2次搜索+写报告+读回)
MIN_SEARCH_CALLS = 2   # 至少2次联网搜索(多轮证据)
MIN_LLM_ROUNDS = 2     # 至少2轮LLM(防单轮直答)
MIN_REPORT_CHARS = 500  # 报告正文至少500字(防空报告)


def _research_input(subdir, filename, keyword, topic):
    return ("请完成一份行业研究报告任务, 必须调用工具分步完成, 严禁只用对话回答:"
            f"第一步: 调用联网搜索工具，分多次搜索“{topic}”的最新情况，"
            "至少搜索2个不同角度（如现状规模、最新动态/数据）。"
            f"第二步: 根据搜索结果，在 E:\\test_dir\\{subdir}\\ 下写研究报告 {filename}，"
            f"标题含“{keyword}”，正文分现状、数据/动态、结论三节，内容要具体、500字以上。"
            f"第三步: 把报告读回核对，确认标题含“{keyword}”且内容完整。全部用工具完成。")


PAR_TASKS = [
    ("E2E-PAR-04-R1", "par4_r1", "人工智能", "AI行业发展现状",
     "研究报告-AI行业.md"),
    ("E2E-PAR-04-R2", "par4_r2", "钢铁", "钢铁行业发展现状",
     "研究报告-钢铁行业.md"),
    ("E2E-PAR-04-R3", "par4_r3", "Agent", "Agent技术行业发展现状",
     "研究报告-Agent技术.md"),
    ("E2E-PAR-04-R4", "par4_r4", "厄尔尼诺", "厄尔尼诺现象研究",
     "研究报告-厄尔尼诺.md"),
    ("E2E-PAR-04-R5", "par4_r5", "物业", "物业领域最新法律执行",
     "研究报告-物业法律.md"),
]
N_SESSIONS = len(PAR_TASKS)


def _is_search_call(tool_entry):
    """工具名/目标含搜索语义即计一次搜索 — 小欧 2026-09-21"""
    text = str(tool_entry.get("tool", "")) + str(tool_entry.get("target", ""))
    return any(k in text.lower() for k in
               ("search", "web", "query", "fetch", "crawl", "搜索", "联网", "浏览"))


def _read_text_retry(fpath):
    """字节读+双解码+轮询重读(防落盘竞态撕裂读) — 小欧 2026-09-21"""
    last = ""
    for _ in range(5):
        raw = fpath.read_bytes()
        try:
            last = raw.decode("utf-8")
        except UnicodeDecodeError:
            last = raw.decode("gbk", errors="replace")
        if last and "\ufffd" not in last:
            break
        _time.sleep(1)
    alt = raw.decode("gbk", errors="replace")
    return last, alt


def _check_one(tag, subdir, keyword, user_input, filename, result, test_start):
    """单会话断言包(MUST全量): 搜索数/工具数/轮数/流终态/关键词/磁盘实证/DB/一致性/日志。"""
    sid = result["session_id"]
    elapsed = result["total_time_ms"] / 1000.0

    end_type = assert_stream_ended(result)
    assert result["total_steps"] >= 2, f"{tag} 至少start+final(MUST), got {result['total_steps']}"
    assert result["unique_step_numbers"] < 600, f"{tag} 疑似死循环(MUST): {result['unique_step_numbers']}步"
    tool_calls = result.get("tool_calls", [])
    assert len(tool_calls) >= MIN_TOOL_CALLS, f"{tag} 工具调用数须>=4(MUST), 实际{len(tool_calls)}"
    n_search = sum(1 for t in tool_calls if _is_search_call(t))
    assert n_search >= MIN_SEARCH_CALLS, f"{tag} 联网搜索须>=2次(MUST), 实际{n_search}"
    assert result["llm_call_count"] >= MIN_LLM_ROUNDS, f"{tag} LLM须>=2轮(MUST), 实际{result['llm_call_count']}"
    assert not result["has_error"], f"{tag} 流不应有error(MUST)"

    resp = result["response_text"]
    assert len(resp) > 10, f"{tag} 回复太短({len(resp)}字)(SHOULD)"
    assert keyword in resp, f"{tag} 回复缺本会话关键词[{keyword}], 疑似串流(MUST)"

    # 磁盘实证: 研究报告真实存在、含关键词、够长(防幻觉/防空报告)
    f = Path(f"E:/test_dir/{subdir}") / filename
    assert f.is_file(), f"{tag} 磁盘缺研究报告(MUST): {f}"
    content, alt = _read_text_retry(f)
    body = content if keyword in content else alt
    assert keyword in body, f"{tag} 报告缺关键词[{keyword}](MUST): {f}"
    assert len(body) >= MIN_REPORT_CHARS, f"{tag} 报告太短(须>=500字)(MUST), 实际{len(body)}字: {f}"

    db = check_db(sid)
    assert db["session_exists"], f"{tag} session必须保存到DB(MUST)"
    assert db["is_valid"], f"{tag} is_valid必须为true(MUST), got {db['is_valid']}"
    assert db["has_user_message"], f"{tag} 必须有user消息(MUST)"
    assert db["has_assistant_message"], f"{tag} 必须有assistant消息(MUST)"
    assert db["message_order_correct"], f"{tag} 消息顺序必须user在前(MUST)"
    assert len(db["step_field_issues"]) == 0, f"{tag} step字段不完整(MUST): {db['step_field_issues']}"
    assert len(db["time_issues"]) == 0, f"{tag} 时间异常(MUST): {db['time_issues']}"

    ci = verify_consistency(result, sid)
    assert len(ci) == 0, f"{tag} 一致性验证失败(MUST): {ci}"

    si = verify_steps(result, sid)
    assert len(si) == 0, f"{tag} 步骤合理性异常: {si}"

    lc = check_logs(test_start, sid)
    filtered = filter_safety_errors(lc["errors"])
    assert len(filtered["other_errors"]) == 0, f"{tag} 日志不应有非安全ERROR(MUST): {filtered['other_errors'][:3]}"
    assert len(lc["tracebacks"]) == 0, f"{tag} 日志不应有Traceback(MUST)"

    print_report(
        tag, f"研究报告并发-{keyword}", result, db, lc,
        ci, si, True, elapsed,
        extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"],
               "tools": len(tool_calls), "search": n_search},
    )
    return sid, db, ci, si, lc, elapsed


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_par_04_research_reports():
    """PAR-04: 5会话并发行业研究报告(联网搜索+写报告)。"""
    test_start = datetime.now()
    passed = False
    per_session = {}  # tag -> (result, db, ci, si, lc, elapsed)
    inputs = {}
    for tag, subdir, keyword, topic, filename in PAR_TASKS:
        inputs[tag] = _research_input(subdir, filename, keyword, topic)
    error_info = None

    try:
        register_pending_record(
            "E2E-PAR-04", "并行会话多任务执行-5会话并发行业研究报告",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # 前置: 清空五目录旧产物(仅删文件, 保留目录), 保证磁盘实证干净
        for _, subdir, _, _, _ in PAR_TASKS:
            d = Path(f"E:/test_dir/{subdir}")
            d.mkdir(parents=True, exist_ok=True)
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()

        # 5会话真正并行发起(同事件循环gather, 各自独立session)
        results = await asyncio.gather(*[
            send_chat(inputs[tag]) for tag, _, _, _, _ in PAR_TASKS
        ])

        # 跨会话隔离断言(MUST): session与user消息id全局唯一, 防分配器竞态重号
        sids = [r["session_id"] for r in results]
        assert len(set(sids)) == N_SESSIONS, f"5会话session_id必须两两不同(MUST), got {sids}"
        msg_ids = [r["user_msg_id"] for r in results]
        assert len(set(msg_ids)) == N_SESSIONS, f"5会话user_msg_id必须两两不同(MUST), got {msg_ids}"

        for (tag, subdir, keyword, _, filename), result in zip(PAR_TASKS, results):
            per_session[tag] = (result, *_check_one(
                tag, subdir, keyword, inputs[tag], filename, result, test_start)[1:])

        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        for tag, _, _, _, _ in PAR_TASKS:
            if tag not in per_session:
                continue
            _r, _db, _ci, _si, _lc, _el = per_session[tag]
            write_test_record(
                tag, f"研究报告并发-{tag}",
                inputs[tag],
                _r or {}, _db, _ci, _si, _lc, passed, _el,
                error_info=error_info,
            )
        # 主记录: 覆盖register_pending_record留下的空占位, 汇总五会话结论
        if per_session:
            _m = per_session[PAR_TASKS[0][0]]
            write_test_record(
                "E2E-PAR-04", TEST_CASE_NAME, USER_INPUT,
                _m[0], _m[1], _m[2], _m[3], _m[4], passed,
                sum(v[5] for v in per_session.values()),
                error_info=error_info,
            )
