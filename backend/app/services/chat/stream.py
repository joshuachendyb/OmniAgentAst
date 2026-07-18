# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - _load_previous_messages改为从chat_message_steps组装(load_execution_steps), 多轮上下文读取新表
# 2026-07-18 - 小欧 - #30 fix: _read_stream排空后复查len(buffer.event_log),防done前追加丢事件
"""
stream — SSE流运行器（消费者）

北京老陈 2026-07-12: 将原 run_sse_stream（生产者+消费者合一）拆为：
- agent_runner.run_agent_in_background: 生产者（后台运行 agent，写事件缓冲）
- 本文件 stream_reader: 消费者（从 agent_streams[task_id] 缓冲按 seq 读取并转发 SSE）

小欧 2026-07-10 从 react_sse_wrapper/run_sse_stream.py 移入
"""

import json
import time
from typing import Any, Callable, Dict, List, Optional

from app.db import db
from app.services.agent.steps import ErrorStep
from app.services.task.task_state import agent_streams
from app.logger import logger
from app.utils.sse_formatter import format_agent_sse
from app.utils.json_utils import safe_json_dumps  # steps序列化为JSON串供多轮上下文 — 小欧 2026-07-14
from app.services.chat.storage import load_execution_steps  # 从chat_message_steps组装 — 小欧 2026-07-14


def _parse_tool_calls(msg_id: int, exec_steps_json: str) -> List[Dict]:
    """从execution_steps JSON提取tool_calls列表 — 小欧 2026-06-25 从_load_previous_messages提取"""
    try:
        exec_steps = json.loads(exec_steps_json)
        tool_calls = []
        for step in exec_steps:
            if step.get("type") == "action_tool":
                tool_calls.append({
                    "id": f"call_{msg_id}_{step.get('step', 0)}",
                    "type": "function",
                    "function": {
                        "name": step.get("tool_name", ""),
                        "arguments": __import__("json").dumps(step.get("tool_params", {}), ensure_ascii=False)
                    }
                })
        return tool_calls
    except Exception:
        return []


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
            await buffer.cond.wait()


def _log_task_end(task_id: str, end_type: str, start_time: Optional[float] = None,
                  steps: Optional[list] = None, agent: Any = None) -> None:
    """输出 TASK_END 日志（结束方式+耗时+步骤统计+LLM调用次数）— 一行完整"""
    parts = [f"task_id={task_id}", f"end_type={end_type}"]
    if start_time is not None:
        elapsed = time.time() - start_time
        parts.append(f"duration={elapsed:.2f}s")
    if agent is not None:
        parts.append(f"llm_calls={getattr(agent, 'llm_call_count', 0)}")
    if steps:
        counter: Dict[str, int] = {}
        for s in steps:
            t = s.get("type", "?") if isinstance(s, dict) else "?"
            counter[t] = counter.get(t, 0) + 1
        step_summary = ",".join(f"{k}={v}" for k, v in sorted(counter.items()))
        if step_summary:
            parts.append(f"steps=[{step_summary}]")
    _msg = f"[TASK_END] {' | '.join(parts)}"
    print(_msg)
    logger.info(_msg)


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
