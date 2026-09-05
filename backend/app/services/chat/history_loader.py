# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 - 新建: [7]8.6 一拆三——stream_reader.py 历史加载下沉。整份搬入
#   _parse_tool_calls/_parse_observations/_load_previous_messages 三函数(逐字复制零改动),
#   与 storage.py 的 fetch_session_user_message_pairs 做邻居(复用优先)。仅改导入归属, 业务逻辑一字不改,
#   删 stream_reader.py 空壳时不留垫片(禁 backward)。
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


def _parse_tool_calls(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取tool_calls列表
    小欧 2026-06-25 从_load_previous_messages提取
    小欧 2026-07-18 F4修复: try收窄到单步, 单步参数异常不株连整批
    2026-08-18 小欧 §10.3.5(3)④: 兼容新 action(tools数组) + 老 action_tool(单工具)"""
    try:
        exec_steps = json.loads(exec_steps_json)
    except Exception:
        return []
    if not isinstance(exec_steps, list):
        logger.warning(f"[_parse_tool_calls] exec_steps非list, 跳过: {type(exec_steps)}")
        return []
    tool_calls = []
    _step_count: Dict[int, int] = {}   # 2026-08-18 小欧 兼容老 action_tool: 同 step 多工具追加组内序号
    # bug#9修复(小沈 2026-08-29): 预扫描 observation 的 FC id 集合, 仅保留与 observation 配对的 action tool_call;
    # 防 action/observation 工具数不一致→孤儿 tool_call(assistant 有 id 但无对应 tool 消息)→OpenAI 400
    _obs_ids: set = set()
    _orphan_skipped = 0
    for _st in exec_steps:
        if not isinstance(_st, dict) or _st.get("type") != "observation":
            continue
        _os = _st.get("step", 0)
        _tr = _st.get("tool_result")
        if isinstance(_tr, list):
            for _oi, _el in enumerate(_tr):
                if not isinstance(_el, dict):
                    continue
                if not (_el.get("data_text") or _el.get("llm_data_text") or ""):
                    continue
                _obs_ids.add(f"call_{msg_id}_{_os}_{_oi}")
        else:
            _oc = _st.get("content", "")
            if _oc:
                _obs_ids.add(f"call_{msg_id}_{_os}_{0}")
    for step in exec_steps:
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
                if _tcid not in _obs_ids:   # bug#9: 丢弃无配对 observation 的孤儿 tool_call
                    _orphan_skipped += 1
                    continue
                _name = t.get("tool", "")
                _params = t.get("params") or {}
                try:
                    arguments = json.dumps(_params, ensure_ascii=False)
                except (TypeError, ValueError):
                    arguments = "{}"
                tool_calls.append({
                    "id": _tcid,
                    "type": "function",
                    "function": {"name": _name, "arguments": arguments},
                })
        else:  # 老 action_tool: 逐个 step 一工具, 同 step 用 _step_count 补序号, 与老 observation 对齐
            _c = _step_count.get(_s, 0)
            _step_count[_s] = _c + 1
            _tcid = f"call_{msg_id}_{_s}_{_c}"
            if _tcid not in _obs_ids:   # bug#9: 丢弃无配对 observation 的孤儿 tool_call
                continue
            try:
                arguments = json.dumps(step.get("tool_params", {}), ensure_ascii=False)
            except (TypeError, ValueError):
                arguments = "{}"
                logger.warning(f"[_parse_tool_calls] tool_params不可序列化, 降级为{{}}: {step.get('tool_name')}")
            tool_calls.append({
                "id": _tcid,
                "type": "function",
                "function": {"name": step.get("tool_name", ""), "arguments": arguments},
            })
    if _orphan_skipped > 0:
        logger.debug(f"[_parse_tool_calls] 跳过{_orphan_skipped}个无配对observation的孤儿tool_call(msg_id={msg_id})")
    return tool_calls


def _parse_observations(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取observation tool消息 — 小欧 2026-06-25 从_load_previous_messages提取
    小欧 2026-07-10 M-12: content已扁平到顶层，不再从observation包装读取
    2026-08-18 小欧 §10.3.5(3)④: 直接读 tool_result 数组(新格式) + 老 content 回退
    2026-08-18 小健 Bug#8: 截断场景的 truncated_output observation 无对应 action(运行时 id 为上次
      assistant 的 _retry_tc_id, 无法从 step_json 恢复), 回放一律生成孤儿 tool 消息 → 跳过, 防 OpenAI 历史不合法"""
    try:
        exec_steps = json.loads(exec_steps_json)
        # 预扫描全部对应 action 的 FC id, 供孤儿截断观测跳过
        _action_ids = set()
        for _st in exec_steps:
            if not isinstance(_st, dict):
                continue
            if _st.get("type") != "action":
                continue
            _tools = _st.get("tools") or []
            if isinstance(_tools, list):
                for _i in range(len(_tools)):
                    _action_ids.add(f"call_{msg_id}_{_st.get('step',0)}_{_i}")
        observations = []
        _legacy_seq: Dict[int, int] = {}  # 2026-08-19 小欧 Bug#: 老格式content回退分支同step多observation时tool_call_id唯一
        for step in exec_steps:
            if not isinstance(step, dict) or step.get("type") != "observation":
                continue
            _s = step.get("step", 0)
            tool_result = step.get("tool_result")
            if isinstance(tool_result, list) and tool_result:
                # 新格式: 直接读 tool_result 数组（每元素 tool_call_id 与 _parse_tool_calls 同 _s/_i 对齐）
                for _i, el in enumerate(tool_result):
                    if not isinstance(el, dict):
                        continue
                    content = el.get("data_text") or el.get("llm_data_text") or ""
                    if not content:
                        continue
                    _cum = el.get("tool_name", "") == "truncated_output"
                    _cid = f"call_{msg_id}_{_s}_{_i}"
                    # Bug#8: 截断观测量接管回放孤儿(无对应 action assistant), 跳过防 LLM 历史不合法
                    if _cum and _cid not in _action_ids:
                        continue
                    observations.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": _cid,
                    })
            else:
                # 2026-08-18 小欧 兼容老数据: 旧 ObservationStep 以 content(summary) 承载单次结果
                content = step.get("content", "")
                if content:
                    _seq = _legacy_seq.get(_s, 0)
                    _legacy_seq[_s] = _seq + 1
                    observations.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": f"call_{msg_id}_{_s}_{_seq}",
                    })
        return observations
    except Exception:
        return []


def _load_previous_messages(session_id: str, context_link_mode: str = "independent",
                            context_root_task_id: Optional[str] = None,
                            upper_message_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """从DB加载会话历史消息 — 小健 2026-06-17 委托db层，消除SQLite越界
    小欧 2026-06-25: 抽取_parse_tool_calls/_parse_observations消除嵌套try/except
    小欧 2026-07-14: 从chat_message_steps组装
    2026-08-16 - 小欧 - S1(10.1.4⑤): 按任务链范围过滤——
      independent(新任务,默认): 直接返回[](从零,不带链上历史,防误灌);
      linked(续聊): 沿"链根任务首条user消息id → 本任务用户消息id前"范围加载(BETWEEN 下界 AND 上界),链外消息不进LLM;
      upper_message_id=本任务user消息id(上界,由 orchestrator _user_msg_id 闭包注入;设计1643 SQL语义要求,签名补充该参)"""
    # S1 判断兜底(10.1.4⑧)：非法/缺失值由 orchestrator 已归一为 independent；此处二次兜底(仅接受 linked/independent)
    if context_link_mode not in ("linked", "independent"):
        context_link_mode = "independent"
    if context_link_mode == "independent":
        return []
    try:
        with db.get_conn("chat") as conn:
            # linked: 按链根范围过滤。链根首条user消息id = chat_tasks(chain_root).user_message_id 起
            _lo = context_root_task_id  # 链根task_id(=context_root_task_id 自身或其根)
            _lower_id = None
            if _lo:
                _r = conn.execute(
                    "SELECT user_message_id FROM chat_tasks WHERE task_id=?",
                    (_lo,),
                ).fetchone()
                if _r and _r["user_message_id"]:
                    _lower_id = _r["user_message_id"]
            if _lower_id is not None and upper_message_id is not None:
                # 设计1643: 链根首消息id → 本任务user消息id"前"(链外消息不进LLM)
                # 2026-08-17 - 小健 - 三堂会审-E1修复: 原 BETWEEN lo AND upper 含上界,
                #   把本任务自身的 user 消息(id=upper)也装入上下文, 与本次 user_input 重复;
                #   改 id < upper(不含本任务 user 消息), 语义对齐"本任务前"
                # 北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 改读 chat_user_message+chat_tasks(复用 fetch_session_user_message_pairs)
                pairs = fetch_session_user_message_pairs(conn, session_id, lower_id=_lower_id, upper_id=upper_message_id)
            elif _lower_id is not None:  # 链根存在但无上界(异常兜底): 仅下界过滤
                pairs = fetch_session_user_message_pairs(conn, session_id, lower_id=_lower_id)
            else:  # 链根无 user_message_id(异常兜底)时退化为按会话加载, 防回退丢历史的退化
                logger.warning(f"[SSE] linked 链根 {_lo} 无 user_message_id, 退化为按会话加载(session={session_id})")
                pairs = fetch_session_user_message_pairs(conn, session_id)
            messages = []
            for p in pairs:
                messages.append({"role": "user", "content": p["user_content"] or ""})
                ai_id = p["ai_message_id"]
                if ai_id is None:
                    continue
                steps = load_execution_steps(conn, ai_id)
                steps_json = safe_json_dumps(steps) if steps else None
                tool_calls = _parse_tool_calls(ai_id, steps_json) if steps_json else []
                if tool_calls:
                    messages.append({"role": "assistant", "content": p["ai_content"] or "", "tool_calls": tool_calls})
                else:
                    messages.append({"role": "assistant", "content": p["ai_content"] or ""})
                if steps_json:
                    messages.extend(_parse_observations(ai_id, steps_json))
        return messages
    except Exception as e:
        # 【P1-14修复】DB异常加日志而非静默吞掉 — chendyg 2026-06-26
        logger.warning(f"[SSE] 加载会话历史失败(session={session_id}): {e}")
        return []