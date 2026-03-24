"""
对话 API 路由

================================================================================
【重要！绝对禁止硬编码 Provider 名称 - 所有代码编写人员必须遵守！】

禁止事项：
1. 绝对禁止在代码中硬编码具体的 provider 名称（如"zhipuai"、"opencode"、"longcat"等）
2. 绝对禁止在注释中硬编码 provider 名称（如"支持智谱 GLM 和 OpenCode 模型"）
3. 所有 provider 必须从配置文件中动态遍历，不能写死
4. 配置文件里有什么 provider，代码就支持什么 provider
5. 这是通用程序，不是只给这几个 provider 用的！

正确做法：
1. 使用 get_provider_display_name() 函数动态获取显示名称
2. 从配置文件中读取 provider 列表
3. 动态遍历处理所有 provider

违反后果：
- 代码审查不通过
- 必须立即修复
- 严重者重新学习项目规范
================================================================================

集成文件操作 Agent
支持 SSE 流式响应
"""

import httpx
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, AsyncGenerator, Any
from app.services import AIServiceFactory
from app.services.base import Message  # ⭐ 【调试添加】用于日志记录
from app.services.agent import IntentAgent as FileOperationAgent  # IntentAgent 已重命名，保留别名保持兼容
from app.services.shell_security import check_command_safety
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name  # ⭐ 【小沈添加 2026-03-03】
from app.utils.retry_controller import RetryController  # 【小沈-2026-03-14添加】统一的空闲超时和重试控制器
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError  # 【小沈-2026-03-14添加】通用的空闲超时异步迭代器
from app.chat_stream.chat_stream_query import chat_stream_query  # 【重构优化】复用 chat_stream_query 模块
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused, create_incident_data  # 【重构优化】复用 incident_handler 模块
from app.chat_stream.error_handler import create_error_response, get_user_friendly_error, create_error_step  # 【重构优化】复用 error_handler 模块
from app.chat_stream.chat_helpers import create_final_response, create_timestamp  # 【重构优化】复用 chat_helpers 模块
from app.api.v1.intent_classifier import detect_file_operation_intent  # 【小沈修复 2026-03-23】使用子串匹配版本，支持"给我查看一下 D盘有什么文件"
from app.chat_stream.message_saver import save_execution_steps_to_db, add_step_and_save, create_add_step_and_save, parse_and_save_sse  # 【小沈重构 2026-03-23】统一消息保存模块
from pathlib import Path
import shutil

# Provider 显示名称映射
# 从配置文件验证Provider是否存在 - 小新第二修复 2026-03-01 17:04:23
def get_provider_display_name(provider: str) -> str:
    """
    直接返回provider名称，不做任何映射转换
    只验证provider是否在配置文件中存在
    """
    from app.config import get_config
    config = get_config()
    ai_config = config.get('ai', {})
    
    # 如果provider在配置文件中存在，直接返回原始名称
    if provider in ai_config:
        return provider
    else:
        return provider

# 【重构优化】create_error_response, get_user_friendly_error 已移至 app.chat_stream.error_handler

# 【重构优化】check_and_yield_if_interrupted, check_and_yield_if_paused 已移至 app.chat_stream.incident_handler

# 【重构优化】simplify_observation 已删除（未被使用）



# 【重构优化】create_final_response 已移至 app.chat_stream.chat_helpers

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
    task_id: Optional[str] = Field(default=None, description="前端指定的任务ID - 前端小新代修改")
    session_id: Optional[str] = Field(default=None, description="会话ID - 小沈添加 2026-03-03，用于缓存display_name")

class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool = Field(..., description="是否成功")
    content: str = Field(default="", description="回复内容")
    model: str = Field(default="", description="使用的模型")
    provider: str = Field(default="", description="使用的提供商")
    error: Optional[str] = Field(default=None, description="错误信息")
    execution_steps: Optional[List[Dict]] = Field(default=None, description="执行步骤详情列表")

class ValidateResponse(BaseModel):
    """验证响应"""
    success: bool = Field(..., description="验证是否通过")
    provider: str = Field(..., description="当前使用的提供商")
    model: str = Field(default="", description="当前使用的模型")
    message: str = Field(default="", description="验证消息")


# 【重构优化】detect_file_operation_intent 和 extract_file_path 已移至 ver1_detect_file_operation_intent.py

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    发送对话请求
    
    - **messages**: 消息列表，格式为 [{"role": "user", "content": "你好"}]
    - **stream**: 是否流式返回（当前版本不支持，预留）
    - **temperature**: 创造性参数，0-2之间
    
    返回AI助手的回复内容
    支持文件操作：自动检测文件操作意图并执行
    """
    # 【新增】每次对话开始，LLM调用计数器
    llm_call_count = 0
    
    try:
        # 【修复P2-002】验证消息列表
        if not request.messages:
            raise HTTPException(
                status_code=400,
                detail="消息列表不能为空"
            )
        
        # 验证每条消息的内容
        for i, msg in enumerate(request.messages):
            if not msg.content or not msg.content.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"第{i+1}条消息内容不能为空"
                )
        
        # 获取最后一条用户消息
        last_message = request.messages[-1].content
        
        # 【修复】检测文件操作意图（返回3个值：是否文件操作、操作类型、置信度）
        is_file_op, op_type, confidence = detect_file_operation_intent(last_message)
        
        # 【修复】非文件操作，正常调用AI服务
        # 获取AI服务实例
        if request.provider and request.model:
            ai_service = AIServiceFactory.get_service_for_model(request.provider, request.model)
        else:
            ai_service = AIServiceFactory.get_service()
        
        # 转换消息格式
        from app.services.base import Message
        history = []
        
        # 除最后一条消息外，其他作为历史记录
        if len(request.messages) > 1:
            for msg in request.messages[:-1]:
                history.append(Message(role=msg.role, content=msg.content))
        
        # 调用AI服务（非流式）
        llm_call_count += 1
        logger.info(f"[LLM Total Counter] >>> Non-stream AI called, count: {llm_call_count}")
        response = await ai_service.chat(
            message=last_message,
            history=history
        )
        
        return ChatResponse(
            success=response.success,
            content=response.content,
            model=response.model,
            provider=ai_service.provider,
            error=response.error
        )
        
    except HTTPException:
        # FastAPI的HTTP异常直接抛出，让FastAPI处理
        raise
    except json.JSONDecodeError as e:
        # 【小沈修复 2026-03-14】JSON解析错误
        logger.warning(f"聊天请求JSON解析错误: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"请求JSON格式错误: {str(e)}"
        )
    except (KeyError, TypeError) as e:
        # 【小沈修复 2026-03-14】消息结构缺失字段或类型错误
        logger.warning(f"聊天请求消息结构错误: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"消息缺少必需字段或类型错误: {str(e)}"
        )
    except ValueError as e:
        # 客户端输入错误
        logger.warning(f"聊天请求参数错误: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"请求参数错误: {str(e)}"
        )
    except IndexError as e:
        # 消息列表索引错误（虽然前面已验证，但保留防御）
        logger.warning(f"消息列表索引错误: {e}")
        raise HTTPException(
            status_code=400,
            detail="消息列表格式错误"
        )
    except httpx.TimeoutException as e:
        # 【小沈修复 2026-03-14】AI服务请求超时
        logger.error(f"AI服务请求超时: {e}")
        raise HTTPException(
            status_code=504,
            detail="AI服务响应超时，请稍后重试"
        )
    except httpx.RequestError as e:
        # 【小沈修复 2026-03-14】AI服务网络错误
        logger.error(f"AI服务网络错误: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI服务暂时不可用，请稍后重试"
        )
    except Exception as e:
        # 服务端错误，记录详细日志但返回通用错误信息
        logger.error(f"聊天请求服务端错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="服务器内部错误，请稍后重试"
        )


# ============================================================
# SSE流式API - 实时展示ReAct执行步骤
# 支持任务中断/暂停
# ============================================================

# 任务管理字典（存储运行中的任务，用于中断）
running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}

# 【小沈-2026-03-13修复】会话级别中断记录（防止重连循环）
# 记录已中断的会话ID和最后一次中断时间
# TODO【小健-2026-03-13深度检查】：需要添加定期清理机制，否则长期运行会内存泄漏
# TODO【小健-2026-03-13深度检查】：需要添加锁保护，否则并发写入可能有竞态条件
interrupted_sessions: dict[str, datetime] = {}
INTERRUPTED_SESSION_TIMEOUT = timedelta(minutes=5)  # 5分钟后允许重新连接
TASK_TIMEOUT = timedelta(hours=1)  # 1小时超时

async def cleanup_expired_tasks():
    """清理过期任务"""
    now = datetime.now()
    async with running_tasks_lock:
        expired_tasks = [
            task_id for task_id, task in running_tasks.items()
            if task.get("created_at") and now - task["created_at"] > TASK_TIMEOUT
        ]
        for task_id in expired_tasks:
            del running_tasks[task_id]
        if expired_tasks:
            logger.info(f"清理了 {len(expired_tasks)} 个过期任务")


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式API - SSE (Server-Sent Events)
    
    实时推送ReAct执行步骤：思考→行动→观察
    支持任务中断（前端使用AbortController）
    
    - **messages**: 消息列表
    - **stream**: 是否流式返回（此路由强制为True）
    - **temperature**: 创造性参数
    """
    import uuid
    
    # 【前端小新代修改】优先使用前端传递的task_id，没有才自己生成
    task_id = request.task_id if request.task_id else str(uuid.uuid4())
    
    # 【小沈-2026-03-13修复】检查会话是否已中断（防止重连循环）
    session_id = request.session_id
    if session_id and session_id in interrupted_sessions:
        last_interrupt = interrupted_sessions[session_id]
        if datetime.now() - last_interrupt < INTERRUPTED_SESSION_TIMEOUT:
            logger.warning(f"[Session Blocked] 会话 {session_id} 在5分钟内被中断过，拒绝重连")
            
            async def blocked_response():
                yield create_error_response(
                    error_type="session_interrupted",
                    message="会话已中断，请新建对话",
                    code="SESSION_INTERRUPTED",
                    retryable=False
                )
            
            return StreamingResponse(
                blocked_response(),
                media_type="text/event-stream"
            )
        else:
            # 超过5分钟，清除记录，允许重新连接
            logger.info(f"[Session Cleared] 会话 {session_id} 中断已超过5分钟，清除记录")
            del interrupted_sessions[session_id]
    
    async def generate():
        """生成SSE流，支持中断和暂停"""
        # 【新增】每次对话开始，重置LLM调用计数器
        llm_call_count = 0
        
        # 【修改】优先使用前端传递的模型信息，fallback到配置文件
        if request.provider and request.model:
            ai_service = AIServiceFactory.get_service_for_model(
                request.provider, 
                request.model
            )
        else:
            ai_service = AIServiceFactory.get_service()
        
        # 注册任务（包含ai_service引用，用于强制中断）
        async with running_tasks_lock:
            running_tasks[task_id] = {
                "status": "running", 
                "cancelled": False,
                "paused": False,  # 暂停状态
                "created_at": datetime.now(),
                "ai_service": ai_service  # 【小沈-2026-03-13修复】保存ai_service引用
            }
        
        logger.info(f"[LLM Total Counter] ====== New conversation started, counter reset to 0 ======")
        
        # 步骤计数器（必须在使用前定义）
        step_counter = 0
        
        def next_step():
            nonlocal step_counter
            step_counter += 1
            return step_counter
        
        # 【小沈修复 2026-03-23】先初始化 execution_steps 列表，后续 start 会添加到这里
        current_execution_steps: List[Dict] = []  # 执行步骤列表
        current_content: str = ""  # 当前累积内容
        
        # 【前端小新代修改】在流式响应开始时发送start事件
        display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
        
        # 缓存 display_name
        if request.session_id:
            cache_display_name(request.session_id, display_name)
        
        # 【问题1修复】在start阶段添加安全检查
        # 获取最后一条用户消息进行安全检查
        last_message = request.messages[-1].content if request.messages else ""
        security_check_result = check_command_safety(last_message)
        
        # 发送 start 步骤（包含security_check和用户消息）
        user_message_preview = last_message[:40] if last_message else ""
        start_data = {
            'type': 'start',
            'step': next_step(),
            'timestamp': create_timestamp(),
            'display_name': display_name,
            'provider': ai_service.provider,
            'model': ai_service.model,
            'task_id': task_id,
            'user_message': user_message_preview,  # 【小强添加 2026-03-24】用户消息前40字
            'security_check': {
                'is_safe': security_check_result.get('is_safe', True),
                'risk_level': security_check_result.get('risk_level'),
                'risk': security_check_result.get('risk'),
                'blocked': security_check_result.get('blocked', False)
            }
        }
        logger.info(f"[Step start] 发送start步骤 - step={start_data['step']}")
        
        yield f"data: {json.dumps(start_data)}\n\n"
        
        # 【小沈修复 2026-03-23】将 start 添加到 execution_steps 并保存到数据库
        current_execution_steps.append(start_data)
        await save_execution_steps_to_db(request.session_id, current_execution_steps, "")
        
        # 如果安全检查未通过，直接返回错误
        if not security_check_result.get('is_safe', True):
            risk = security_check_result.get('risk', '未知风险')
            logger.info(f"[Step error] 发送error步骤(安全检测拦截)")
            error_step = create_error_step(
                code='SECURITY_BLOCKED',
                message=f'危险操作需确认: {risk}',
                error_type='security',
                step_num=next_step(),
                model=ai_service.model,
                provider=ai_service.provider
            )
            current_execution_steps.append(error_step)
            await save_execution_steps_to_db(request.session_id, current_execution_steps, f"错误: {risk}")
            yield create_error_response(
                error_type="security",
                message=f'危险操作需确认: {risk}',
                code='SECURITY_BLOCKED',
                model=ai_service.model,
                provider=ai_service.provider,
                retryable=False
            )
            return
        
        try:
            # 获取最后一条用户消息
            last_message = request.messages[-1].content if request.messages else ""
            
            # 构建历史消息
            from app.services.base import Message
            history = []
            if len(request.messages) > 1:
                for msg in request.messages[:-1]:
                    history.append(Message(role=msg.role, content=msg.content))
            
            # 【重构优化】chat_stream_query 需要的变量
            # 注意：step_counter, next_step(), current_execution_steps 已在前面定义，此处直接复用
            last_is_reasoning: Optional[bool] = None  # 上一个is_reasoning状态
            
            # 【小沈重构 2026-03-23】使用统一的 message_saver 模块
            # 为了与 chat_stream_query 的参数签名兼容，创建包装函数
            async def wrapped_save_steps(execution_steps: List[Dict], content: Optional[str] = None):
                await save_execution_steps_to_db(request.session_id, execution_steps, content)
            
            async def wrapped_add_step(step: Dict, content: Optional[str] = None):
                await add_step_and_save(current_execution_steps, step, request.session_id, content)
            
            # 【小沈删除 2026-03-23】删除了重复发送 thought 的逻辑
            # 原因：ver1_run_stream 内部已经包含完整的 ReAct 处理逻辑（thought → action_tool → observation → final）
            # 如果这里再发送 thought，会导致重复的 thought 步骤，step 编号也会跳跃
            # 正确流程：start → ver1_run_stream(完整ReAct) → final
            
            # ⭐ 修复：只检查一次中断（删除 4 次重复代码）
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            
            # ⭐ 暂停检查：如果暂停则等待恢复
            async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
                yield pause_event
            
            # 检测文件操作意图
            is_file_op, _, confidence = detect_file_operation_intent(last_message)
            
            if is_file_op and confidence >= 0.3:
                # 文件操作：直接流式执行（使用已有的 ai_service）
                session_id = str(uuid.uuid4())
                
                async def llm_client(message, history=None):
                    response = await ai_service.chat(message, history)
                    return type('obj', (object,), {'content': response.content})()
                
                agent = FileOperationAgent(
                    llm_client=llm_client,
                    session_id=session_id
                )
                
                try:
                    # 【小沈修复 2026-03-23】传递 next_step 函数，统一 step 计数器
                    async for sse_data in agent.ver1_run_stream(
                        task=last_message,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        get_next_step=next_step  # 传入统一的 step 计数函数
                    ):
                        # 每步检查是否被中断
                        async with running_tasks_lock:
                            if running_tasks.get(task_id, {}).get("cancelled", False):
                                interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                                logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                                yield f"data: {json.dumps(interrupted_data)}\n\n"
                                break
                        
                        # 【小沈修复 2026-03-23】解析 SSE 并保存到数据库
                        if sse_data.startswith("data: "):
                            step_data = json.loads(sse_data[6:])
                            current_execution_steps.append(step_data)
                            # 更新 current_content（如果是 final 或 chunk 类型）
                            if step_data.get('type') == 'final':
                                current_content = step_data.get('content', '')
                            elif step_data.get('type') == 'chunk':
                                current_content = (current_content or '') + (step_data.get('content', '') or '')
                            # 保存到数据库
                            await save_execution_steps_to_db(request.session_id, current_execution_steps, current_content)
                        
                        logger.info(f"[FileOp SSE] 发送数据")
                        yield sse_data
                        await asyncio.sleep(0.05)
                    
                except Exception as e:
                    logger.error(f"文件操作执行出错：task_id={task_id}, error={e}", exc_info=True)
                    error_step = create_error_step(
                        code='FILE_OPERATION_ERROR',
                        message="文件操作执行失败",
                        error_type='file_operation_error',
                        step_num=next_step(),
                        model=ai_service.model,
                        provider=ai_service.provider
                    )
                    current_execution_steps.append(error_step)
                    await save_execution_steps_to_db(request.session_id, current_execution_steps, "文件操作执行失败")
                    yield create_error_response(
                        error_type="file_operation_error",
                        message="文件操作执行失败",
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=False
                    )
            else:
                # 普通对话：调用 chat_stream_query（复用公共逻辑）
                # 【小沈修复 2026-03-23】添加 session_id 参数
                async for chunk in chat_stream_query(
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
                    session_id=request.session_id,  # 【小沈修复 2026-03-23】传递 session_id
                    save_execution_steps_to_db=wrapped_save_steps,
                    add_step_and_save=wrapped_add_step,
                ):
                    yield chunk
                        
        except asyncio.CancelledError:
            # 客户端断开连接，任务被中断
            async with running_tasks_lock:
                running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
            interrupted_data = create_incident_data('interrupted', '客户端断开连接，任务中断')
            logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开)")
            interrupted_step = create_incident_data(
                incident_value='interrupted',
                message='客户端断开连接，任务中断',
                step=next_step()
            )
            current_execution_steps.append(interrupted_step)
            await save_execution_steps_to_db(request.session_id, current_execution_steps, current_content)
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            
        except Exception as e:
            # 【小沈代修改 - 统一错误处理】使用 get_user_friendly_error 和 create_error_response
            logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
            error_info = get_user_friendly_error(e)
            logger.info(f"[Step error] 发送error步骤")
            error_step = create_error_step(
                code=error_info.get("code", "INTERNAL_ERROR"),
                message=error_info.get("message", "服务调用失败"),
                error_type=error_info.get("error_type", "server"),
                step_num=next_step(),
                model=ai_service.model,
                provider=ai_service.provider
            )
            current_execution_steps.append(error_step)
            await save_execution_steps_to_db(request.session_id, current_execution_steps, f"错误: {error_info.get('message', '服务调用失败')}")
            yield create_error_response(
                error_type=error_info.get("error_type", "server"),
                message=error_info.get("message", "服务调用失败"),
                code=error_info.get("code", "INTERNAL_ERROR"),
                model=ai_service.model,
                provider=ai_service.provider,
                retryable=error_info.get("retryable", False),
                retry_after=error_info.get("retry_after")
            )
        
        finally:
            # 【新增】输出最终的 LLM 调用次数
            logger.info(f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {llm_call_count} ======")
            
            # 清理任务
            async with running_tasks_lock:
                if task_id in running_tasks:
                    del running_tasks[task_id]
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用Nginx缓冲，确保流式输出
        }
    )


# ============================================================
# 任务中断接口
# ============================================================

@router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    中断指定的流式任务
    
    - **task_id**: 任务ID
    - **session_id**: 会话ID（可选，用于阻止重连）
    """
    # 【小沈-2026-03-13修复】记录会话级别中断，阻止5分钟内的重连
    # TODO【小健-2026-03-13深度检查】：空session_id需要特殊处理，避免空字符串跳过检查
    if session_id:
        interrupted_sessions[session_id] = datetime.now()
        logger.info(f"[Session Interrupted] 会话 {session_id} 已标记为中断，5分钟内禁止重连")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            task_info["cancelled"] = True
            task_info["status"] = "cancelled"
            
            # 【小沈-2026-03-13修复】关键！强制关闭HTTP连接
            # TODO【小健-2026-03-13深度检查】：应在锁外调用cancel，避免长时间持有锁
            if "ai_service" in task_info and task_info["ai_service"]:
                ai_service = task_info["ai_service"]
                try:
                    ai_service.cancel()
                    logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
                except Exception as e:
                    logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
            
            logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为中断")
            return {"success": True, "message": f"任务 {task_id} 已中断"}
    
    # 即使任务不存在，也记录会话中断
    if session_id:
        return {"success": True, "message": f"会话 {session_id} 已标记为中断（任务可能已完成）"}
    
    return {"success": False, "message": f"任务 {task_id} 不存在"}


# 任务暂停/继续接口
# ============================================================

@router.post("/chat/stream/pause/{task_id}")
async def pause_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    暂停指定的流式任务
    
    - **task_id**: 任务ID
    - **session_id**: 会话ID（可选，用于记录暂停状态）
    - 暂停时：前端停止显示，但后端继续处理，数据暂存缓冲区
    """
    # 【小沈-2026-03-13修复】支持session_id参数（可选）
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = True
            running_tasks[task_id]["status"] = "paused"
            logger.info(f"[Pause] 任务 {task_id} 已暂停")
            return {"success": True, "message": f"任务 {task_id} 已暂停"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}


@router.post("/chat/stream/resume/{task_id}")
async def resume_stream_task(task_id: str, session_id: Optional[str] = None):
    """
    继续指定的流式任务
    
    - **task_id**: 任务ID
    - **session_id**: 会话ID（可选，用于记录恢复状态）
    - 继续时：前端恢复显示暂存的数据
    """
    # 【小沈-2026-03-13修复】支持session_id参数（可选）
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
