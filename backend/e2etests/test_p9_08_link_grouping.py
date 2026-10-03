# -*- coding: utf-8 -*-
"""全链路E2E集成测试 - P9-08: 会话级 link 开关的分组契约(后端, 多步工具链路)

操作手册对照:
   用例: E2E-P9-08(文档[4] 新增)
   场景: 同一会话连发多条消息, 每条为真实多步工具任务, 验证 link 的分组与状态口径
   通过标准:
     门3 会话隔离 : link 开关经唯一读真源出口(GET /sessions/{id}/messages)读回, 且 /sessions/{id} 不得下发该字段
     门2 分组正确 : link 开时新任务并入"最近一条任务所在组"(context_root_task_id 相同)
     门5 任意状态 : 上一任务为 failed 时, link 开 -> 新任务**仍并入该组**
                   (本次口径变更核心风险点: 原仅认 completed, 现改为最近一条任意状态)
     条款4        : link 关时新任务自成新组, 沿用原 independent 行为
   失败标准: 链根不一致 / 两读点读不回 / 关后仍并入旧组 / failed 后被回溯到更早任务 /
             工具未真实调用 / 任务2答不出上一任务的产物(历史未注入)

【为何任务必须是多步真实工具链路】(2026-10-03 北京老陈指正: 任务太简单)
   本 case 若只用"只回复 7"这类一句话, 则:
     - 不会产生任何 tool_calls, 拿不到 [CALL CHAIN], 不构成全链路
     - 任务2与任务1无因果关系, 即使断链注入历史失败, 测试依然绿 -> 蒙人
   故任务1/任务2设计为强因果的探测文件任务:
     任务1(link关): 读源文件 -> 统计 -> 写入探测文件(含固定魔数 MAGIC-8808) -> 回读校验
     任务2(link开): **不告知文件路径**, 只说"刚才创建的探测文件", 要求回读第一行
                   -> agent 只能靠【注入的历史】知道路径与魔数
                   -> 断链则读不到/答不出魔数, 断言必红(而非侥幸绿)
   局限如实说明: 任务2 理论上可能靠扫描 E:\\test_dir 目录猜中文件, 故文件名带随机后缀降低概率;
     但核心断言(DB 链根 + 工具真实调用)是确定性的, 不受此影响。

【门5 为何直连 sqlite】(确定性验证, 非蒙人)
   无任何 API 能把任务置 failed(已核实 sessions.py 仅 POST/PUT/DELETE/trust)。
   直连 sqlite 改 status 属"造前置数据"让被测逻辑进入特定初始状态, 与 e2e_helpers:2050
   verify_token_usage 落库核查同款惯例; 被测的链根计算与分组全程走生产代码, 未 Mock 任何逻辑。
   门5 若用"等上一任务恰好 failed"的观察式写法, 断言恒成立 = 蒙人测试, 严禁。

铁律:
   1. 一个用例一个脚本, 写完跑通再写下一个
   2. 所有验证基于真实后端 + 真实 LLM, 禁止 Mock 被测逻辑
   3. 测试前必须重启后端服务(手册6.1)
   4. 禁止在测试代码中使用emoji字符
   5. 严禁在脚本内设任何超时 — 统一由 pytest.ini 的 timeout 管理

-- 小欧 2026-10-03
-- 更新: 2026-10-03 北京老陈指正"任务太简单, 怎么也要有几步" -> 任务1/任务2 改为多步工具链路强因果任务
-- 更新: 2026-10-03 小欧 文档[4] 5.7.14.4 -> 任务2 改由 send_chat(link_enabled=True) 携带开关,
   读回断言移到发消息之后
-- 更新: 2026-10-03 小欧 PATCH /sessions/{id}/link 端点废止(北京老陈定案: 开关只准随消息发出,
   严禁独立影响后端), 任务3/4/5 一并改为 send_chat(link_enabled=...) 携带, 全用例只剩一条写路径
"""

import json
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, create_session, check_db,
    verify_consistency, verify_steps, verify_db_tool_usage,
    verify_db_prompt_consistency, check_logs,
    print_report, write_test_record, assert_stream_ended, cleanup,
    register_pending_record, filter_safety_errors, _api_get,
    BASE_URL, API_PREFIX, AUTH_HEADERS, DB_PATH, READ_TOOLS,
)

TEST_CASE_ID = "E2E-P9-08"
TEST_CASE_NAME = "会话级link开关分组契约(多步工具链路)"

MAGIC = "MAGIC-8808"          # 固定魔数: 任务2 必须靠注入的历史才能答出
SRC_FILE = Path("E:/test_dir/test.txt")          # 任务1 的读取源(P9-04 同款前置)
PROBE_TEMPLATE = "E:/test_dir/p9_08_probe_{}.txt"  # 任务1 产出, 文件名含随机后缀(防任务2靠扫目录猜中)

INPUT_R1 = (
    "请完成以下多步任务, 每步都要用真实工具执行, 不要凭记忆作答:"
    "第1步 读取 {src} 的全文, 统计它的字符数(含空格)与行数;"
    "第2步 新建文件 {probe}, 第一行原样写入固定字符串 {magic}, 30遍,每一行5个"
    "文档尾巴写入第1步统计到的字符数与行数;"
    "第3步 重新读取 {probe}, 确认两行内容与写入一致。"
    "最后请说明你实际调用了哪些工具。"
)

INPUT_R2 = (
    "接着刚才的工作继续: 请读取你刚才创建的那个探测文件, "
    "把它第一行的内容原样告诉我"
    "只回答前3行行内容本身, "
    "列表查询这个文档在那个目录多大时间等文档信息"
)

INPUT_R3 = (
    "换个话题: 请用工具读取 {src} 的第一行, 然后只回答这一行的前20个字符。"
    "查询今天是几号,本地天气如何,记录到文件"
)

INPUT_R4 = (
    "继续: 请用工具读取 {src} 的第二行, 只回答这一行前20个字符。"
    "查询今天是星期几,农历是什么日子 ,本地天气如何,有木有什么活动啊,记录到文件"
)

INPUT_R5 = (
    "再继续: 请用工具读取 {src} 的第三行, 只回答这一行前20个字符。"
     "查询今天的新闻热点有什么 有木有什么活动啊,记录到文件"
)

# 本用例共发送 5 条消息 = 5 个任务(每次 send_chat 在后端建一个任务, 故产生 5 个 task_id)。
#   北京老陈指正"只有两个 INPUT 哪来的 5 个 task_id" —— 根因是任务3/4/5 的 prompt 曾以
#   内联字符串写在断言逻辑中间, 只有任务1/2 提到顶部常量, 审查时数不出总数。
#   现全部提到顶部, 并用下表固化"任务 × link 状态 × 预期链根", 便于一眼核对:
#
#   任务 | 输入        | link 开关怎么设       | 该任务自身状态   | 预期 context_root_task_id
#   ----+-------------+---------------------+------------------+--------------------------------
#    1   | INPUT_R1    | 默认关(新会话)      | completed        | 自身(条款4: 关则自成新组)
#    2   | INPUT_R2    | **随消息携带 True**  | completed        | 任务1 所在组(门2 分组正确 + 覆盖携带链路)
#    3   | INPUT_R3    | 随消息携带 False    | completed        | 自身 = 组B(条款4)
#    4   | INPUT_R4    | 随消息携带 False    | failed(人为置入) | 自身 = 组C, 且 C≠B(门5前提)
#    5   | INPUT_R5    | 随消息携带 True     | completed        | 组C(门5: 上一任务failed仍并入, 不回溯到组B)
#
#   任务3/4/5 的内容刻意做成"读文件第N行"这种轻任务: 它们的作用不是考验 LLM 能力,
#   而只是**产生新任务供观测链根**(门4/门5 需要新任务才能看到分组结果), 用最少 LLM 调用达成。
#
# 串行 + 固定间隔(北京老陈 2026-10-03 指示):
#   1) 严禁并行: 5 个任务必须严格串行, 前一个完全结束(SSE 收到 final + 后端收尾落库完成)
#      之后才发下一个。并行会同时打多个 LLM 请求, 既会撞 429 限流, 也会让"最近一条任务"
#      的判定出现竞态, 门5 的观测结果不可信。本文件无 gather/create_task 等并行原语。
#   2) 固定间隔 JOB_GAP_SECONDS: 上个任务结束后后端仍有异步收尾(大体积 execution_steps
#      落库、token_usage 明细实时落库), 紧接发送可能读到尚未写完的状态。故留 5 秒缓冲。
JOB_GAP_SECONDS = 5


def _record_round(no: int, user_input: str, result: dict, session_id: str,
                  task_id: str, round_start, checks: list,
                  rounds_all: list, task_ids_all: list) -> None:
    """单个任务跑完即落一份测试记录(北京老陈 2026-10-03 指示: 每完成一个任务就出记录)。

    之前只在 finally 里写一份汇总记录, 失败时只能看到"整个用例红了", 无法定位是哪个任务出的问题;
    且单任务维度(DB步骤/一致性/日志窗口)也只有在按任务落盘时才准确 ——
    汇总那次用的是末任务的 task_id 与末任务的时间窗口, 前几个任务的数据会被覆盖。

    记录编号: E2E-P9-08-T1 ~ T5, 与汇总记录 E2E-P9-08 分开, 互不覆盖。
    每个任务各自统计: 该任务自己的 DB 步骤 / SSE-DB 一致性 / 步骤合理性 / 时间窗口内的日志。
    """
    r_db = check_db(session_id, task_id)
    r_ci = verify_consistency(result, session_id)
    r_si = verify_steps(result, session_id)
    r_lc = check_logs(round_start, session_id, result.get("user_msg_id"))
    r_dpi = verify_db_prompt_consistency(session_id, result.get("user_msg_id"))
    _rf = filter_safety_errors(r_lc["errors"])
    write_test_record(
        f"{TEST_CASE_ID}-T{no}", f"{TEST_CASE_NAME}-任务{no}",
        user_input, result, r_db, r_ci, r_si, r_lc,
        True, result.get("total_time_ms", 0) / 1000.0,
        extra={
            "本记录范围": f"仅任务{no}(共5个任务, 每个任务各有一份记录 T1~T5)",
            "本任务task_id": task_id,
            "本任务工具链": [t["tool_name"] for t in result.get("tool_calls", [])],
            "本任务LLM调用": result.get("llm_call_count", 0),
            "本任务SSE事件数": result.get("total_steps", 0),
            "本任务跨任务注入": _injection_of(result)["有无注入"],
            "本任务已验证断言": list(checks),
            "截至本任务的任务链根": [
                {"序": i + 1, "task_id": task_ids_all[i], "链根": t[1], "状态": t[2]}
                for i, t in enumerate(
                    _tasks(session_id)) if i < len(task_ids_all)
            ],
        },
        dpi=r_dpi,
    )


def _tasks(session_id: str) -> list:
    """取该会话任务 (task_id, context_root_task_id, status), 按创建序"""
    data = _api_get(f"/sessions/{session_id}/tasks", timeout=30)
    assert data, "GET /sessions/{id}/tasks 不可用"
    return [(t["task_id"], t.get("context_root_task_id"), t.get("status"))
            for t in data.get("tasks", [])]


def _link_read(session_id: str):
    """读回 link_enabled —— 唯一读真源出口是 GET /sessions/{id}/messages(5.7.13)。

    2026-10-03: 原实现同时读 /sessions/{id} 与 /messages 做"两读点一致"校验。该第二读点
    已按 YAGNI/DRY 废止(零消费字段 = 同一真源开两个 HTTP 出口 = 双通道隐患), 故此处只留
    messages 一条; 另加一条反向断言, 防 SessionResponse 又长回 link_enabled。
    """
    a = (_api_get(f"/sessions/{session_id}", timeout=30) or {})
    b = (_api_get(f"/sessions/{session_id}/messages", timeout=30) or {})
    assert (
        "link_enabled" not in a
    ), f"/sessions/{{id}} 不得下发 link_enabled(5.7.5/5.7.6 已废止), 实得 {a.get('link_enabled')}"
    return None, b.get("link_enabled")


def _aggregate_rounds(results: list, checks: list, task_ids: list = None) -> dict:
    """把同一会话的多次发送 send_chat 结果合并为"全量汇总视图", 供 write_test_record 渲染。

    2026-10-03 北京老陈指正"未生成有效测试记录"(根因已定位):
      e2e_helpers 的记录模板是**单任务专用**(以单个 result 渲染全部栏目), 而本用例有5个任务。
      原来只把末个任务 r5 传进 write_test_record, 导致记录严重失真:
        运行耗时 只显示末个任务 7.5s (真实全程72s) / 工具调用链只有末任务1个read(任务1实为5个工具)
        / LLM调用次数 只有末任务2次(全程约14次) / 任务1的多步链路与任务2的魔数证据全部丢失。
      另: write_test_record 的 extra 参数**从不写入文件**(只转交 register_pending_record),
      故此前传的 extra 全部无效, 此处不依赖它。

    合并规则(全部取自真实运行结果, 无任何编造):
      start_time     取首个任务 -> "运行耗时"=全程墙钟, 而非末个任务
      tool_calls     五个任务全部平铺 -> "工具调用链"完整可见
      events/event_types 五个任务合并 -> "SSE事件详情"与"逻辑步数"反映全程
      llm_call_count 五个任务累加     -> 与 verify_token_usage 的 session 级对账一致
      total_steps    五个任务累加
      final_event/task_id/response_text 取末个任务(终态以末个任务为准)
    """
    if not results:
        return {}
    agg = dict(results[-1])
    agg["start_time"] = results[0].get("start_time")
    agg["tool_calls"] = [tc for r in results for tc in r.get("tool_calls", [])]
    agg["events"] = [e for r in results for e in r.get("events", [])]
    agg["event_types"] = [et for r in results for et in r.get("event_types", [])]
    agg["total_steps"] = sum(r.get("total_steps", 0) for r in results)
    agg["llm_call_count"] = sum(r.get("llm_call_count", 0) for r in results)
    agg["has_error"] = any(r.get("has_error", False) for r in results)
    # task_id 取自 /sessions/{id}/tasks: send_chat 返回体(744-764行)根本没有 task_id 键,
    #   直接 r.get("task_id") 只会得到 None(实测记录里五个任务全是 None)。
    _tids = list(task_ids or [])
    agg["rounds"] = [
        {
            "任务序": i + 1,
            "task_id": _tids[i] if i < len(_tids) else None,
            "tools": [t["tool_name"] for t in r.get("tool_calls", [])],
            "llm_calls": r.get("llm_call_count", 0),
            "end_type": assert_stream_ended(r),
            # 每个任务回复都进记录: 记录第2节"LLM回复内容"只渲染末个任务 response,
            # 多次发送 case 下前几个任务的产出(尤其任务2的魔数)会被整段丢掉 — 北京老陈指正"不能只显示最后一次"
            "回复(尾部)": (r.get("response_text", "") or "")[-160:].replace("\n", " ⏎ "),
            **_injection_of(r),
        }
        for i, r in enumerate(results)
    ]
    agg["assertions"] = list(checks)
    return agg


def _injection_of(r: dict) -> dict:
    """取本次 context_overview 的跨任务注入量(与 write_test_record 同字段名)。

    背景: 记录第1节"跨任务注入上下文"字段在 write_test_record:2333-2339 只取
      events 里**第一个** context_overview 就 break —— 单任务 case 成立, 多次发送 case 会失真:
      本用例任务1 是新会话首条消息(注入0), 于是该字段显示"无(本任务单轮/无历史注入)",
      而任务2~5 确有注入, 全部看不到(第三个记录失真点, 由北京老陈指正发现)。
      不改 helper 判定语义(公共基座, 单任务 case 依赖它), 改为在附加信息里给出每个任务准确注入量。
    """
    out = {"注入消息数": 0, "注入tok": 0, "有无注入": "无"}
    for e in r.get("events", []):
        if isinstance(e, dict) and e.get("type") == "context_overview":
            n = e.get("injected_message_count", 0) or 0
            tok = e.get("injected_estimated_tokens", 0) or 0
            out = {
                "注入消息数": n,
                "注入tok": tok,
                "有无注入": f"消息{n}条/≈{tok}tok" if (n or tok) else "无(本次发送首条,无历史)",
            }
            break
    return out


def _ck(checks: list, msg: str) -> None:
    """实时打印每条已通过的断言 —— 2026-10-03 小欧 修证据链缺陷:
    原实现把 CHECK 攒到用例末尾统一打印, 中途断言失败时 stdout 里一条 CHECK 都没有,
    无法判断"失败前哪些已验证通过"。改为 append 即打印。"""
    checks.append(msg)
    print(f"  [CHECK] {msg}", flush=True)


def _force_status(session_id: str, task_id: str, status: str) -> None:
    """把任务行 status 置为指定值 —— 造前置数据(被测的链根计算全程真实执行)"""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("UPDATE chat_tasks SET status=? WHERE task_id=?", (status, task_id))
        conn.commit()
    finally:
        conn.close()


@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p9_08_link_grouping_contract():
    """P9-08: link 分组契约 —— 多步工具链路 / 分组 / 两读点 / 关则新组 / failed 仍并入"""

    from datetime import datetime

    test_start = datetime.now()
    passed = False
    sid = None
    r = {}
    db = {}
    ci = []
    si = []
    dpi = []
    lc = {"errors": [], "tracebacks": []}
    elapsed = 0.0
    error_info = None
    checks = []
    probe = Path(PROBE_TEMPLATE.format(f"{test_start:%m%d%H%M%S}"))
    inputs = []
    rounds = []          # 2026-10-03 五个任务真实结果汇总落盘(见 _aggregate_rounds)
    task_ids = []        # send_chat 返回体无 task_id 键, 从 /sessions/{id}/tasks 取

    try:
        register_pending_record(
            TEST_CASE_ID, TEST_CASE_NAME,
            "", {}, {}, [], [], {"errors": [], "tracebacks": []}, False,
        )
        assert ensure_backend_ready(), "后端未启动(手册6.1)"
        assert SRC_FILE.exists(), f"任务1读取源不存在: {SRC_FILE}"

        in1 = INPUT_R1.format(src=str(SRC_FILE), probe=str(probe), magic=MAGIC)
        inputs.append(in1)
        print(f"\n  [Setup] session 待建, probe={probe.name}")

        # ── 任务1 (link 关): 多步工具链路, 产出含魔数的探测文件 ──
        sid = await create_session()
        assert sid, "建会话失败"
        print(f"  [Setup] session={sid}")

        a0, b0 = _link_read(sid)
        assert b0 is False, \
            f"新会话默认为关闭(唯一读点 messages), 实得 msg={b0}"
        _ck(checks,"新会话link默认关闭(messages 唯一读点)")

        r1 = await send_chat(in1, session_id=sid)
        rounds.append(r1)
        _ck(checks, f"任务1 已发送完成(task_id={task_ids[0] if task_ids else '待取'})")
        # 串行固定间隔: 等上个任务的后端异步收尾落库完成再发下一个(见顶部 JOB_GAP_SECONDS)
        time.sleep(JOB_GAP_SECONDS)
        end1 = assert_stream_ended(r1)
        assert end1 == "final", f"任务1必须成功结束(MUST): {end1}"
        tools1 = [t["tool_name"] for t in r1["tool_calls"]]
        print(f"  [任务1] tools: {tools1}, steps={r1['total_steps']}, "
              f"llm_calls={r1['llm_call_count']}")

        db1 = check_db(sid)
        assert db1["execution_steps_count"] >= 2, \
            f"任务1必须有多步记录(MUST), got {db1['execution_steps_count']}"
        t1i = verify_db_tool_usage(db1, expect_any_tools=list(READ_TOOLS), min_tool_steps=1)
        assert len(t1i) == 0, f"任务1 DB 必须有真实读工具调用(MUST): {t1i}"
        _ck(checks,f"任务1 真实工具链路: tools={tools1}, steps={db1['execution_steps_count']}")

        t1 = _tasks(sid)
        task_ids.append(t1[0][0])
        assert len(t1) == 1, f"应有1个任务, 实得 {t1}"
        root1 = t1[0][1]
        assert root1 == t1[0][0], f"link关时任务1应自为链根(条款4), 实得 {t1[0]}"
        _record_round(1, in1, r1, sid, t1[0][0], test_start, checks, rounds, task_ids)
        print(f"  [记录] 任务1 已落盘: {TEST_CASE_ID}-T1")

        # ── 任务2: link 值随消息携带(与前端真实链路一致), 同时校验唯一读真源出口 ──
        # 2026-10-03 小欧 - 文档[4] 5.7.14: 覆盖"值随消息携带"这条链路。
        #   读回断言必须放在发消息之后 —— 发之前后端还没有新值, 测不出携带是否生效。
        #   PATCH /sessions/{id}/link 已废止, 全5 个任务统一走send_chat(link_enabled=...) 携带。
        in2 = INPUT_R2
        inputs.append(in2)
        r2 = await send_chat(in2, session_id=sid, link_enabled=True)
        rounds.append(r2)
        # 串行固定间隔: 等上个任务的后端异步收尾落库完成再发下一个(见顶部 JOB_GAP_SECONDS)
        time.sleep(JOB_GAP_SECONDS)
        end2 = assert_stream_ended(r2)
        assert end2 == "final", f"任务2必须成功结束(MUST): {end2}"
        tools2 = [t["tool_name"] for t in r2["tool_calls"]]
        print(f"  [任务2] tools: {tools2}, steps={r2['total_steps']}, "
              f"resp={r2['response_text'][:120]}")

        a1, b1 = _link_read(sid)
        assert b1 is True, \
            f"任务2 携带 link_enabled=True 后唯一读点应为True, 实得 msg={b1}"
        _ck(checks,"随消息携带 link_enabled=True 生效: 发消息后 messages 读点读到True")

        # 门2: 链根必须并入任务1 所在组
        t2 = _tasks(sid)
        task_ids.append(t2[1][0])
        assert len(t2) == 2, f"应有2个任务, 实得 {t2}"
        assert t2[1][1] == root1, \
            f"门2: link开时任务2应并入任务1所在组({root1}), 实得 {t2[1]}"
        _ck(checks,f"门2 分组正确: 任务2并入任务1所在组({root1})")

        # 历史注入的真实效果: 核心判据是"答出魔数"(下方 MAGIC 断言)。
        #   2026-10-03 北京老陈指正测试不稳定: 原先额外硬断言"必须调 read 工具",
        #   但模型换用 bash/listdir 等其它工具读同一文件也会被判失败(实测某次报
        #   "读工具调用数0<1", 而该次魔数已答对) —— 用工具名做硬断言属过度约束,
        #   让"用哪个工具读"这种模型自由度过关用例生死。改为只要求"确有工具调用",
        #   工具名单不作约束; 魔数断言才是精准判据。
        db2 = check_db(sid)
        t2i = verify_db_tool_usage(db2, expect_any_tools=None, min_tool_steps=1)
        assert len(t2i) == 0, f"任务2必须真实调用工具(不能凭空答出), 否则说明未实际读取: {t2i}"
        resp2 = r2["response_text"]
        assert MAGIC in resp2, (
            f"任务2必须答出任务1写入的魔数({MAGIC}) —— 说明历史未正确注入或未被使用; 实答: {resp2[:300]}")
        _ck(checks,f"历史注入生效: 任务2未告知路径仍读回魔数({MAGIC})")
        _record_round(2, in2, r2, sid, t2[1][0], test_start, checks, rounds, task_ids)
        print(f"  [记录] 任务2 已落盘: {TEST_CASE_ID}-T2")

        # ── 任务3 (link 关): 自成新组(条款4) ──
        # 2026-10-03 小欧 - PATCH /sessions/{id}/link 已废止(北京老陈定案: 开关只准随消息发出,
        #   严禁独立影响后端), 改由 send_chat(link_enabled=...) 携带, 与前端真实链路一致。
        in3 = INPUT_R3.format(src=str(SRC_FILE))
        inputs.append(in3)
        r3 = await send_chat(in3, session_id=sid, link_enabled=False)
        rounds.append(r3)
        # 串行固定间隔: 等上个任务的后端异步收尾落库完成再发下一个(见顶部 JOB_GAP_SECONDS)
        time.sleep(JOB_GAP_SECONDS)
        end3 = assert_stream_ended(r3)
        assert end3 == "final", f"任务3必须成功结束(MUST): {end3}"
        t3 = _tasks(sid)
        task_ids.append(t3[2][0])
        assert len(t3) == 3, f"应有3个任务, 实得 {t3}"
        assert t3[2][1] != root1, \
            f"条款4: link关时任务3应自成新组(≠{root1}), 实得 {t3[2]}"
        _ck(checks,f"条款4 关link后任务3自成新组({t3[2][1]})")
        _record_round(3, in3, r3, sid, t3[2][0], test_start, checks, rounds, task_ids)
        print(f"  [记录] 任务3 已落盘: {TEST_CASE_ID}-T3")

        # ── 任务4 (link 关): 自成"独立组C" ──
        # 2026-10-03 北京老陈指正蒙人测试(记录第8节暴露): 原设计让任务4(link开)并入任务3所在组,
        #   于是"新口径取最近一条(任务4)"与"旧口径跳过failed的任务4回溯到任务3"**得到同一个链根**,
        #   断言恒成立、根本区分不出新旧口径 —— 等于没验门5。
        #   改为任务4 也走 link 关, 使其自成独立组C, 且 C≠B(任务3的组):
        #     新口径(最近一条任意状态) -> 任务5 并入 组C
        #     旧口径(仅认completed)      -> 跳过failed的任务4, 回溯到任务3 -> 任务5 并入 组B
        #   两者结论不同, 断言才真正有分辨力。
        in4 = INPUT_R4.format(src=str(SRC_FILE))
        inputs.append(in4)
        r4 = await send_chat(in4, session_id=sid, link_enabled=False)
        rounds.append(r4)
        # 串行固定间隔: 等上个任务的后端异步收尾落库完成再发下一个(见顶部 JOB_GAP_SECONDS)
        time.sleep(JOB_GAP_SECONDS)
        end4 = assert_stream_ended(r4)
        assert end4 == "final", f"任务4必须成功结束(MUST): {end4}"
        t4 = _tasks(sid)
        task_ids.append(t4[3][0])
        assert len(t4) == 4, f"应有4个任务, 实得 {t4}"
        assert t4[3][1] == t4[3][0], \
            f"任务4(link关)应自成链根, 实得 {t4[3]}"
        assert t4[3][1] != t3[2][1], (
            f"门5前提: 任务4的组C必须≠任务3的组B, 否则新旧口径结论相同、断言无分辨力; "
            f"实得 C={t4[3][1]} B={t3[2][1]}")
        _ck(checks, f"门5前提: 任务4自成独立组C({t4[3][1]})且≠组B({t3[2][1]})")
        # 落盘放在 _force_status 之前: 此时任务4 刚真实跑完, 状态为 completed;
        # 若放在置failed之后, 记录里会显示 failed, 那是我为门5 人为造的前置, 不是该任务的真实终态。
        _record_round(4, in4, r4, sid, t4[3][0], test_start, checks, rounds, task_ids)
        print(f"  [记录] 任务4 已落盘: {TEST_CASE_ID}-T4")

        # ── 门5(核心): 上一任务(任务4)置 failed, link 开 -> 任务5 仍并入组C ──
        _force_status(sid, t4[3][0], "failed")
        in5 = INPUT_R5.format(src=str(SRC_FILE))
        inputs.append(in5)
        r5 = await send_chat(in5, session_id=sid, link_enabled=True)
        rounds.append(r5)
        end5 = assert_stream_ended(r5)
        assert end5 == "final", f"任务5必须成功结束(MUST): {end5}"
        t5 = _tasks(sid)
        task_ids.append(t5[4][0])
        assert len(t5) == 5, f"应有5个任务, 实得 {t5}"
        # 2026-10-03 小欧 修测试自身BUG: 原断言查 t4(任务4结束时的内存快照),
        # 而 _force_status 只改数据库, 快照不会自动刷新 -> 误报"前置未生效"。
        # 必须查改库之后重新取到的 t5。实测证据: 库中任务4 status=failed, 任务5 root 仍并入该组, 门5 本身是对的。
        assert t5[3][2] == "failed", \
            f"门5前置未生效: 任务4的failed状态应已落库, 实得 {t5[3][2]}"
        assert t5[4][1] == t4[3][1], (
            f"门5(核心): 上一任务为 failed 时任务5仍应并入组C({t4[3][1]}), 实得 {t5[4]}")
        assert t5[4][1] != t3[2][1], (
            f"门5(核心): 任务5链根绝不能是组B({t3[2][1]}) —— 若等于它说明退回旧口径"
            f"(仅认 completed 而跳过 failed 的任务4)")
        _ck(checks, f"门5 任意状态: 任务4=failed时任务5仍并入组C({t4[3][1]}), 未回溯到组B({t3[2][1]})")
        _record_round(5, in5, r5, sid, t5[4][0], test_start, checks, rounds, task_ids)
        print(f"  [记录] 任务5 已落盘: {TEST_CASE_ID}-T5")

        # ── 收尾: DB / 一致性 / 步骤合理性 / 日志 / prompt ──
        db = check_db(sid)
        assert db["session_exists"], "session必须存在于DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST): {db.get('is_valid')}"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"

        r = r5
        elapsed = sum(x.get("total_time_ms", 0) for x in rounds) / 1000.0
        ci = verify_consistency(r5, sid)
        assert len(ci) == 0, f"SSE-DB一致性失败(MUST): {ci}"

        si = verify_steps(r5, sid)
        assert len(si) == 0, f"步骤合理性失败: {si}"

        lc = check_logs(test_start, sid, r5.get("user_msg_id"))
        filtered = filter_safety_errors(lc["errors"])
        if filtered["safety_errors"]:
            print(f"  [INFO] 安全类错误(预期): {len(filtered['safety_errors'])}")
        assert len(filtered["other_errors"]) == 0, \
            f"日志不应有ERROR(MUST): {filtered['other_errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, "日志不应有Traceback(MUST)"

        print_report(
            TEST_CASE_ID, TEST_CASE_NAME, r5, db, lc,
            ci, si, True, elapsed,
            extra={
                "Rounds": 5,
                "R1 tools": tools1,
                "R2 tools": tools2,
                "Magic": MAGIC,
                "Checks": len(checks),
            },
        )
        passed = True

    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"  [FAIL] 异常: {error_info[:800]}")
        if sid:
            lc = check_logs(test_start, sid)
        raise
    finally:
        cleanup(session_id=sid, test_files=[probe])
        # 2026-10-03 北京老陈指正"未生成有效测试记录": 落盘五个任务汇总视图,
        # 否则记录只反映末个任务(耗时/工具链/LLM次数全部失真)。详见 _aggregate_rounds。
        # extra 一并落盘(记录第8节"附加信息"): 带任务明细与逐条已验证断言,
        # 使记录能自证"到底验了哪8条、每个任务各调了什么工具"。数据全部取自真实运行。
        _agg = _aggregate_rounds(rounds, checks, task_ids)
        # 本用例确有跨任务注入, 但记录第1节该字段只取第一个 context_overview(任务1, 注入0),
        # 故此处补一行汇总, 与每个任务明细对照, 避免读者误以为全用例无注入。
        _max_inj = max((d.get("注入消息数", 0) for d in _agg.get("rounds", [])),
                       default=0)
        write_test_record(
            TEST_CASE_ID, TEST_CASE_NAME, "\n\n----\n\n".join(inputs),
            _agg, db, ci, si, lc, passed,
            elapsed,
            extra={
                "任务总数": len(rounds),
                "任务明细(task/工具链/终态/注入量)": _agg.get("rounds", []),
                "已验证断言": list(checks),
                "跨任务注入说明": (
                    f"第1节'跨任务注入上下文'字段因只取首个 context_overview(任务1注入0)显示'无'; "
                    f"本用例实际最大注入 {_max_inj} 条消息, 逐任务明细见上"
                ),
                "消息条数口径": (
                    f"本用例连续发送 {len(rounds)} 条用户消息、产生 {len(rounds)} 个任务、"
                    f"{len(rounds)} 条AI回复(总消息 {len(rounds) * 2} 条)。"
                    f"注意第5节'消息数量'字段取自 check_db 的 messages_count = chat_user_message 表行数, "
                    f"即**只数用户消息**({len(rounds)}), 不含AI回复, 勿误读为总消息数"
                ),
                "历史注入魔数": MAGIC,
                "注入探测文件": probe.name,
                "覆盖验收门": "门2 分组 / 门3 会话隔离 / 门5 任意状态 / 条款4 关则新组",
            },
            dpi=dpi, error_info=error_info,
        )