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

【6步流程】
步骤1: 预处理 (PreprocessingPipeline)
步骤2: 意图检测 (IntentRegistry)
步骤3: 初始化 (ai_service/next_step/running_tasks/current_execution_steps)
步骤4: 安全检测 (security_check)
步骤5: start步骤 (start_step)
步骤6: 调用 react_sse_wrapper（由第二层内部根据intent_type分发）

【阶段6修改】
- 步骤6改为调用 react_sse_wrapper.generate_sse_stream()
- 删除 _handle_file_operation 和 _handle_chat_operation 方法（已移至 react_sse_wrapper）
- intent_type 和 confidence 参数传递给 react_sse_wrapper

Author: 小沈 - 2026-03-26
"""

import json
import uuid
import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.preprocessing.pipeline import PreprocessingPipeline
from app.services.agent.file_react import FileReactAgent
from app.services import AIServiceFactory
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_step_counter
from app.chat_stream.error_handler import create_error_response


# 意图标签列表（用于 PreprocessingPipeline）
INTENT_LABELS = ["chat", "file", "network", "desktop"]


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


@router.post("/chat/stream/v2")
async def chat_stream_v2(request: ChatRequest):
    """
    新版本流式API，使用 chat_router 进行意图路由

    【6步完整流程】
    步骤1: 预处理 (PreprocessingPipeline)
    步骤2: 意图检测 (IntentRegistry)
    步骤3: 初始化
    步骤4: 安全检测 (security_check)
    步骤5: start步骤 (start_step)
    步骤6: 分发到Agent
    """
    # 获取用户输入
    if not request.messages:
        error_response = create_error_response(
            error_type="invalid_request",
            error_message="消息列表不能为空"
        )
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=error_response,
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    
    # 获取配置 - 使用 AIServiceFactory 的统一逻辑
    from app.services import AIServiceFactory
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

    def __init__(self) -> None:
        self.preprocessing = PreprocessingPipeline()

    async def route(
        self,
        user_input: str,
        provider: str,
        model: str,
        session_id: str,
        request: Optional[ChatRequest] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100,
        ai_service: Optional[Any] = None  # 【新增】接收外部传入的 ai_service
    ) -> AsyncGenerator[str, None]:
        """
        根据用户意图路由到对应的执行层

        【6步完整流程】

        Args:
            user_input: 用户输入
            model: 模型名称
            provider: 提供商
            session_id: 会话ID
            request: 原始请求（用于获取history）
            context: 额外上下文
            system_prompt: 自定义系统提示
            max_steps: 最大步数

        Yields:
            SSE 格式字符串
        """
        # ===== 步骤1: 预处理 =====
        intent_result = await self.preprocessing.process(
            user_input=user_input,
            intent_labels=INTENT_LABELS,
            session_id=session_id
        )
        
        # ===== 步骤2: 意图检测 =====
        intent_type = intent_result.get("intent", "chat")
        confidence = intent_result.get("confidence", 0.0)
        
        logger.info(
            f"[ChatRouter] intent_type={intent_type}, confidence={confidence:.4f}, "
            f"original='{user_input}', corrected='{intent_result.get('corrected', '')}'"
        )
        
        # ===== 步骤3: 初始化 =====
        # task_id: 任务ID
        task_id = str(uuid.uuid4())
        
        # ai_service: AI服务实例（优先使用传入的，复用而非重建）
        if ai_service is None:
            ai_service = AIServiceFactory.get_service_for_model(provider, model)
            logger.info(f"[ChatRouter] route() 自行创建 ai_service")
        else:
            logger.info(f"[ChatRouter] route() 复用传入的 ai_service")
        
        # next_step: 步骤计数器（使用统一函数）
        next_step = create_step_counter()
        
        # running_tasks: 任务字典
        running_tasks: Dict[str, Any] = {}
        
        # current_execution_steps: 执行步骤列表
        current_execution_steps: List[Dict] = []
        
        # running_tasks_lock: 任务锁
        running_tasks_lock = asyncio.Lock()
        
        # ===== 步骤4: 安全检测 =====
        from app.services.shell_security import check_command_safety
        security_check_result = check_command_safety(user_input)
        
        # 如果被阻止，记录警告但继续执行
        if security_check_result.get('blocked', False):
            logger.warning(
                f"[ChatRouter] Security check blocked: "
                f"risk={security_check_result.get('risk')}, "
                f"user_input={user_input[:50]}"
            )
        
        # ===== 步骤5: start步骤 =====
        from app.chat_stream.start_step import send_start_step
        
        # 包装 yield 函数
        def yield_sse(data: dict):
            return f"data: {json.dumps(data)}\n\n"
        
        try:
            start_data = await send_start_step(
                ai_service=ai_service,
                task_id=task_id,
                next_step=next_step,
                user_message=user_input,
                security_check_result=security_check_result,
                current_execution_steps=current_execution_steps,
                session_id=session_id,
                yield_func=yield_sse
            )
            # 将 start_data yield 给前端（和 chat2.py 保持一致）
            yield f"data: {json.dumps(start_data)}\n\n"
        except Exception as e:
            logger.error(f"[ChatRouter] send_start_step failed: {e}", exc_info=True)
            yield create_error_response(
                error_type="start_failed",
                error_message=f"start步骤失败: {str(e)}"
            )
            return
        
        # ===== 步骤6: 根据意图类型分发 =====
        # 简单对话（chat 且 confidence >= 0.3）：在 router 里调用 chat_stream_query
        # 动作意图（file/network/desktop 或 confidence < 0.3）：调用 react_sse_wrapper
        
        # display_name 用于 chat_stream_query
        display_name = f"{ai_service.provider} ({ai_service.model})"
        
        if intent_type == "chat" and confidence >= 0.3:
            # 简单对话：直接调用 chat_stream_query
            logger.info(f"[ChatRouter] 简单对话意图，分发到 chat_stream_query")
            async for event in self._handle_chat_operation(
                request=request,
                user_input=user_input,
                ai_service=ai_service,
                task_id=task_id,
                session_id=session_id,
                current_execution_steps=current_execution_steps,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                next_step=next_step,
                display_name=display_name
            ):
                yield event
        else:
            # 动作意图：调用 react_sse_wrapper 处理
            logger.info(f"[ChatRouter] 动作意图 (type={intent_type}, conf={confidence:.2f})，分发到 react_sse_wrapper")
            from app.services.react_sse_wrapper import generate_sse_stream
            
            # 准备 messages 列表
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
            
            async for event in generate_sse_stream(
                messages=messages,
                intent_type=intent_type,
                confidence=confidence,
                provider=provider,
                model=model,
                task_id=task_id,
                session_id=session_id,
                ai_service=ai_service,
                next_step=next_step,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                current_execution_steps=current_execution_steps
            ):
                yield event

    async def _handle_chat_operation(
        self,
        request: Optional[ChatRequest],
        user_input: str,
        ai_service: Any,
        task_id: str,
        session_id: str,
        current_execution_steps: List[Dict],
        running_tasks: Dict[str, Any],
        running_tasks_lock: asyncio.Lock,
        next_step: Callable,
        display_name: str
    ) -> AsyncGenerator[str, None]:
        """处理简单对话意图"""
        try:
            from app.chat_stream.chat_stream_query import chat_stream_query
            
            # 修复：如果 request 为 None，创建一个只包含当前消息的请求对象
            if request is None:
                request = ChatRequest(
                    messages=[ChatMessage(role="user", content=user_input)],
                    session_id=session_id
                )
            
            # 准备 chat_stream_query 需要的参数
            llm_call_count = 0
            current_content = ""
            last_is_reasoning = None
            last_message = user_input
            
            # 包装 save_execution_steps_to_db 函数
            from app.chat_stream.message_saver import save_execution_steps_to_db
            async def wrapped_save_steps(execution_steps, content=None):
                await save_execution_steps_to_db(session_id, execution_steps, content)
            
            # 包装 add_step_and_save 函数
            from app.chat_stream.message_saver import add_step_and_save
            async def wrapped_add_step(step, content=None):
                await add_step_and_save(current_execution_steps, step, session_id, content)
            
            async for event in chat_stream_query(
                request=request,
                ai_service=ai_service,
                task_id=task_id,
                llm_call_count=llm_call_count,
                current_execution_steps=current_execution_steps,
                current_content=current_content,
                last_is_reasoning=last_is_reasoning,
                last_message=last_message,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                next_step=next_step,
                display_name=display_name,
                session_id=session_id,
                save_execution_steps_to_db=wrapped_save_steps,
                add_step_and_save=wrapped_add_step
            ):
                yield event
                
        except Exception as e:
            logger.error(f"[ChatRouter] Chat operation failed: {e}", exc_info=True)
            yield self._create_error_sse(
                error_type="router_error",
                error_message=f"对话执行失败: {str(e)}",
                step=next_step()
            )

    def _create_error_sse(self, error_type: str, error_message: str, step: int) -> str:
        """创建错误 SSE 响应"""
        return create_error_response(
            error_type=error_type,
            error_message=error_message,
            step=step
        )


# 便捷函数：创建 router 实例
def create_chat_router() -> ChatRouter:
    """创建 ChatRouter 实例"""
    return ChatRouter()


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
