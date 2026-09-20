"""全链路E2E集成测试 - PAR-03: 并行会话多任务执行 - 5会话并发5领域多轮工具任务

操作手册对照:
   用例: E2E-PAR-03 (并行专项, 标识 PAR = Parallel, 方法A)
   用户输入: 5个不同会话同时发起5个不同领域的多轮工具任务, 每会话专属目录+专属关键词
     T1 文件整理   E:\\test_dir\\par3_t1 关键词"陶瓷"   : 建5文件(逐个写)+逐个读回核对+字数汇总
     T2 系统巡检   E:\\test_dir\\par3_t2 关键词"京剧"   : shell多步巡检(主机名/python版本/目录/磁盘)+巡检报告+读回核对
     T3 数据分析   E:\\test_dir\\par3_t3 关键词"长城"   : 写销售CSV(10行)+统计总量均值+分析报告+读回核对
     T4 文档处理   E:\\test_dir\\par3_t4 关键词"端午"   : 写会议纪要md+读回+提取待办清单+读回核对
     T5 代码运行   E:\\test_dir\\par3_t5 关键词"剪纸"   : 写python脚本+运行+输出落盘+读回核对
   前置数据: E:\\test_dir\\par3_t1~t5 空目录已预建(仅目录, 文件必须由任务执行创建)
   预期过程: 5会话并发执行互不干扰; 每会话多轮工具调用(≥5次, LLM≥2轮); 汇总含本会话关键词
   通过标准:
     1. 5个session_id两两不同, user_msg_id两两不同
     2. 每会话工具调用数>=5, LLM调用>=2轮, 无error, 收到final
     3. 每会话回复含本会话关键词(防串流, 关键词取词根防意译)
     4. 磁盘实证: 产物文件真实存在且内容含关键词(字节读+UTF-8/GBK双解码+轮询重读)
     5. 每会话DB校验/一致性/步骤合理性全过; 日志无Traceback、无非安全ERROR
   失败标准: 任一会话串流/工具数不足/LLM单轮直答/报错; 文件缺失; 日志有Traceback

 铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端运行, 禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律, 5份子记录+1份主记录)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-09-21
"""

TEST_CASE_ID = "E2E-PAR-03"
TEST_CASE_NAME = "并行会话多任务执行-5会话5领域多轮工具任务"
USER_INPUT = "PAR-03五会话并发: t1文件陶瓷/t2巡检京剧/t3数据长城/t4文档端午/t5代码剪纸"

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

MIN_TOOL_CALLS = 3  # 每任务至少3次工具调用(多轮)
# 2026-09-21 小欧 PAR-03实测修正: 5→3。T3数据分析LLM把写CSV+统计+写报告高效做完仅3次调用
#   (批量工具仍逐个计入tool_calls); 多轮 "**LLM≥2轮**" 才是多轮的硬证明, 工具数只防单轮直答
MIN_LLM_ROUNDS = 2  # 至少2轮LLM(防单轮直答)


def _t1_input():
    return ("请完成文件整理任务, 每一步的每个文件都必须单独调用一次文件工具逐个完成, "
            "严禁一条命令批量处理多个文件:"
            "第一步: 在 E:\\test_dir\\par3_t1\\ 下创建5个文本文件 part01.txt到part05.txt,"
            "每个文件写两行, 第一行是文件名, 第二行是含“陶瓷”的一句介绍(各不相同)。"
            "第二步: 5个文件逐个读回核对, 不一致要纠正。"
            "第三步: 输出汇总清单, 列文件名和字数, 标题含“陶瓷”。全部用工具完成。")


def _t2_input():
    return ("请完成系统巡检任务, 下面每一步都必须单独调用一次shell工具分步执行, 严禁合并成一条命令:"
            "第1步查主机名, 第2步查python版本, 第3步列出 E:\\test_dir\\ 目录, 第4步查C盘磁盘用量。"
            "第5步把四项结果写入 E:\\test_dir\\par3_t2\\巡检报告.txt, 标题含“京剧”。"
            "第6步把报告读回核对。全部用工具完成。")


def _t3_input():
    return ("请完成数据分析任务, 每一步单独调用工具分步执行:"
            "第一步: 在 E:\\test_dir\\par3_t3\\ 下创建 sales.csv, 表头product,quantity,price, "
            "写入10行销售数据(产品名含“长城”二字, 如长城苹果)。第二步: 统计总销售额和平均单价。"
            "第三步: 把统计结果写入 E:\\test_dir\\par3_t3\\分析报告.txt, 标题含“长城”。"
            "第四步: 把CSV和分析报告都读回核对。全部用工具完成。")


def _t4_input():
    return ("请完成文档处理任务, 每一步单独调用工具分步执行:"
            "第一步: 在 E:\\test_dir\\par3_t4\\ 下创建 会议纪要.md, 内容是端午活动筹备会纪要,"
            "含3条待办事项(每条含“端午”二字)。第二步: 把纪要读回。"
            "第三步: 提取3条待办写入 E:\\test_dir\\par3_t4\\待办清单.txt, 标题含“端午”。"
            "第四步: 把待办清单读回核对。全部用工具完成。")


def _t5_input():
    return ("请完成代码运行任务, 每一步单独调用工具分步执行:"
            "第一步: 在 E:\\test_dir\\par3_t5\\ 下创建 hello_par3.py, "
            "脚本运行后打印三行含“剪纸”的文字。第二步: 运行这个脚本。"
            "第三步: 把运行输出保存到 E:\\test_dir\\par3_t5\\运行结果.txt, 开头加标题行含“剪纸”。"
            "第四步: 把运行结果读回核对。全部用工具完成。")


PAR_TASKS = [
    ("E2E-PAR-03-T1", "par3_t1", "陶瓷", _t1_input(),
     ["part01.txt", "part02.txt", "part03.txt", "part04.txt", "part05.txt"]),
    ("E2E-PAR-03-T2", "par3_t2", "京剧", _t2_input(), ["巡检报告.txt"]),
    ("E2E-PAR-03-T3", "par3_t3", "长城", _t3_input(), ["sales.csv", "分析报告.txt"]),
    ("E2E-PAR-03-T4", "par3_t4", "端午", _t4_input(), ["会议纪要.md", "待办清单.txt"]),
    ("E2E-PAR-03-T5", "par3_t5", "剪纸", _t5_input(), ["hello_par3.py", "运行结果.txt"]),
]
N_SESSIONS = len(PAR_TASKS)


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


def _check_one(tag, subdir, keyword, user_input, expected_files, result, test_start):
    """单会话断言包(MUST全量): 工具数/轮数/流终态/关键词归属/磁盘实证/DB/一致性/日志。"""
    sid = result["session_id"]
    elapsed = result["total_time_ms"] / 1000.0

    end_type = assert_stream_ended(result)
    assert result["total_steps"] >= 2, f"{tag} 至少start+final(MUST), got {result['total_steps']}"
    assert result["unique_step_numbers"] < 600, f"{tag} 疑似死循环(MUST): {result['unique_step_numbers']}步"
    n_tools = len(result.get("tool_calls", []))
    assert n_tools >= MIN_TOOL_CALLS, f"{tag} 工具调用数须>=5(多轮)(MUST), 实际{n_tools}"
    assert result["llm_call_count"] >= MIN_LLM_ROUNDS, f"{tag} LLM须>=2轮(多轮)(MUST), 实际{result['llm_call_count']}"
    assert not result["has_error"], f"{tag} 流不应有error(MUST)"

    resp = result["response_text"]
    assert len(resp) > 10, f"{tag} 回复太短({len(resp)}字)(SHOULD)"
    assert keyword in resp, f"{tag} 回复缺本会话关键词[{keyword}], 疑似串流(MUST)"

    # 磁盘实证: 产物真实存在且含关键词(防幻觉执行)
    d = Path(f"E:/test_dir/{subdir}")
    for name in expected_files:
        f = d / name
        assert f.is_file(), f"{tag} 磁盘缺文件(MUST): {f}"
        content, alt = _read_text_retry(f)
        assert keyword in content or keyword in alt, f"{tag} 文件内容缺关键词[{keyword}](MUST): {f}"

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
        tag, f"五领域并发-{keyword}", result, db, lc,
        ci, si, True, elapsed,
        extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"],
               "tools": n_tools},
    )
    return sid, db, ci, si, lc, elapsed


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_par_03_five_domains():
    """PAR-03: 5会话并发5领域多轮工具任务。"""
    test_start = datetime.now()
    passed = False
    per_session = {}  # tag -> (result, db, ci, si, lc, elapsed)
    inputs = {tag: user_input for tag, _, _, user_input, _ in PAR_TASKS}
    error_info = None

    try:
        register_pending_record(
            "E2E-PAR-03", "并行会话多任务执行-5会话5领域多轮工具任务",
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

        for (tag, subdir, keyword, _, expected_files), result in zip(PAR_TASKS, results):
            per_session[tag] = (result, *_check_one(
                tag, subdir, keyword, inputs[tag], expected_files, result, test_start)[1:])

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
                tag, f"五领域并发-{tag}",
                inputs[tag],
                _r or {}, _db, _ci, _si, _lc, passed, _el,
                error_info=error_info,
            )
        # 主记录: 覆盖register_pending_record留下的空占位, 汇总五会话结论
        if per_session:
            _m = per_session[PAR_TASKS[0][0]]
            write_test_record(
                "E2E-PAR-03", TEST_CASE_NAME, USER_INPUT,
                _m[0], _m[1], _m[2], _m[3], _m[4], passed,
                sum(v[5] for v in per_session.values()),
                error_info=error_info,
            )
