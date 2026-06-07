# -*- coding: utf-8 -*-
"""
消息保存 — 单一入口

Author: 小沈 - 2026-06-07
"""

import json
from typing import List, Dict, Optional, Set

_INVALID_SESSION_IDS: Set[str] = set()


async def save_execution_steps_to_db(
    session_id: Optional[str],
    execution_steps: List[Dict],
    content: Optional[str] = None,
    user_message_id: Optional[int] = None
) -> None:
    """保存execution_steps到DB — 唯一保存入口"""
    from app.api.v1 import messages as _messages
    from app.api.v1.conversation import save_execution_steps, ExecutionStepsUpdate
    from app.constants import INVALID_SESSION_IDS_MAX

    if session_id is None or session_id in _INVALID_SESSION_IDS:
        return

    try:
        if user_message_id is None:
            user_message_id = _messages.get_user_message_id(session_id)
        await save_execution_steps(
            session_id,
            ExecutionStepsUpdate(
                execution_steps=execution_steps,
                content=content,
                reply_to_message_id=user_message_id
            )
        )
    except Exception as e:
        from app.utils.logger import logger
        if "会话不存在" in str(e) or "404" in str(e):
            if len(_INVALID_SESSION_IDS) < INVALID_SESSION_IDS_MAX:
                _INVALID_SESSION_IDS.add(session_id)
            logger.warning(f"[Save] 会话不存在,已标记跳过: session_id={session_id}")
        else:
            logger.error(f"[Save] 保存失败: {e}", exc_info=True)


async def add_step_and_save(
    current_execution_steps: List[Dict],
    step: Dict,
    session_id: Optional[str],
    content: Optional[str] = None
) -> None:
    """添加步骤并保存"""
    current_execution_steps.append(step)
    await save_execution_steps_to_db(session_id, current_execution_steps, content or "")


async def parse_and_save_sse(
    sse_data: str,
    current_execution_steps: List[Dict],
    session_id: str,
    current_content: str = ""
) -> Dict:
    """解析SSE数据并保存"""
    if sse_data.startswith("data: "):
        sse_data = sse_data[6:]
    step_data = json.loads(sse_data)
    current_execution_steps.append(step_data)
    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
    return step_data
