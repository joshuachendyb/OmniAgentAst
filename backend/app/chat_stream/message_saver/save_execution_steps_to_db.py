# -*- coding: utf-8 -*-
"""
save_execution_steps_to_db — 从 message_saver.py 拷出

拷贝来源: message_saver.py 第34-89行
"""

from typing import List, Dict, Optional, Set

_INVALID_SESSION_IDS: Set[str] = set()


async def save_execution_steps_to_db(
    session_id: Optional[str],
    execution_steps: List[Dict],
    content: Optional[str] = None,
    user_message_id: Optional[int] = None
) -> None:
    """拷贝自 message_saver.py 第34-89行"""
    from app.api.v1 import messages as _messages
    from app.api.v1.conversation import save_execution_steps, ExecutionStepsUpdate
    from app.constants import INVALID_SESSION_IDS_MAX

    if session_id is None:
        return

    if session_id in _INVALID_SESSION_IDS:
        return

    try:
        if user_message_id is None:
            user_message_id = _messages._user_message_ids.get(session_id)

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
            logger.warning(f"[Save] 会话不存在，已标记跳过: session_id={session_id}, 缓存大小={len(_INVALID_SESSION_IDS)}")
        else:
            logger.error(f"[Save] 保存失败: {e}", exc_info=True)
