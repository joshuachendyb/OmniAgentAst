# -*- coding: utf-8 -*-
"""
_handle_client_disconnect — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第217-244行
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import List, Dict, Optional, Any, AsyncGenerator, Callable

from app.services.agent.steps import IncidentStep
from app.utils.logger import logger
from app.chat_stream.message_saver import save_execution_steps_to_db
from app.chat_stream.sse_formatter import format_agent_sse


async def handle_client_disconnect(
    task_id: str,
    session_id: Optional[str],
    current_execution_steps: List[Dict],
    current_content: str,
    next_step: Callable[[], int],
    running_tasks: Dict[str, Any],
    running_tasks_lock: asyncio.Lock,
) -> AsyncGenerator[str, None]:
    """复制自 react_sse_wrapper.py 第217-244行"""
    async with running_tasks_lock:
        running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
    incident_step = IncidentStep(
        step=next_step(),
        incident_value='interrupted',
        message='客户端断开连接，任务中断'
    )
    current_execution_steps.append(incident_step.to_dict())
    try:
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
    except Exception as _save_err:
        logger.warning(f"[SSE] CancelledError后保存失败(可忽略): {_save_err}")
    try:
        logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开)")
        yield format_agent_sse(incident_step)
    except Exception:
        logger.info(f"[Step interrupted] 客户端已断开，跳过yield")
