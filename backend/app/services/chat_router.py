# -*- coding: utf-8 -*-
"""
Chat Router - 路由层

【第一阶段实现 - 2026-03-26 小沈】
【Stage 5 更新 - 2026-03-26】
【阶段6更新 - 2026-03-27】简化分发逻辑，统一调用 react_sse_wrapper

架构：
- 第一层：chat_router.py - 路由入口 + 6步完整流程
- 第二层：react_sse_wrapper.py - SSE 包装（本文件调用）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【4步流程】
步骤1: 意图检测
步骤2: 初始化 (ai_service/next_step/running_tasks/current_execution_steps)
步骤3: start步骤 (start_step)
步骤4: 调用 react_sse_wrapper（由第二层内部根据intent_type分发）

【阶段6修改】
- 步骤6改为调用 react_sse_wrapper.generate_sse_stream()
- 删除 _handle_file_operation 和 _handle_chat_operation 方法（已移至 react_sse_wrapper）
- intent_type 和 confidence 参数传递给 react_sse_wrapper

Author: 小沈 - 2026-03-26
"""

import json
import uuid
import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.services import AIServiceFactory
from app.utils.logger import logger
from app.utils.time_utils import create_step_counter
from app.chat_stream.error_handler import create_error_response
from app.constants import DEFAULT_MAX_STEPS
from app.services.tools.tool_types import ToolCategory

# 【2026-05-01 小沈】从独立模块导入CRSS评分功能
from app.services.intents.crss_scorer import (
    detect_intent_v2,
    CRSS_CONFIDENCE_THRESHOLD,
)
from app.services.react_sse_wrapper import running_tasks, running_tasks_lock, generate_sse_stream
from app.chat_stream.start_step import send_start_step
from app.chat_stream.sse_formatter import format_sse_event
from app.services.preprocessing.intent_classifier import classify_intent
from app.services.intents.intent_mapper import resolve_category


# 【修复 2026-04-30 小沈】CRSS置信度阈值：归一化评分 >= 此值认为意图可信
# CRSS评分经 1 - 2^(-raw) 归一化到 [0, 1)，0.3 对应原始分约 0.5
# 【2026-05-01 小沈】已移至独立模块 app/services/intents/crss_scorer.py


# ================================================================================
# route_with_fallback - 两阶段意图路由（设计文档v1.5 3.1.2节）
# 阶段1: CRSS快速匹配 → 阶段2: LLM语义分类（兜底）
# 小沈 - 2026-04-30
# ================================================================================

async def _route_with_fallback(user_input: str) -> Dict:
    """
    两阶段意图路由：CRSS快速匹配 + LLM兜底

    阶段1: 调用 detect_intent_v2 进行CRSS规则匹配
      - 匹配成功且唯一 → 直接返回，不调LLM
    阶段2: 无匹配或模糊匹配 → 调用 LLM 语义分类

    Args:
        user_input: 用户输入

    Returns:
        dict: {
            "intent": ToolCategory,       # 最终意图
            "candidates": List[ToolCategory],  # 所有候选
            "confidence": float,           # 置信度
            "original": str,               # 原始输入
            "corrected": str,              # 矫正后文本（LLM兜底时）
            "all_intents": dict,           # 所有意图置信度
            "source": str,                 # "crss" 或 "llm"
        }
    """
    # ===== 阶段1: CRSS快速匹配 =====
    primary, candidates, confidence = detect_intent_v2(user_input)

    result = {
        "intent": primary,
        "candidates": candidates,
        "confidence": confidence,
        "original": user_input,
        "corrected": user_input,
        "all_intents": {},
        "source": "crss",
    }

    # CRSS匹配成功（加权评分后有明确主意图）
    if primary is not None and confidence >= CRSS_CONFIDENCE_THRESHOLD:
        logger.info(
            f"[RouteFallback] CRSS阶段1 → intent={primary.value}, "
            f"conf={confidence}, candidates={[c.value for c in candidates]}"
        )
        return result

    # ===== 阶段2: LLM语义分类（兜底）=====
    logger.info(
        f"[RouteFallback] CRSS无匹配或模糊，进入LLM兜底阶段2. "
        f"primary={primary}, candidates={candidates}"
    )

    try:
        # 准备提示标签（所有ToolCategory，不再含chat——所有请求走ReAct循环）
        intent_labels = [c.value for c in ToolCategory]

        llm_result = await classify_intent(user_input, intent_labels)

        intent_str = llm_result.get("intent", "")
        llm_confidence = float(llm_result.get("confidence", 0.5))

        # 将LLM返回的字符串转为ToolCategory（支持新旧意图名） - 【2026-05-18 小沈】
        intent_enum = resolve_category(intent_str)

        result.update({
            "intent": intent_enum,
            "candidates": [intent_enum] if intent_enum else [],
            "confidence": llm_confidence,
            "corrected": llm_result.get("corrected", user_input),
            "all_intents": llm_result.get("all_intents", {}),
            "source": "llm",
            "raw_intent": intent_str,
        })

        logger.info(
            f"[RouteFallback] LLM阶段2 → intent={intent_str}({intent_enum}), "
            f"conf={llm_confidence}, corrected='{result['corrected']}'"
        )
    except Exception as e:
        logger.warning(f"[RouteFallback] LLM兜底失败: {e}，使用CRSS结果")
        # LLM失败时，保持CRSS结果

    return result


# ==================== FastAPI 路由定义 ====================

router = APIRouter()


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., description="角色: system/user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""
    messages: List[ChatMessage] = Field(..., description="消息列表")
    stream: bool = Field(default=False, description="是否流式返回")
    temperature: Optional[float] = Field(default=0.7, ge=0, le=2, description="温度参数")
    provider: Optional[str] = Field(default=None, description="前端指定的提供商")
    model: Optional[str] = Field(default=None, description="前端指定的模型")
    task_id: Optional[str] = Field(default=None, description="前端指定的任务ID")
    session_id: Optional[str] = Field(default=None, description="会话ID")


@router.post("/chat/stream")
async def chat_stream_v2(request: ChatRequest):
    """
    新版本流式API，使用 chat_router 进行意图路由

    【6步完整流程】
    步骤1: 预处理 (PreprocessingPipeline)
    步骤2: 意图检测 (IntentRegistry)
    步骤3: 初始化

    步骤5: start步骤 (start_step)
    步骤6: 分发到Agent
    """
    # 获取用户输入
    if not request.messages:
        error_response = create_error_response(
            error_type="invalid_request",
            error_message="消息列表不能为空"
        )
        return PlainTextResponse(
            content=error_response,
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    
    # 获取配置 - 使用 AIServiceFactory 的统一逻辑
    ai_service = AIServiceFactory.get_service()
    provider = ai_service.provider
    model = ai_service.model
    
    # session_id
    session_id = request.session_id or str(uuid.uuid4())
    
    # 创建 ChatRouter 实例
    chat_router = ChatRouter()
    
    # 创建 SSE 生成器
    async def generate():
        try:
            async for sse_data in chat_router.route(
                user_input=user_input,
                provider=provider,
                model=model,
                session_id=session_id,
                request=request,  # 传递原始请求用于获取 history
                ai_service=ai_service  # 【新增】传递已创建的 ai_service
            ):
                yield sse_data
        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield create_error_response(
                error_type="router_error",
                error_message=f"路由异常: {str(e)}"
            )
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== ChatRouter 服务层 ====================

class ChatRouter:
    """
    聊天路由器 - 根据意图类型分发到对应的执行层
    """

    async def _detect_intent(self, user_input: str) -> Tuple[str, str, float, List[str]]:
        """两阶段意图检测 + 闲聊/network降级。返回 (intent_type, source, confidence, candidates) — 小沈 2026-05-25 重构"""
        intent_info = await _route_with_fallback(user_input)
        intent_value = intent_info["intent"]
        source = intent_info.get("source", "unknown")
        conf = intent_info["confidence"]
        candidates = [c.value for c in intent_info.get("candidates", []) if c]
        if intent_value is not None:
            return intent_value.value, source, conf, candidates
        raw = str(intent_info.get("raw_intent", "")).lower()
        intent_type = "system" if raw in {"greeting", "chat", "conversation", "qa", "question"} else "network"
        return intent_type, f"{source}(fallback)", conf, candidates

    def _init_route_context(self, provider: str, model: str, ai_service, session_id: str):
        """初始化 task_id/ai_service/steps/execution_steps/running_tasks引用 — 小沈 2026-05-25 重构"""
        task_id = str(uuid.uuid4())
        if ai_service is None:
            ai_service = AIServiceFactory.get_service_for_model(provider, model)
        return task_id, ai_service, running_tasks, running_tasks_lock

    async def _step_start(self, ai_service, task_id, next_step, user_input, execution_steps, session_id):
        """S3 start_step 细节下沉 — SLAP分层"""
        try:
            start_data = await send_start_step(
                ai_service=ai_service, task_id=task_id, next_step=next_step,
                user_message=user_input, security_check_result={},
                current_execution_steps=execution_steps, session_id=session_id,
                yield_func=lambda d: f"data: {json.dumps(d)}\n\n"
            )
            yield f"data: {json.dumps(start_data)}\n\n"
        except Exception as e:
            yield create_error_response(error_type="start_failed", error_message=f"start步骤失败: {e}")

    async def _step_react_loop(self, messages, intent_type, confidence, candidates, provider, model,
                               task_id, session_id, ai_service, next_step, running_tasks, running_tasks_lock,
                               execution_steps):
        """S4 ReAct 循环细节下沉 — 实现SLAP分层"""
        messages_list = [{"role": msg.role, "content": msg.content} for msg in messages]
        async for event in generate_sse_stream(messages=messages_list, intent_type=intent_type,
            confidence=confidence, candidates=candidates, provider=provider, model=model,
            task_id=task_id, session_id=session_id, ai_service=ai_service, next_step=next_step,
            running_tasks=running_tasks, running_tasks_lock=running_tasks_lock,
            current_execution_steps=execution_steps):
            yield event

    async def route(
        self,
        user_input: str,
        provider: str,
        model: str,
        session_id: str,
        request: Optional[ChatRequest] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        ai_service: Optional[Any] = None
    ) -> AsyncGenerator[str, None]:
        """4步路由：意图检测→初始化→start_step→ReAct — 小沈 2026-05-27 清理"""
        # S1 意图检测
        intent_type, source, confidence, candidates = await self._detect_intent(user_input)
        logger.info(f"[ChatRouter] intent_type={intent_type}({source}), conf={confidence:.2f}")

        # S2 初始化
        task_id, ai_service, running_tasks, running_tasks_lock = self._init_route_context(
            provider, model, ai_service, session_id)
        next_step = create_step_counter()
        execution_steps: List[Dict] = []

        # S3 start_step — 安全检查统一在react_sse_wrapper中执行，此处不重复检查
        async for event in self._step_start(
            ai_service, task_id, next_step, user_input, execution_steps, session_id
        ):
            yield event

        # S4 ReAct 循环（所有意图统一路由）
        async for event in self._step_react_loop(
            request.messages, intent_type, confidence, candidates, provider, model,
            task_id, session_id, ai_service, next_step, running_tasks, running_tasks_lock,
            execution_steps
        ):
            yield event


# ============================================================================
# 任务控制 API 端点（附录7.1）
# 从 react_sse_wrapper 导入任务控制函数
# ============================================================================
from app.services.react_sse_wrapper import (
    cancel_task as wrapper_cancel_task,
    pause_task as wrapper_pause_task,
    resume_task as wrapper_resume_task,
)

task_router = APIRouter()


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    取消任务
    """
    logger.info(f"[TaskControl] 取消任务: task_id={task_id}")
    result = await wrapper_cancel_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    暂停任务
    """
    logger.info(f"[TaskControl] 暂停任务: task_id={task_id}")
    result = await wrapper_pause_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    恢复任务
    """
    logger.info(f"[TaskControl] 恢复任务: task_id={task_id}")
    result = await wrapper_resume_task(task_id, session_id)
    return result


@task_router.post("/chat/stream/confirm")
async def confirm_operation(request: Request):
    """
    用户确认继续操作
    """
    body = await request.json()
    task_id = body.get("task_id")
    confirmed = body.get("confirmed", True)
    
    logger.info(f"[TaskControl] 用户确认: task_id={task_id}, confirmed={confirmed}")
    
    # TODO: 实现用户确认逻辑
    return {
        "success": True,
        "message": "确认已收到"
    }


@router.get("/chat/validate")
async def validate_chat_config():
    """
    验证AI服务配置是否可用
    
    Returns:
        dict: 验证结果，包含valid、message、provider、model字段
    """
    try:
        from app.services.factory import AIServiceFactory
        from app.services.ai_config_resolver import get_ai_config_resolver
        
        resolver = get_ai_config_resolver()
        is_valid, final_provider, final_model, error_messages = resolver.validate_config()
        
        if not is_valid:
            return {
                "valid": False,
                "message": f"配置验证失败: {', '.join(error_messages)}",
                "provider": final_provider or "unknown",
                "model": final_model or ""
            }
        
        return {
            "valid": True,
            "message": f"配置验证通过: {final_provider} ({final_model})",
            "provider": final_provider,
            "model": final_model
        }
    except Exception as e:
        logger.error(f"验证AI服务配置失败: {e}")
        return {
            "valid": False,
            "message": f"验证失败: {str(e)}",
            "provider": "unknown",
            "model": ""
        }
