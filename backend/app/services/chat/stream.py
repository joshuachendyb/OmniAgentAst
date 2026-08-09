# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 小欧 - _load_previous_messages改为从chat_message_steps组装(load_execution_steps), 多轮上下文读取新表
# 2026-07-18 小欧 - #30 fix: _read_stream排空后复查len(buffer.event_log),防done前追加丢事件
# 2026-07-18 小欧 - F4 fix: _parse_tool_calls try收窄到单步, 单步参数异常不株连整批
# 2026-07-23 小欧 - log_and_print统一: print(_msg); logger.info(_msg)替换为log_and_print(_msg), 导入log_and_print; TASK_END消息追加时间串
# 2026-07-30 - 小欧 - 后端卡死根因修复: cond.wait() 加 60s 超时(asyncio.wait_for)+超时后重检 buffer.done; 防止 SSE 消费者因 cond 永远不被 notify 而永久挂起占死 HTTP 连接
# 2026-08-09 - 小欧 - TASK_END 追加真实累计token用量 usage_tokens=prompt_tokens=..,completion_tokens=..,total_tokens=..(读agent.accumulated_usage) 及 total_steps=N 总步骤数; steps 统计剔除 usage 类型计数(原 usage=N 恒等llm_calls 为 usage step 计数非 token, 曾误导读数)
"""
stream — SSE流运行器（消费者）

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
from app.services.agent.steps import ErrorStep
from app.services.task.task_state import agent_streams
from app.logger import logger, log_and_print
from app.utils.sse_formatter import format_agent_sse
from app.utils.json_utils import safe_json_dumps  # steps序列化为JSON串供多轮上下文 — 小欧 2026-07-14
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14


def _parse_tool_calls(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取tool_calls列表
    小欧 2026-06-25 从_load_previous_messages提取
    小欧 2026-07-18 F4修复: try收窄到单步, 单步参数异常不株连整批"""
    try:
        exec_steps = json.loads(exec_steps_json)
    except Exception:
        return []
    if not isinstance(exec_steps, list):
        logger.warning(f"[_parse_tool_calls] exec_steps非list, 跳过: {type(exec_steps)}")
        return []
    tool_calls = []
    for step in exec_steps:
        if step.get("type") != "action_tool":
            continue
        try:
            arguments = json.dumps(step.get("tool_params", {}), ensure_ascii=False)
        except (TypeError, ValueError):
            arguments = "{}"
            logger.warning(f"[_parse_tool_calls] tool_params不可序列化, 降级为{{}}: {step.get('tool_name')}")
        tool_calls.append({
            "id": f"call_{msg_id}_{step.get('step', 0)}",
            "type": "function",
            "function": {
                "name": step.get("tool_name", ""),
                "arguments": arguments,
            }
        })
    return tool_calls


def _parse_observations(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取observation tool消息 — 小欧 2026-06-25 从_load_previous_messages提取
    小欧 2026-07-10 M-12: content已扁平到顶层，不再从observation包装读取"""
    try:
        exec_steps = json.loads(exec_steps_json)
        observations = []
        for step in exec_steps:
            if step.get("type") == "observation":
                content = step.get("content", "")
                if content:
                    observations.append({
                        "role": "tool",
                        "content": content,
                        "tool_call_id": f"call_{msg_id}_{step.get('step', 0)}"
                    })
        return observations
    except Exception:
        return []


def _load_previous_messages(session_id: str) -> List[Dict[str, Any]]:
    """从DB加载会话历史消息 — 小健 2026-06-17 委托db层，消除SQLite越界
    小欧 2026-06-25: 抽取_parse_tool_calls/_parse_observations消除嵌套try/except
    小欧 2026-07-14: 从chat_message_steps组装"""
    try:
        with db.get_conn("chat") as conn:
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
        total = sum(counter.values())
        # usage 为 Meta 步骤非业务步骤, 真实消耗由 usage_tokens 承担; 不混入业务统计 — 小欧 2026-08-09
        counter.pop("usage", None)
        step_summary = ",".join(f"{k}={v}" for k, v in sorted(counter.items()))
        if step_summary:
            parts.append(f"steps=[{step_summary}]")
        parts.append(f"total_steps={total}")
    _msg = f"[TASK_END] {time.strftime('%H:%M:%S')} {' | '.join(parts)}"
    log_and_print(_msg)


def _yield_error_sse(error_type, error_label, log_tag, task_id, e, next_step, current_execution_steps, session_id):
    """内联错误SSE生成(避免外部模块依赖) — P2-18 使用ErrorStep替代手工dict"""
    step_num = next_step()
    error_step = ErrorStep(
        step=step_num,
        error_type=error_type,
        error_message=str(e),
    )
    current_execution_steps.append(error_step.to_dict())
    # 【修改 2026-06-09 小沈】删除_save调用，统一在finally块中保存
    return format_agent_sse(error_step.to_dict())
