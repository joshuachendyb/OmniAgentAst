# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 - 新建: 8.6 一拆三——stream_reader.py 历史加载下沉。整份搬入
#   _parse_tool_calls/_parse_observations/_load_previous_messages 三函数(逐字复制零改动),
#   与 storage.py 的 fetch_session_user_message_pairs 做邻居(复用优先)。仅改导入归属, 业务逻辑一字不改,
#   删 stream_reader.py 空壳时不留垫片(禁 backward)。
# 2026-10-01 小欧 - 解 [1] E3: load_execution_steps 调用补传 task_id(p["pair_task_id"]), 与 message_service/execution_stream 同源。本函数是"喂 LLM 的历史", 安全性依赖 fetch 的 upper_id 严格上界(排除本任务自身已实时落库的步骤, 防自我回灌), 补 task_id 只收窄不放开, 不改变该边界语义
# 2026-10-03 - 小欧 - 文档[4] 5.7 项9: _load_previous_messages 删 context_link_mode 形参与二次白名单;
#   三堂会审 S1/S2: 两种兜底退化(仅下界=自我回灌 / 仅上界=越链灌入)均不安全, 塌缩为双边界齐全才装历史。
# 2026-10-04 - 小欧 - 字段精简(文档[8]第六章第0步): :53/:139 删 llm_data_text 兜底——前端零引用,
#   实测 2306 条 tool_result 的 data_text 空值数为 0(兜底从未触发), 删后回放零退化 — 小欧-2026-10-04
# 2026-10-07 - 小欧 - 修复: FC对按step(轮次)分桶还原。原实现把整个任务(可含49轮)的全部action step
#   的tool_calls平铺进一条assistant, 再把全部observation extend到其后, 产出
#   `assistant(62个tool_calls) → tool×62`——语义变成"模型在同一次响应里并发发了62个工具调用",
#   与运行时"每轮一条assistant + 该轮tool"的真实结构完全不同, 且tool消息占历史91%、assistant仅5条,
#   注入给LLM的历史严重失真。改法: 新增 _collect_turns 按step分桶, 每轮产assistant(该轮tool_calls)
#   + 该轮tool交错; 任务最终答复(ai_content)独立成一条不带tool_calls的assistant。
#   同时合并原_parse_tool_calls/_parse_observations为_collect_turns: 原来两者各自json.loads +
#   各自预扫描同一份steps(孤儿tool_call的_obs_ids与孤儿truncated_output的_action_ids互为逆条件),
#   拆两处遍历必然漂移, 合并后配对一致性由构造保证。原两函数无外部调用方, 不保留兼容垫片。
"""
history_loader — 会话历史加载(多轮上下文DB读取)

小健 2026-09-05 自 stream_reader.py 搬迁: 历史加载(DB IO)与 SSE 转发各归其位(SRP);
与 storage.py 同层邻居, 复用 fetch_session_user_message_pairs(chat_messages 只写铁律同一来源)。
"""
import json
from typing import Any, Dict, List, Optional

from app.db import db
from app.logger import logger
from app.utils.json_utils import safe_json_dumps  # steps序列化为JSON串供多轮上下文 — 小欧 2026-07-14
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14
from app.services.chat.storage import fetch_session_user_message_pairs  # 北京老陈 2026-08-22: 替代 chat_messages 读取(只写铁律)


def _collect_turns(msg_id: int, exec_steps_json: str) -> Dict[int, Dict[str, List]]:
    """按 step(轮次)分桶收集一个任务的 FC 对 — 小欧 2026-10-07 新建(替代 _parse_tool_calls+_parse_observations)

    返回 {step号: {"tool_calls": [...], "observations": [...]}}, 调用方按 sorted(turns) 逐轮展开。
    分四步: ①预扫 observation 建 _obs_ids(丢弃无配对的孤儿 tool_call, 防 OpenAI 400)
            ②预扫 action 建 _action_ids(丢弃无配对的孤儿 truncated_output observation)
            ③遍历 action 按 step 分桶收 tool_calls  ④遍历 observation 按 step 分桶收 tool 消息
    兼容: 新 action(tools数组) + 老 action_tool(单工具); 老 observation content 回退同 step 用
          _legacy_seq 补序号保证 tool_call_id 唯一。
    """
    try:
        exec_steps = json.loads(exec_steps_json)
    except Exception:
        return {}
    if not isinstance(exec_steps, list):
        logger.warning(f"[_collect_turns] exec_steps非list, 跳过: {type(exec_steps)}")
        return {}

    turns: Dict[int, Dict[str, List]] = {}

    def _bucket(step_no: int) -> Dict[str, List]:
        return turns.setdefault(
            step_no, {"tool_calls": [], "observations": [], "thought": "", "reasoning": ""}
        )

    # ⓪ 收集每轮思考(对齐运行时 add_assistant_tool_call(content=llm_content, reasoning=llm_reasoning))
    #   原实现完全不读 thought step, 还原出的 assistant 只有空 content, 模型看不到决策轨迹。
    #   DB thought step: thought/content = llm_content(正文短句), reasoning = llm_reasoning(推理链)
    #   实测(2026-10-07): thought 非空 8/48 共 200 字符, reasoning 非空 48/48 共 37754 字符。
    #   两字段分开存, 与运行时 message_builder 的 assistant 结构一致(content + reasoning)。
    for _st in exec_steps:
        if not isinstance(_st, dict) or _st.get("type") != "thought":
            continue
        _b = _bucket(_st.get("step", 0))
        if not _b["thought"]:
            _b["thought"] = str(_st.get("thought") or _st.get("content") or "").strip()
        if not _b["reasoning"]:
            _b["reasoning"] = str(_st.get("reasoning") or "").strip()

    # ① 预扫描 observation 的 FC id 集合 — 仅保留与其配对的 action tool_call(小沈 2026-08-29 修复)
    _obs_ids: set = set()
    for _st in exec_steps:
        if not isinstance(_st, dict) or _st.get("type") != "observation":
            continue
        _os = _st.get("step", 0)
        _tr = _st.get("tool_result")
        if isinstance(_tr, list):
            for _oi, _el in enumerate(_tr):
                if not isinstance(_el, dict):
                    continue
                if not (_el.get("data_text") or ""):
                    continue
                _obs_ids.add(f"call_{msg_id}_{_os}_{_oi}")
        else:
            _oc = _st.get("content", "")
            if _oc:
                _obs_ids.add(f"call_{msg_id}_{_os}_{0}")

    # ② 预扫描 action 的 FC id 集合 — 供孤儿 truncated_output observation 跳过(小健 2026-08-18 修复)
    _action_ids: set = set()
    for _st in exec_steps:
        if not isinstance(_st, dict) or _st.get("type") != "action":
            continue
        _tools = _st.get("tools") or []
        if isinstance(_tools, list):
            for _i in range(len(_tools)):
                _action_ids.add(f"call_{msg_id}_{_st.get('step', 0)}_{_i}")

    # ③ 遍历 action — 按 step 分桶收集 tool_calls
    _step_count: Dict[int, int] = {}   # 兼容老 action_tool: 同 step 多工具追加组内序号
    _orphan_skipped = 0
    for step in exec_steps:
        if not isinstance(step, dict):
            continue
        _type = step.get("type", "")
        if _type not in ("action", "action_tool"):   # 兼容老数据 action_tool
            continue
        _s = step.get("step", 0)
        if _type == "action":
            tools = step.get("tools") or []
            if not isinstance(tools, list):
                continue
            for _i, t in enumerate(tools):
                if not isinstance(t, dict):
                    continue
                _tcid = f"call_{msg_id}_{_s}_{_i}"
                if _tcid not in _obs_ids:   # 丢弃无配对 observation 的孤儿 tool_call
                    _orphan_skipped += 1
                    continue
                _params = t.get("params") or {}
                try:
                    arguments = json.dumps(_params, ensure_ascii=False)
                except (TypeError, ValueError):
                    arguments = "{}"
                _bucket(_s)["tool_calls"].append({
                    "id": _tcid,
                    "type": "function",
                    "function": {"name": t.get("tool", ""), "arguments": arguments},
                })
        else:  # 老 action_tool: 逐个 step 一工具, 同 step 用 _step_count 补序号, 与老 observation 对齐
            _c = _step_count.get(_s, 0)
            _step_count[_s] = _c + 1
            _tcid = f"call_{msg_id}_{_s}_{_c}"
            if _tcid not in _obs_ids:
                continue
            try:
                arguments = json.dumps(step.get("tool_params", {}), ensure_ascii=False)
            except (TypeError, ValueError):
                arguments = "{}"
                logger.warning(f"[_collect_turns] tool_params不可序列化, 降级为{{}}: {step.get('tool_name')}")
            _bucket(_s)["tool_calls"].append({
                "id": _tcid,
                "type": "function",
                "function": {"name": step.get("tool_name", ""), "arguments": arguments},
            })

    # ④ 遍历 observation — 按 step 分桶收集 tool 消息
    _legacy_seq: Dict[int, int] = {}  # 老格式 content 回退分支同 step 多 observation 时 tool_call_id 唯一
    for step in exec_steps:
        if not isinstance(step, dict) or step.get("type") != "observation":
            continue
        _s = step.get("step", 0)
        tool_result = step.get("tool_result")
        if isinstance(tool_result, list) and tool_result:
            for _i, el in enumerate(tool_result):
                if not isinstance(el, dict):
                    continue
                content = el.get("data_text") or ""
                if not content:
                    continue
                _cum = el.get("tool_name", "") == "truncated_output"
                _cid = f"call_{msg_id}_{_s}_{_i}"
                if _cum and _cid not in _action_ids:   # 孤儿截断观测跳过, 防 LLM 历史不合法
                    continue
                _bucket(_s)["observations"].append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": _cid,
                })
        else:
            content = step.get("content", "")
            if content:
                _seq = _legacy_seq.get(_s, 0)
                _legacy_seq[_s] = _seq + 1
                _bucket(_s)["observations"].append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": f"call_{msg_id}_{_s}_{_seq}",
                })

    # 只保留有 action tool_calls 的轮次。
    #   运行时 conversation_history 只在 _append_observation(有 action) 时 append assistant,
    #   故"只有 thought 没有 action"的轮次(如 step=40)在运行时根本不入历史, 这里同样丢弃,
    #   否则会产出孤立的 assistant(tool_calls=[]) 破坏 FC 配对。
    for _k in [k for k, v in turns.items() if not v["tool_calls"]]:
        turns.pop(_k, None)
    if _orphan_skipped > 0:
        logger.debug(f"[_collect_turns] 跳过{_orphan_skipped}个无配对observation的孤儿tool_call(msg_id={msg_id})")
    return turns


def _load_previous_messages(session_id: str, context_root_task_id: Optional[str] = None,
                             upper_message_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """从DB加载会话历史消息 — 小健 2026-06-17 委托db层，消除SQLite越界
    小欧 2026-06-25: 抽取 FC 对解析消除嵌套try/except
    小欧 2026-07-14: 从chat_message_steps组装
    2026-10-07 小欧: FC 对还原改按 step(轮次)分桶(见 _collect_turns), 每轮 assistant+该轮 tool 交错,
      最终答复独立成条 — 替代原"全任务塌成一条 assistant"
    2026-08-16 - 小欧 - S1(10.1.4⑤): 按任务链范围过滤——
      2026-10-02 小欧 - 文档[4] 5.7 项9: 链模式形参废止，开关改由 context_root_task_id 承载——
        None(link 关): 直接返回[](从零,不带历史,防误灌,等价原 independent);
        非空(link 开): 沿"链根任务首条user消息id → 本任务用户消息id前"范围加载(BETWEEN 下界 AND 上界),链外消息不进LLM;
      upper_message_id=本任务user消息id(上界,由 orchestrator _user_msg_id 闭包注入;设计1643 SQL语义要求,签名补充该参)"""
    # link 关闭(链根为空)即无链可沿: 不装任何历史 — 小欧 2026-10-02
    if not context_root_task_id:
        return []
    try:
        with db.get_conn("chat") as conn:
            # 链根首条user消息id = chat_tasks(chain_root).user_message_id 起
            _r = conn.execute(
                "SELECT user_message_id FROM chat_tasks WHERE task_id=?",
                (context_root_task_id,),
            ).fetchone()
            _lower_id = _r["user_message_id"] if (_r and _r["user_message_id"]) else None
            # 2026-10-03 小欧 三堂会审 S1/S2: 链范围须双边界齐全才装历史, 否则 fail-closed。
            #   原两种兜底都不安全(仅下界=自我回灌; 仅上界=越链灌入), 故全部删除。
            if _lower_id is None or upper_message_id is None:
                logger.warning(
                    f"[SSE] linked 链范围边界缺失(lower={_lower_id}, upper={upper_message_id}), "
                    f"按不装历史处理(session={session_id}, root={context_root_task_id})"
                )
                return []
            # 2026-08-17 - 小健 - 三堂会审-E1: 改 id<upper(不含本任务 user 消息), 语义对齐"本任务前"
            # 北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 改读 chat_user_message+chat_tasks
            pairs = fetch_session_user_message_pairs(conn, session_id, lower_id=_lower_id, upper_id=upper_message_id)
            messages = []
            for p in pairs:
                messages.append({"role": "user", "content": p["user_content"] or ""})
                ai_id = p["ai_message_id"]
                if ai_id is None:
                    continue
                # 2026-10-01 小欧: 补传 task_id(解 [1] E3), 与 message_service/execution_stream 同源。
                #   本函数是"喂 LLM 的历史", 安全性依赖 fetch 的 upper_id < 严格上界(排除本任务自身
                #   已实时落库的步骤, 防自我回灌); 补 task_id 只收窄不放开, 不改变该边界语义。
                steps = load_execution_steps(conn, ai_id, p.get("pair_task_id"))
                steps_json = safe_json_dumps(steps) if steps else None
                # 2026-10-07 小欧: 按 step(轮次)分桶还原 FC 对, 每轮一条 assistant + 该轮 tool 交错。
                #   任务最终答复(ai_content)独立成一条**不带 tool_calls** 的 assistant, 还原真实语义。
                if steps_json:
                    turns = _collect_turns(ai_id, steps_json)
                    for _step_no in sorted(turns):
                        _turn = turns[_step_no]
                        _a: Dict[str, Any] = {
                            "role": "assistant",
                            "content": _turn["thought"],
                            "tool_calls": _turn["tool_calls"],
                        }
                        # 2026-10-07 小欧: reasoning 还原为独立字段, 不并入 content。
                        #   运行时 add_assistant_tool_call(content=llm_content, reasoning=llm_reasoning) 是
                        #   两个独立字段, prepare_messages_for_llm 再把 reasoning 转 reasoning_content 发给
                        #   API; 并入 content 会让模型只见混合文本、丢失推理区, 结构也与运行时不一致。
                        if _turn["reasoning"]:
                            _a["reasoning"] = _turn["reasoning"]
                        messages.append(_a)
                        messages.extend(_turn["observations"])
                # 最终答复独立成条(无 tool_calls), 还原"末轮 answer"的真实形态
                _final = p["ai_content"] or ""
                if _final:
                    messages.append({"role": "assistant", "content": _final})
        return messages
    except Exception as e:
        # 【修复】DB异常加日志而非静默吞掉 — chendyg 2026-06-26
        logger.warning(f"[SSE] 加载会话历史失败(session={session_id}): {e}")
        return []