# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 小欧 - _load_previous_messages改为从chat_message_steps组装(load_execution_steps), 多轮上下文读取新表
# 2026-07-18 小欧 - #30 fix: _read_stream排空后复查len(buffer.event_log),防done前追加丢事件
# 2026-07-18 小欧 - F4 fix: _parse_tool_calls try收窄到单步, 单步参数异常不株连整批
# 2026-07-23 小欧 - log_and_print统一: print(_msg); logger.info(_msg)替换为log_and_print(_msg), 导入log_and_print; TASK_END消息追加时间串
# 2026-07-30 - 小欧 - 后端卡死根因修复: cond.wait() 加 60s 超时(asyncio.wait_for)+超时后重检 buffer.done; 防止 SSE 消费者因 cond 永远不被 notify 而永久挂起占死 HTTP 连接
# 2026-08-09 - 小欧 - TASK_END 追加真实累计token用量 usage_tokens=prompt_tokens=..,completion_tokens=..,total_tokens=..(读agent.accumulated_usage) 及 total_steps=N 总步骤数; steps 统计剔除 usage 类型计数(原 usage=N 恒等llm_calls 为 usage step 计数非 token, 曾误导读数)
# 2026-08-09 - 小欧 - P3修正(见doc-8月优化修复代码三堂会审报告v1.1): total_steps 排除项由仅"usage"扩为非业务MetaStep集合
#   (paused/resumed/retrying/cancelled/authorization_required/start + usage),与"Meta步骤非业务步骤"注释自洽;
#   业务步骤(chunk/action/thought/observation/final/error)不计入排除不误伤; total在pop之后计算。ast语法✓
# 2026-08-14 - 小欧 - 改名名实相符: stream.py → stream_reader.py(实为SSE流运行器/消费者 stream_reader; "stream"过宽且与api/v1/chat/execution_stream语义重叠)
# 2026-08-16 - 小欧 - S1(10.1.4⑤): _load_previous_messages 加 context_link_mode/context_root_task_id/upper_message_id 参数+
#   按任务链范围过滤(BETWEEN 链根首条user消息id AND 本任务user消息id); independent新任务直接返回[](从零),链外消息不进LLM
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   E1: _load_previous_messages 原 BETWEEN lo AND upper 含上界, 把本任务自身 user 消息(id=upper)也装入上下文与
#       本次 user_input 重复; 改 `id>=lo AND id<upper`(不含本任务user消息), 语义对齐"本任务前"。
#   PARALLEL: _parse_tool_calls/_parse_observations 的 tool_call/observation id 追加 step 值组内序号(_c),
#       解决一轮内并行多工具同 step 致 call_{msg}_{step} 重复 → 历史回放 FC 配对错乱; 两函数同规则(_step_count)
#       保证 assistant.tool_calls 与对应 tool 消息 tool_call_id 对齐。经数据实测3遍: 空content observation 被跳过
#       时该工具无响应(非错位), tc/obs id 严格配对无交叉错配。
# 2026-08-18 小欧 - §10.3.5(3)④: _parse_tool_calls 兼容 action(tools数组)+老 action_tool(单工具); _parse_observations 读 tool_result 数组+老 content 回退
# 2026-08-18 - 小健 - 三堂会审 Bug#8: _parse_observations 预扫描 action 的 FC id 集合(_action_ids), 截断场景 truncated_output observation 无对应 action(运行时 id 不可恢复)回放生成孤儿 tool 消息→OpenAI历史不合法, 跳过防非法; _log_task_end 注释同步(P1后chunk不入steps)
"""
stream_reader — SSE流运行器（消费者）

北京老陈 2026-07-12: 将原 run_sse_stream（生产者+消费者合一）拆为：
- agent_runner.run_agent_in_background: 生产者（后台运行 agent，写事件缓冲）
- 本文件 stream_reader: 消费者（从 agent_streams[task_id] 缓冲按 seq 读取并转发 SSE）

小欧 2026-07-10 从 react_sse_wrapper/run_sse_stream.py 移入
"""

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional

from app.db import db
from app.services.task.task_state import agent_streams
from app.logger import logger, log_and_print
from app.utils.sse_formatter import format_agent_sse
from app.utils.json_utils import safe_json_dumps  # steps序列化为JSON串供多轮上下文 — 小欧 2026-07-14
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14


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
                _name = t.get("tool", "")
                _params = t.get("params") or {}
                try:
                    arguments = json.dumps(_params, ensure_ascii=False)
                except (TypeError, ValueError):
                    arguments = "{}"
                tool_calls.append({
                    "id": f"call_{msg_id}_{_s}_{_i}",
                    "type": "function",
                    "function": {"name": _name, "arguments": arguments},
                })
        else:  # 老 action_tool: 逐个 step 一工具, 同 step 用 _step_count 补序号, 与老 observation 对齐
            _c = _step_count.get(_s, 0)
            _step_count[_s] = _c + 1
            try:
                arguments = json.dumps(step.get("tool_params", {}), ensure_ascii=False)
            except (TypeError, ValueError):
                arguments = "{}"
                logger.warning(f"[_parse_tool_calls] tool_params不可序列化, 降级为{{}}: {step.get('tool_name')}")
            tool_calls.append({
                "id": f"call_{msg_id}_{_s}_{_c}",
                "type": "function",
                "function": {"name": step.get("tool_name", ""), "arguments": arguments},
            })
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
                    observations.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": f"call_{msg_id}_{_s}_0",
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
                rows = conn.execute(
                    "SELECT id, role, content FROM chat_messages "
                    "WHERE session_id=? AND id >= ? AND id < ? ORDER BY id ASC",
                    (session_id, _lower_id, upper_message_id),
                ).fetchall()
            elif _lower_id is not None:  # 链根存在但无上界(异常兜底): 仅下界过滤
                rows = conn.execute(
                    "SELECT id, role, content FROM chat_messages "
                    "WHERE session_id=? AND id>=? ORDER BY id ASC",
                    (session_id, _lower_id),
                ).fetchall()
            else:  # 链根无 user_message_id(异常兜底)时退化为按会话加载, 防回退丢历史的退化
                logger.warning(f"[SSE] linked 链根 {_lo} 无 user_message_id, 退化为按会话加载(session={session_id})")
                rows = conn.execute(
                    "SELECT id, role, content FROM chat_messages "
                    "WHERE session_id=? ORDER BY id ASC",
                    (session_id,),
                ).fetchall()
            messages = []
            for msg_id, role, content in rows:
                if role == "user":
                    messages.append({"role": "user", "content": content or ""})
                elif role == "assistant":
                    steps = load_execution_steps(conn, msg_id)
                    steps_json = safe_json_dumps(steps) if steps else None
                    tool_calls = _parse_tool_calls(msg_id, steps_json) if steps_json else []
                    if tool_calls:
                        messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
                    else:
                        messages.append({"role": "assistant", "content": content or ""})
                    if steps_json:
                        messages.extend(_parse_observations(msg_id, steps_json))
        return messages
    except Exception as e:
        # 【P1-14修复】DB异常加日志而非静默吞掉 — chendyg 2026-06-26
        logger.warning(f"[SSE] 加载会话历史失败(session={session_id}): {e}")
        return []


async def stream_reader(buffer, task_id: str, after_seq: int = 0):
    """纯消费者：从事件缓冲按 seq 偏移读取并转发 SSE — 小欧 2026-07-12

    解决什么问题：SSE 只做"读缓冲→转发"，断线即返回、不碰 agent；
    重连复用同一函数（传 after_seq 续传），避免重复事件。 — 北京老陈 2026-07-12
    """
    offset = after_seq
    while True:
        async with buffer.cond:
            while offset < len(buffer.event_log):
                yield format_agent_sse(buffer.event_log[offset])
                offset += 1
            # #30 fix:排空后复查 len,防止 done.set() 前 producer 追加丢事件 — 小欧 2026-07-18
            if offset < len(buffer.event_log):
                continue
            if buffer.done.is_set():
                return
            # cond.wait()无超时: 若producer崩溃永不set.done, 消费者永久挂起泄漏HTTP连接
            # 加60s超时, 超时后循环重检done — 北京老陈 2026-07-30
            try:
                await asyncio.wait_for(buffer.cond.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning(f"[SSE] stream_reader cond.wait 60s超时, 重检done: task_id={task_id}")
                if buffer.done.is_set():
                    return
                continue


def _log_task_end(task_id: str, end_type: str, start_time: Optional[float] = None,
                  steps: Optional[list] = None, agent: Any = None) -> None:
    """输出 TASK_END 日志（结束方式+耗时+步骤统计+LLM调用次数+累计token消耗）— 一行完整"""
    parts = [f"task_id={task_id}", f"end_type={end_type}"]
    if start_time is not None:
        elapsed = time.time() - start_time
        parts.append(f"duration={elapsed:.2f}s")
    if agent is not None:
        parts.append(f"llm_calls={getattr(agent, 'llm_call_count', 0)}")
        # 累计 token 消耗(真实用量) — 小欧 2026-08-09: 修正 steps 中 usage=N 仅为 step 计数而非 token
        _au = getattr(agent, "accumulated_usage", None)
        if _au and isinstance(_au, dict):
            parts.append("usage_tokens=" + ",".join(
                f"{k}={_au.get(k, 0)}" for k in ("prompt_tokens", "completion_tokens", "total_tokens")))
    if steps:
        counter: Dict[str, int] = {}
        for s in steps:
            t = s.get("type", "?") if isinstance(s, dict) else "?"
            counter[t] = counter.get(t, 0) + 1
        # 2026-08-09 - 小欧 - 三审收尾: usage 为非业务 Meta 步骤, 真实消耗由 usage_tokens 承担, 不混入业务统计;
        #   同性质非业务 MetaStep(paused/resumed/retrying/cancelled/authorization_required/start) 一并剔除, 与
        #   "Meta 步骤非业务步骤"注释自洽; 业务步骤(action/thought/observation/final/error)不计入排除,
        #   不误伤。total 必须在 pop 之后计算, 否则 total_steps 含排除项与注释声明矛盾。
        # 2026-08-18 小欧 P1/P3/P5/P6: chunk/error/usage/paused/resumed/retrying/cancelled 均仅SSE不落库,
        #   不入 current_execution_steps, total_steps 自然剔除; cancelled 经 task_runtime.task_cancel_check_and_yield(:90) append 进内存 steps 须显式剔除,
        #   收敛剔除集={cancelled,authorization_required,start}与 agent_runner:388 口径一致(10.4.4 第0步) — 小欧 2026-08-18(修正)
        for _t in ("cancelled", "authorization_required", "start"):
            counter.pop(_t, None)
        total = sum(counter.values())
        step_summary = ",".join(f"{k}={v}" for k, v in sorted(counter.items()))
        if step_summary:
            parts.append(f"steps=[{step_summary}]")
        parts.append(f"total_steps={total}")
    _msg = f"[TASK_END] {time.strftime('%H:%M:%S')} {' | '.join(parts)}"
    log_and_print(_msg)
