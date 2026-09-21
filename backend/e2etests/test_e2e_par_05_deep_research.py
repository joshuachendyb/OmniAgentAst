"""全链路E2E集成测试 - PAR-05: 并行会话多任务执行 - 5会话并发深度研究报告(完成即写记录)

操作手册对照:
   用例: E2E-PAR-05 (并行专项, 标识 PAR = Parallel, 方法A)
   用户输入: 5个不同会话同时发起5个深度研究任务, 每会话专属目录+专属关键词
     S1 今日股市分析      E:\\test_dir\\par5_s1 关键词"股市"   : 今日股市情况+波动原因, 完整分析报告
     S2 股市10日趋势      E:\\test_dir\\par5_s2 关键词"趋势"   : 未来10日变化趋势(有理有据), 完整分析报告
     S3 货币市场与人民币  E:\\test_dir\\par5_s3 关键词"人民币" : 货币市场变化+人民币国际化进展+未来半年变化, 完整分析报告
     S4 中东与伊美战争    E:\\test_dir\\par5_s4 关键词"中东"   : 中东局势与伊美战争发展趋势+未来半年变化, 完整分析报告
     S5 台湾统一分析      E:\\test_dir\\par5_s5 关键词"台湾"   : 台湾统一形势+半年来变化可能, 完整分析报告
   前置数据: E:\\test_dir\\par5_s1~s5 空目录已预建(仅目录, 报告必须由任务执行创建)
   预期过程: 5会话并发执行互不干扰; 每会话多轮搜索+写报告+读回核对;
     记录按完成顺序即时写入(谁先跑完谁先落盘, as_completed, 不等其他会话)
   通过标准:
     1. 5个session_id两两不同, user_msg_id两两不同(全部收齐后断言)
     2. 每会话工具调用数>=4, LLM调用>=2轮, 无error, 收到final
     3. 每会话回复含本会话关键词(防串流, 关键词取词根防意译)
     4. 磁盘实证: 分析报告真实存在、内容含关键词且>=500字
     5. 每会话DB校验/一致性/步骤合理性全过; 日志无Traceback、无非安全ERROR
   失败标准: 任一会话串流/工具不足/报告缺失或过短/报错; 日志有Traceback

 记录机制(2026-09-21 小欧, 北京老陈要求):
   不再等5会话全完才写记录; 用asyncio.as_completed按完成顺序逐个断言、逐个
   write_test_record。跨会话id唯一性在收齐后断言(近乎不可能失败, 失败则主记录FAIL)。

 铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端运行, 禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律, 5份子记录+1份主记录)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-09-21
"""

TEST_CASE_ID = "E2E-PAR-05"
TEST_CASE_NAME = "并行会话多任务执行-5会话并发深度研究报告"
USER_INPUT = "PAR-05五会话并发深度研究: s1今日股市/s2十日趋势/s3人民币国际化/s4中东伊美/s5台湾统一"

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

MIN_TOOL_CALLS = 4     # 每任务至少4次工具调用(含搜索+写报告+读回)
MIN_LLM_ROUNDS = 2     # 至少2轮LLM(防单轮直答)
MIN_REPORT_CHARS = 500  # 报告正文至少500字(防空报告)


def _research_input(subdir, filename, keyword, topic, angles):
    return ("请完成一份深度研究报告任务, 必须调用工具分步完成, 严禁只用对话回答:"
            "第一步(必须先做, 不做不得写报告): 调用联网搜索工具searchweb，"
            f"分多次搜索“{topic}”的最新情况，至少搜索2个不同角度（{angles}），"
            "把每次搜索的要点记下来。"
            f"第二步: 根据搜索结果，在 E:\\test_dir\\{subdir}\\ 下写分析报告 {filename}，"
            f"标题含“{keyword}”，正文深入展开、500字以上，结论明确。"
            f"第三步: 把报告读回核对，确认标题含“{keyword}”且内容完整。全部用工具完成。")


PAR_TASKS = [
    ("E2E-PAR-05-S1", "par5_s1", "股市", "今日股市情况与波动原因",
     "分析报告-今日股市.md", "今日盘面、涨跌家数"),
    ("E2E-PAR-05-S2", "par5_s2", "趋势", "股市未来10日变化趋势",
     "分析报告-十日趋势.md", "技术面、资金面"),
    ("E2E-PAR-05-S3", "par5_s3", "人民币", "货币市场变化与人民币国际化进展",
     "分析报告-人民币国际化.md", "汇率走势、跨境结算"),
    ("E2E-PAR-05-S4", "par5_s4", "中东", "中东局势与伊美战争发展趋势",
     "分析报告-中东局势.md", "冲突现状、各方表态"),
    ("E2E-PAR-05-S5", "par5_s5", "台湾", "台湾统一形势分析",
     "分析报告-台湾统一.md", "两岸动态、政策信号"),
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
    """单会话断言包(MUST全量): 工具数/轮数/流终态/关键词/磁盘实证/DB/一致性/日志。"""
    sid = result["session_id"]
    elapsed = result["total_time_ms"] / 1000.0

    end_type = assert_stream_ended(result)
    assert result["total_steps"] >= 2, f"{tag} 至少start+final(MUST), got {result['total_steps']}"
    assert result["unique_step_numbers"] < 600, f"{tag} 疑似死循环(MUST): {result['unique_step_numbers']}步"
    tool_calls = result.get("tool_calls", [])
    assert len(tool_calls) >= MIN_TOOL_CALLS, f"{tag} 工具调用数须>=4(MUST), 实际{len(tool_calls)}"
    n_search = sum(1 for t in tool_calls if _is_search_call(t))
    if n_search < 2:
        print(f"[PAR-05 {tag} 注意] 联网搜索仅{n_search}次(期望>=2)，只记录不判FAIL")
    assert result["llm_call_count"] >= MIN_LLM_ROUNDS, f"{tag} LLM须>=2轮(MUST), 实际{result['llm_call_count']}"
    assert not result["has_error"], f"{tag} 流不应有error(MUST)"

    resp = result["response_text"]
    assert len(resp) > 10, f"{tag} 回复太短({len(resp)}字)(SHOULD)"
    assert keyword in resp, f"{tag} 回复缺本会话关键词[{keyword}], 疑似串流(MUST)"

    # 磁盘实证: 分析报告真实存在、含关键词、够长(防幻觉/防空报告)
    f = Path(f"E:/test_dir/{subdir}") / filename
    assert f.is_file(), f"{tag} 磁盘缺分析报告(MUST): {f}"
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
        tag, f"深度研究并发-{keyword}", result, db, lc,
        ci, si, True, elapsed,
        extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"],
               "tools": len(tool_calls), "search": n_search},
    )
    return sid, db, ci, si, lc, elapsed


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_par_05_deep_research():
    """PAR-05: 5会话并发深度研究报告, 按完成顺序即时写记录。"""
    test_start = datetime.now()
    passed = False
    per_session = {}  # tag -> (result, db, ci, si, lc, elapsed)
    results = {}      # tag -> result(收齐后做跨会话断言)
    meta = {tag: (subdir, keyword, user_input, filename)
            for tag, subdir, keyword, topic, filename, angles in PAR_TASKS
            for user_input in [_research_input(subdir, filename, keyword, topic, angles)]}
    inputs = {tag: meta[tag][2] for tag in meta}
    error_info = None

    try:
        register_pending_record(
            "E2E-PAR-05", "并行会话多任务执行-5会话并发深度研究报告",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # 前置: 清空五目录旧产物(仅删文件, 保留目录), 保证磁盘实证干净
        for _, subdir, _, _, _, _ in PAR_TASKS:
            d = Path(f"E:/test_dir/{subdir}")
            d.mkdir(parents=True, exist_ok=True)
            for f in d.iterdir():
                if f.is_file():
                    f.unlink()

        # 5会话真正并行发起; 按完成顺序逐个断言、逐个即时写记录(不等其他会话)
        tasks = {asyncio.ensure_future(send_chat(inputs[tag])): tag
                 for tag, _, _, _, _, _ in PAR_TASKS}
        for fut in asyncio.as_completed(tasks):
            tag = tasks[fut]
            result = await fut
            results[tag] = result
            subdir, keyword, user_input, filename = meta[tag]
            checked = _check_one(tag, subdir, keyword, user_input, filename,
                                 result, test_start)
            per_session[tag] = (result,) + checked[1:]
            _r, _db, _ci, _si, _lc, _el = per_session[tag]
            write_test_record(
                tag, f"深度研究并发-{tag}",
                user_input,
                _r or {}, _db, _ci, _si, _lc, True, _el,
                error_info=None,
            )

        # 跨会话隔离断言(MUST, 收齐后): session与user消息id全局唯一
        sids = [results[tag]["session_id"] for tag, _, _, _, _, _ in PAR_TASKS]
        assert len(set(sids)) == N_SESSIONS, f"5会话session_id必须两两不同(MUST), got {sids}"
        msg_ids = [results[tag]["user_msg_id"] for tag, _, _, _, _, _ in PAR_TASKS]
        assert len(set(msg_ids)) == N_SESSIONS, f"5会话user_msg_id必须两两不同(MUST), got {msg_ids}"

        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        # 主记录: 覆盖空占位, 汇总五会话结论
        if per_session:
            _m = per_session[PAR_TASKS[0][0]] if PAR_TASKS[0][0] in per_session else next(iter(per_session.values()))
            write_test_record(
                "E2E-PAR-05", TEST_CASE_NAME, USER_INPUT,
                _m[0], _m[1], _m[2], _m[3], _m[4], passed,
                sum(v[5] for v in per_session.values()),
                error_info=error_info,
            )
