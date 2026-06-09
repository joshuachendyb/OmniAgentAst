# -*- coding: utf-8 -*-
"""
chat_stream — SSE事件流处理统一模块

合并来源:
- chat_stream/error_handler.py (create_error_response, resolve_http_error_type, get_stream_error_info, get_error_info)
- chat_stream/sse_formatter.py (format_sse_event, format_agent_sse)
- chat_stream/message_saver/ (save_execution_steps_to_db)
- chat_stream/chat_helpers.py (create_final_response)
- chat_stream/start_step.py (send_start_step)

合并人: 小沈 - 2026-06-08
SLAP原则: 所有SSE流式事件相关函数统一在此模块，不再分散到子模块
"""

import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.utils.time_utils import create_timestamp
from app.utils.counter_utils import create_step_counter
from app.services.agent.steps import StartStep, ErrorStep, FinalStep
from app.utils.error_classifier import UnifiedErrorClassifier
from app.utils.error_parser import extract_api_error_detail
from app.utils.logger import logger
from app.constants import INVALID_SESSION_IDS_MAX


# ====================================================================
# SSE格式化工具
# ====================================================================

def format_sse_event(event_type: str, step: int, data: Dict[str, Any]) -> str:
    """统一格式化 SSE 事件"""
    base = {
        'type': event_type,
        'step': step
    }
    if 'timestamp' in data:
        base['timestamp'] = data['timestamp']
    else:
        base['timestamp'] = create_timestamp()
    base.update(data)
    return f"data: {json.dumps(base, ensure_ascii=False)}\n\n"


def format_agent_sse(step_dict: dict, step: int = None) -> str:
    """Agent步骤dict → SSE字符串，只接受dict输入"""
    event_type = step_dict.get('type', '')
    step_num = step or step_dict.get('step', 0)
    if not event_type:
        return ''
    return format_sse_event(event_type, step_num, step_dict)


# ====================================================================
# 错误处理
# ====================================================================

def create_error_response(
    error_type: str,
    error_message: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[str] = None,
    stack: Optional[str] = None,
    recoverable: Optional[bool] = None,
    retry_after: Optional[int] = None,
    step: Optional[int] = None
) -> str:
    """创建统一的错误响应格式 — 使用 ErrorStep + format_agent_sse
    【修复P0-4 2026-06-08 小沈】删除StepFactory，直接调用ErrorStep构造函数
    """
    error_step = ErrorStep(
        step=step or 0,
        error_type=error_type,
        error_message=error_message,
        model=model,
        provider=provider,
        recoverable=recoverable or False,
        retry_after=retry_after,
        context={"details": details, "stack": stack} if details or stack else None
    )
    return format_agent_sse(error_step.to_dict())


def get_error_info(error: Exception) -> Dict[str, Any]:
    """获取错误信息，委托给UnifiedErrorClassifier"""
    info = UnifiedErrorClassifier.get_error_info(error)
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

_INVALID_SESSION_IDS: set = set()


def _get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID — 延迟导入避免循环依赖"""
    from app.api.v1 import messages as _messages
    return _messages.get_user_message_id(session_id)


async def save_execution_steps_to_db(
    session_id: Optional[str],
    execution_steps: List[Dict],
    content: Optional[str] = None,
    user_message_id: Optional[int] = None
) -> None:
    """保存execution_steps到DB — 唯一保存入口"""
    from app.api.v1.conversation import save_execution_steps, ExecutionStepsUpdate

    if session_id is None or session_id in _INVALID_SESSION_IDS:
        return

    try:
        if user_message_id is None:
            user_message_id = _get_user_message_id(session_id)
        await save_execution_steps(
            session_id,
            ExecutionStepsUpdate(
                execution_steps=execution_steps,
                content=content,
                reply_to_message_id=user_message_id
            )
        )
    except Exception as e:
        if "会话不存在" in str(e) or "404" in str(e):
            if len(_INVALID_SESSION_IDS) < INVALID_SESSION_IDS_MAX:
                _INVALID_SESSION_IDS.add(session_id)
            logger.warning(f"[Save] 会话不存在,已标记跳过: session_id={session_id}")
        else:
            logger.error(f"[Save] 保存失败: {e}", exc_info=True)


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
    current_execution_steps: List[Dict[str, Any]],
    session_id: str,
) -> StartStep:
    """发送 start 步骤 — P2-19 使用StartStep统一构建"""
    start_step = StartStep(
        step=next_step(),
        display_name=f"{ai_service.provider} ({ai_service.model})",
        provider=ai_service.provider,
        model=ai_service.model,
        task_id=task_id,
        user_message=user_message if user_message else "",
        security_check={
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    )
    current_execution_steps.append(start_step.to_dict())
    return start_step
