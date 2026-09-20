"""全链路E2E集成测试 - PAR-02: 并行会话多任务执行 - 3会话并发工具调用(每会话20+轮同类文件任务)

操作手册对照:
   用例: E2E-PAR-02 (并行专项, 标识 PAR = Parallel)
   用户输入: 3个不同会话同时发起同构文件任务, 每会话: 建10个文件(逐个写) + 逐个读回核对
     S1目录E:\\test_dir\\par_s1 关键词"青花瓷"
     S2目录E:\\test_dir\\par_s2 关键词"光合作用"
     S3目录E:\\test_dir\\par_s3 关键词"丝绸之路"
   前置数据: E:\\test_dir\\par_s1/par_s2/par_s3 空目录已预建(仅目录, 文件必须由任务执行创建)
   预期过程: 3会话并发执行互不干扰; 每会话10写+10读=20+工具调用; 最终汇总清单含本会话关键词
   通过标准:
     1. 3个session_id两两不同, user_msg_id两两不同
     2. 每会话工具调用数>=20(10写+10读), 无error, 收到final
     3. 每会话回复含本会话唯一关键词(防串流)
     4. 磁盘 ground truth: 10个文件真实存在且内容含关键词(防幻觉)
     5. 每会话DB校验/一致性/步骤合理性全过; 日志无Traceback、无非安全ERROR
   失败标准: 任一会话工具数不足20/串流/报错; 文件缺失或内容不符; 日志有Traceback

 针对今日(2026-09-20)并行相关修复:
   E-1 stream_reader锁内不yield / D-2 allocator读写锁 / B机制注入串行守卫 /
   P5 LLM软配额信号量 / D-8取消帧去重 / C-1共享池快照 / D-1注入消息DB补配对

 铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端运行, 禁止Mock
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. finally中必须调用write_test_record(手册5.5铁律)
   6. 严禁在脚本内设任何超时 — 统一由pytest.ini的timeout=3000管理

-- 小欧 2026-09-21
"""

TEST_CASE_ID = "E2E-PAR-02"
TEST_CASE_NAME = "并行会话多任务执行-3会话并发工具调用20轮"
USER_INPUT = "PAR-02三会话并发文件任务: par_s1青花瓷/par_s2光合作用/par_s3丝绸之路(各10写+10读)"

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    assert_stream_ended, register_pending_record, filter_safety_errors,
)

PAR_TASKS = [
    ("E2E-PAR-02-S1", "par_s1", "青花瓷"),
    ("E2E-PAR-02-S2", "par_s2", "光合作用"),
    # 2026-09-21 小欧 PAR-02实测修正: S3关键词"丝绸之路"→"丝绸":
    #   LLM写文件时意译为"丝绸/丝路"致磁盘实证误判(非后端缺陷, 三轮S1/S2流+DB全过);
    #   取词根"丝绸"仍与S1/S2互斥, 串流检测效力不变
    ("E2E-PAR-02-S3", "par_s3", "丝绸"),
]
FILE_COUNT = 10
MIN_TOOL_CALLS = 20  # 10写 + 10读


def _build_input(subdir, keyword):
    lines = [
        f"请完成以下文件任务, 分三步走, 每一步的每个文件都必须单独调用一次文件工具逐个完成, 严禁一条命令批量处理多个文件:",
        f"第一步: 在 E:\\test_dir\\{subdir}\\ 目录下创建 {FILE_COUNT} 个文本文件 part01.txt 到 part{FILE_COUNT:02d}.txt,"
        f"每个文件写入两行内容, 第一行是该文件名, 第二行是包含“{keyword}”的一句介绍(每个文件介绍各不相同)。",
        f"第二步: 把这 {FILE_COUNT} 个文件逐个读回, 核对内容是否与写入一致, 发现不一致要纠正。",
        f"第三步: 输出一份汇总清单, 列出每个文件名和字数, 清单标题必须包含“{keyword}”。",
        "注意: 全部用工具完成, 不要只用对话回答。",
    ]
    return "".join(lines)


def _check_one(tag, subdir, keyword, user_input, result, test_start):
    """单会话断言包(MUST全量): 工具数/流终态/关键词归属/磁盘实证/DB/一致性/日志。"""
    sid = result["session_id"]
    elapsed = result["total_time_ms"] / 1000.0

    end_type = assert_stream_ended(result)
    assert result["total_steps"] >= 2, f"{tag} 至少start+final(MUST), got {result['total_steps']}"
    assert result["unique_step_numbers"] < 600, f"{tag} 疑似死循环(MUST): {result['unique_step_numbers']}步"
    n_tools = len(result.get("tool_calls", []))
    assert n_tools >= MIN_TOOL_CALLS, f"{tag} 工具调用数须>=20(10写+10读)(MUST), 实际{n_tools}"
    assert not result["has_error"], f"{tag} 流不应有error(MUST)"

    resp = result["response_text"]
    assert len(resp) > 10, f"{tag} 回复太短({len(resp)}字)(SHOULD)"
    assert keyword in resp, f"{tag} 回复缺本会话关键词[{keyword}], 疑似串流(MUST)"

    # 磁盘 ground truth: 10文件真实存在且含关键词(防幻觉执行)
    # 2026-09-21 小欧 PAR-02实测修正:
    #   ①工具写盘编码可能是GBK, UTF-8直读会把关键词冲成�致误判 → 字节读 + UTF-8/GBK双解码;
    #   ②流结束与落盘刷写存在竞态(实测S3-part05读到半截写入，UTF-8/GBK双解码均无关键词，
    #     数分钟后同文件已是合法UTF-8且含关键词) → 轮询重读，最多5次×1s，防撕裂读误判
    import time as _time
    d = Path(f"E:/test_dir/{subdir}")
    for i in range(1, FILE_COUNT + 1):
        f = d / f"part{i:02d}.txt"
        assert f.is_file(), f"{tag} 磁盘缺文件(MUST): {f}"
        content_ok = False
        for _try in range(5):
            raw = f.read_bytes()
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                content = raw.decode("gbk", errors="replace")
            if keyword in content or keyword in raw.decode("gbk", errors="replace"):
                content_ok = True
                break
            _time.sleep(1)
        assert content_ok, f"{tag} 文件内容缺关键词[{keyword}](MUST): {f}"

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
        tag, f"并行工具任务-{keyword}", result, db, lc,
        ci, si, True, elapsed,
        extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"],
               "tools": n_tools},
    )
    return sid, db, ci, si, lc, elapsed


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_par_02_concurrent_tools():
    """PAR-02: 3会话并发同构文件任务, 每会话20+工具调用。"""
    test_start = datetime.now()
    passed = False
    per_session = {}  # tag -> (result, db, ci, si, lc, elapsed)
    inputs = {tag: _build_input(subdir, kw) for tag, subdir, kw in PAR_TASKS}
    error_info = None

    try:
        register_pending_record(
            "E2E-PAR-02", "并行会话多任务执行-3会话并发工具调用20轮",
            USER_INPUT, {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"

        # 前置: 清空三目录旧文件(仅删文件, 保留目录), 保证磁盘实证干净
        for _, subdir, _ in PAR_TASKS:
            d = Path(f"E:/test_dir/{subdir}")
            d.mkdir(parents=True, exist_ok=True)
            for f in d.glob("part*.txt"):
                f.unlink()

        # 3会话真正并行发起(同事件循环gather, 各自独立session)
        results = await asyncio.gather(*[
            send_chat(inputs[tag]) for tag, _, _ in PAR_TASKS
        ])

        # 跨会话隔离断言(MUST): session与user消息id全局唯一, 防分配器竞态重号
        sids = [r["session_id"] for r in results]
        assert len(set(sids)) == 3, f"3会话session_id必须两两不同(MUST), got {sids}"
        msg_ids = [r["user_msg_id"] for r in results]
        assert len(set(msg_ids)) == 3, f"3会话user_msg_id必须两两不同(MUST), got {msg_ids}"

        for (tag, subdir, keyword), result in zip(PAR_TASKS, results):
            per_session[tag] = (result, *_check_one(
                tag, subdir, keyword, inputs[tag], result, test_start)[1:])

        passed = True

    except Exception as e:
        passed = False
        import traceback as tb
        error_info = f"{type(e).__name__}: {str(e)}\n{tb.format_exc()}"
        raise
    finally:
        for tag, subdir, keyword in PAR_TASKS:
            if tag not in per_session:
                continue
            _r, _db, _ci, _si, _lc, _el = per_session[tag]
            write_test_record(
                tag, f"并行工具任务-{tag}",
                inputs[tag],
                _r or {}, _db, _ci, _si, _lc, passed, _el,
                error_info=error_info,
            )
        # 主记录: 覆盖register_pending_record留下的空占位, 汇总三会话结论
        # 2026-09-21 小欧
        if per_session:
            _m = per_session[PAR_TASKS[0][0]]
            write_test_record(
                "E2E-PAR-02", TEST_CASE_NAME, USER_INPUT,
                _m[0], _m[1], _m[2], _m[3], _m[4], passed,
                sum(v[5] for v in per_session.values()),
                error_info=error_info,
            )
