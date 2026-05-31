# -*- coding: utf-8 -*-
"""
_log_prompts — 从 react_sse_wrapper.py 拆出

复制来源: react_sse_wrapper.py 第97-152行
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional


async def log_prompts(
    messages: List[Dict[str, str]],
    intent_type: str,
    confidence: float,
    session_id: Optional[str],
    task_id: str,
) -> None:
    """复制自 react_sse_wrapper.py 第97-152行"""
    if not messages:
        return
    user_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    from app.api.v1.messages import _assistant_message_ids, _user_message_ids
    ai_message_id = _assistant_message_ids.get(session_id)
    if not ai_message_id and session_id in _user_message_ids:
        ai_message_id = _user_message_ids[session_id] + 1
    if not ai_message_id:
        return
    from app.utils.prompt_logger import get_prompt_logger
    prompt_logger = get_prompt_logger()
    prompt_logger.start_request(
        user_message=user_message,
        user_message_id=str(ai_message_id),
        session_id=session_id or task_id,
    )
    if intent_type in ("", "generic", "chat"):
        prompts_instance = None
        source_name = "通用意图：无系统Prompt"
    else:
        try:
            from app.services.agent.agent_config import resolve_agent_config
            config = resolve_agent_config(intent_type)
            prompts_instance = config.prompt_class()
            source_name = config.prompt_module.split('.')[-1] + ".py"
        except (ValueError, ImportError):
            from app.services.prompts.file import FileOperationPrompts
            prompts_instance = FileOperationPrompts()
            source_name = "file_prompts.py"
    if prompts_instance and intent_type not in ("", "generic"):
        full_prompt = prompts_instance.build_full_system_prompt()
        prompt_logger.log_system_prompt(
            step_name="系统Prompt生成",
            prompt_content=full_prompt,
            source=source_name,
            details={"intent_type": intent_type, "confidence": confidence, "note": "含OUTPUT_FORMAT(含退出规则)+TOOL_CALL_RULES+SAFETY+ROLLBACK"},
            round_number=1,
        )
    prompt_logger.log_task_prompt(
        task_content=user_message,
        context={"intent_type": intent_type, "confidence": confidence},
        round_number=1,
    )
