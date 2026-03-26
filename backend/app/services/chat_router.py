# -*- coding: utf-8 -*-
"""
Chat Router - 路由层

【第一阶段实现 - 2026-03-26 小沈】
【Stage 5 更新 - 2026-03-26】
根据用户意图类型，将请求分发到对应的执行层。

架构：
- 第一层：chat_router.py - 路由入口 + 6步完整流程
- 第二层：react_sse_wrapper.py - SSE 包装（待实现）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【6步流程】
步骤1: 预处理 (PreprocessingPipeline)
步骤2: 意图检测 (IntentRegistry)
步骤3: 初始化 (ai_service/next_step/running_tasks/current_execution_steps)
步骤4: 安全检测 (security_check)
步骤5: start步骤 (start_step)
步骤6: 分发到Agent

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
        error_data = {"type": "error", "message": "消息列表不能为空"}
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=f"data: {json.dumps(error_data)}\n\n",
            media_type="text/event-stream"
        )

    user_input = request.messages[-1].content
    
    # 获取配置
    from app.config import get_config
    config = get_config()
    ai_config = config.get('ai', {})
    
    # 确定 provider 和 model
    provider = request.provider
    model = request.model
    
    if not provider or provider not in ai_config:
        # 默认使用第一个可用的 provider
        provider = list(ai_config.keys())[0] if ai_config else "openai"
    
    if not model:
        # 默认模型
        model = ai_config.get(provider, {}).get('default_model', 'gpt-4')
    
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
                request=request  # 传递原始请求用于获取 history
            ):
                yield sse_data
        except Exception as e:
            logger.error(f"[chat_stream_v2] Error: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
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
        model: str,
        provider: str,
        session_id: str,
        request: Optional[ChatRequest] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100
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
        intent_result = self.preprocessing.process(
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
        
        # ai_service: AI服务实例
        ai_service = AIServiceFactory.get_service_for_model(provider, model)
        
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
        except Exception as e:
            logger.error(f"[ChatRouter] send_start_step failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': f'start步骤失败: {str(e)}'})}\n\n"
            return
        
        # ===== 提取 llm_client =====
        # FileReactAgent 需要 llm_client 函数，从 ai_service.chat 包装
        async def llm_client(message, history=None):
            response = await ai_service.chat(message, history)
            return type('obj', (object,), {'content': response.content})()
        
        # ===== 步骤6: 分发到Agent =====
        if intent_type == "chat" or confidence < 0.3:
            # 简单对话
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
                display_name=start_data['display_name']
            ):
                yield event
        elif intent_type == "file" and confidence >= 0.3:
            # 文件操作
            async for event in self._handle_file_operation(
                user_input=user_input,
                model=model,
                provider=provider,
                llm_client=llm_client,
                session_id=session_id,
                context=context,
                system_prompt=system_prompt,
                max_steps=max_steps,
                next_step=next_step
            ):
                yield event
        elif intent_type == "network" and confidence >= 0.3:
            # 网络操作 - 暂不支持
            logger.warning(f"[ChatRouter] Network intent not implemented yet")
            yield self._create_error_sse(
                message="network功能正在开发中",
                step=next_step()
            )
        elif intent_type == "desktop" and confidence >= 0.3:
            # 桌面操作 - 暂不支持
            logger.warning(f"[ChatRouter] Desktop intent not implemented yet")
            yield self._create_error_sse(
                message="desktop功能正在开发中",
                step=next_step()
            )
        else:
            # 默认回退到 chat
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
                display_name=start_data['display_name']
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
                message=f"对话执行失败: {str(e)}",
                step=next_step()
            )

    async def _handle_file_operation(
        self,
        user_input: str,
        model: str,
        provider: str,
        llm_client: Any,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100,
        next_step: Optional[Callable[[], int]] = None
    ) -> AsyncGenerator[str, None]:
        """
        处理文件操作意图

        Args:
            user_input: 用户输入
            model: 模型名称
            provider: 提供商
            llm_client: LLM 客户端函数
            session_id: 会话ID
            context: 额外上下文
            system_prompt: 自定义系统提示
            max_steps: 最大步数
            next_step: step 计数函数

        Yields:
            SSE 格式字符串
        """
        try:
            # 创建 FileReactAgent 实例
            agent = FileReactAgent(
                llm_client=llm_client,
                session_id=session_id
            )

            # 调用 ver1_run_stream（返回 SSE 字符串）
            async for sse_data in agent.ver1_run_stream(
                task=user_input,
                model=model,
                provider=provider,
                context=context,
                system_prompt=system_prompt,
                max_steps=max_steps,
                get_next_step=next_step
            ):
                yield sse_data

        except Exception as e:
            logger.error(f"[ChatRouter] File operation failed: {e}", exc_info=True)
            yield self._create_error_sse(
                message=f"文件操作执行失败: {str(e)}",
                step=next_step() if next_step else 0
            )

    def _create_error_sse(self, message: str, step: int) -> str:
        """创建错误 SSE 响应"""
        error_data = {
            "type": "error",
            "step": step,
            "code": "ROUTER_ERROR",
            "message": message
        }
        return f"data: {json.dumps(error_data)}\n\n"


# 便捷函数：创建 router 实例
def create_chat_router() -> ChatRouter:
    """创建 ChatRouter 实例"""
    return ChatRouter()
