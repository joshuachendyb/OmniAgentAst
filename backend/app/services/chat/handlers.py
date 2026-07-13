# -*- coding: utf-8 -*-
"""
handlers — SSE事件流处理模块
从 react_sse_wrapper/chat_stream.py 移入
小欧 2026-07-10
"""

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.utils.time_utils import create_timestamp
from app.utils.sse_formatter import format_sse_event, format_agent_sse
from app.services.agent.steps import MetaStep, ErrorStep, FinalStep
from app.services.llm.error_classifier import SystemErrorClassifier
from app.logger import logger
from app.services.chat.storage import save_execution_steps
from app.services.chat.storage import ExecutionStepsUpdate
from app.services.chat.storage import get_user_message_id


# ====================================================================

# 错误处理
# ====================================================================

def create_error_response(
    error_type: str,
    error_message: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    step: Optional[int] = None
) -> str:
    """创建统一的错误响应格式 — 使用 ErrorStep + format_agent_sse — 小欧 2026-07-13 删 recoverable（终态由 ErrorStep 表示）"""
    error_step = ErrorStep(
        step=step or 0,
        error_type=error_type,
        error_message=error_message,
        model=model,
        provider=provider,
    )
    return format_agent_sse(error_step.to_dict())


def get_error_info(error: Exception) -> Dict[str, Any]:
    """获取错误信息，委托给SystemErrorClassifier"""
    info = SystemErrorClassifier.get_error_info(error)
    category = info["category"]
    return {
        "code": category.name,
        "message": info["message"],
        "error_type": info["code"],
        "retryable": info["retryable"],
        "retry_after": 5 if info["retryable"] else None,
    }



# ====================================================================
# 消息保存
# ====================================================================

async def save_execution_steps_to_db(
    session_id: Optional[str],
    execution_steps: List[Dict],
    content: Optional[str] = None,
    user_message_id: Optional[int] = None,
    status: Optional[str] = None
) -> None:
    """保存execution_steps到DB — 唯一保存入口 — 小健 2026-06-18 内联_get_user_message_id
    小欧 2026-07-13: 新增 status 参数，落 chat_messages.status 列（终态），正常路径依赖该列"""

    if session_id is None:
        return

    try:
        if user_message_id is None:
            user_message_id = get_user_message_id(session_id)
        result = await save_execution_steps(
            session_id,
            ExecutionStepsUpdate(
                execution_steps=execution_steps,
                content=content,
                reply_to_message_id=user_message_id,
                **({"status": status} if status else {})
            )
        )
        ai_message_id = result.get("ai_message_id") if isinstance(result, dict) else None
        return ai_message_id

    except Exception as e:
        if "会话不存在" in str(e) or "404" in str(e):
            logger.warning(f"[Save] 会话不存在,跳过本次: session_id={session_id}")
        else:
            logger.error(f"[Save] 保存失败: {e}", exc_info=True)
        return None


# ====================================================================
# 辅助函数
# ====================================================================

def create_final_response(
    content: str,
    step: Optional[int] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    thought: str = '',
) -> str:
    """创建最终的SSE响应 — 使用 FinalStep + format_agent_sse
    【修复P0-4 2026-06-08 小沈】删除StepFactory，直接调用FinalStep构造函数
    """
    final_step = FinalStep(
        step=step or 0,
        response=content,
        thought=thought,
        model=model,
        provider=provider
    )
    return format_agent_sse(final_step.to_dict())


# ====================================================================
# Start步骤
# ====================================================================

async def send_start_step(
    ai_service: Any,
    task_id: str,
    next_step: Callable,
    user_message: str,
    security_check_result: Dict[str, Any],
) -> MetaStep:
    """发送 start 步骤 — 使用MetaStep统一构建"""
    return MetaStep(
        step=next_step(),
        type="start",
        message=user_message if user_message else "",
        display_name=f"{ai_service.provider} ({ai_service.model})",
        provider=ai_service.provider,
        model=ai_service.model,
        task_id=task_id,
        security_check={
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    )
