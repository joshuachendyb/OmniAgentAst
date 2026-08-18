# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-22 - 小欧 - send_start_step 新增 warning 参数，透传给 MetaStep 供前端显示模型不在列表提示
# 2026-08-14 - 小欧 - 改名名实相符: handlers.py → sse_events.py(实为SSE事件构建+错误处理+落库; "handlers"过宽且与agent/handlers同名歧义)
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-16 - 小欧 - S3(10.1.7③/10.1.2③): send_start_step 增 system_prompt/context_summary 两字段、
#   删 security_check 空占位死代码(真实安全拦截归 tools/security 域 / HITL confirm 链路)、保留 warning(有前端消费);
#   参数收敛为 (ai_service, task_id, next_step, user_message, system_prompt, context_summary, warning) —
#   MetaStep **kwargs 透传(base.py:114), 无需新建 StartStep 类
# 2026-08-17 - 小健 - start 业务过程收敛(北京老陈驱动, 痛斥四处散落): 新增 build_start_step 集中函数,
#   start 全部业务(算 context_summary 快照 message_count/total_tokens + 构造任务输入契约 StartStep)收拢一处,
#   orchestrator 闭包只负责 P4 捕获传参; 依赖方向 chat→agent(MessageBuilder 估算, 合法方向)
# 2026-08-17 - 小健 - start 业务彻底迁出(老陈驱动, 三思三省): 契约构造逻辑迁入 start_step 模块(_build_start_contract),
#   删除本文件 send_start_step/build_start_step 两函数及 MetaStep/MessageBuilder import(死代码清除);
#   start 业务完整单归属 start_step.py, sse_events 不再承载任何 start 构造 — 小健 2026-08-17
# 2026-08-18 小欧 - §10.3.3(4): create_final_response 参数 thought→reasoning(FinalStep已删thought字段)
"""
sse_events — SSE事件流处理模块
从 react_sse_wrapper/chat_stream.py 移入
小欧 2026-07-10
"""

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.utils.sse_formatter import format_sse_event, format_agent_sse
from app.services.agent.steps import ErrorStep, FinalStep
from app.llm.error_classifier import SystemErrorClassifier
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
    reasoning: str = '',   # 2026-08-18 小欧 thought→reasoning
) -> str:
    """创建最终的SSE响应 — 使用 FinalStep + format_agent_sse
    【修复P0-4 2026-06-08 小沈】删除StepFactory，直接调用FinalStep构造函数
    """
    final_step = FinalStep(
        step=step or 0,
        response=content,
        reasoning=reasoning,
        model=model,
        provider=provider
    )
    return format_agent_sse(final_step.to_dict())
