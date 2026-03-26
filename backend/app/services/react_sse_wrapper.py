# -*- coding: utf-8 -*-
"""
React SSE Wrapper - SSE 流式包装层

【第二阶段实现 - 2026-03-26 小沈】
从 chat2.py 复制，删除路由判断，保留通用职责。

架构：
- 第一层：chat_router.py - 路由入口
- 第二层：react_sse_wrapper.py - SSE 包装（本文件）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【阶段2目标】
- 从 chat2.py 复制为 react_sse_wrapper.py
- 删除路由判断（if is_file_op）
- 删除意图检测代码
- 保留任务管理、DB保存等通用职责

【本文件说明】
- 作为服务层，不包含 FastAPI 路由
- 提供 SSE 流式生成器函数，供 chat_router.py 调用
- 保留任务管理变量和函数

Author: 小沈 - 2026-03-26
"""

import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable
from app.services import AIServiceFactory
from app.services.base import Message
from app.services.shell_security import check_command_safety
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused, create_incident_data
from app.chat_stream.error_handler import create_error_response, get_user_friendly_error, create_error_step
from app.chat_stream.chat_helpers import create_final_response, create_timestamp, create_step_counter
from app.chat_stream.message_saver import save_execution_steps_to_db, add_step_and_save, create_add_step_and_save, parse_and_save_sse


# ============================================================
# 任务管理相关（服务层可被外部调用）
# ============================================================

# 任务管理字典（存储运行中的任务，用于中断）
running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}

# 会话级别中断记录（防止重连循环）
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


# ============================================================
# SSE 流式生成器函数（供 chat_router.py 调用）
# ============================================================

async def generate_sse_stream(
    messages: List[Dict[str, str]],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成器 - 实时展示ReAct执行步骤
    
    供 chat_router.py 调用，返回 AsyncGenerator 用于 SSE 流式输出。
    
    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}]
        provider: AI 服务提供商
        model: AI 模型
        temperature: 创造性参数
        task_id: 任务ID（可选）
        session_id: 会话ID（可选）
    
    Yields:
        SSE 格式的数据字符串
    """
    # 生成 task_id
    if not task_id:
        task_id = str(uuid.uuid4())
    
    # 【小沈-2026-03-13修复】检查会话是否已中断（防止重连循环）
    if session_id and session_id in interrupted_sessions:
        last_interrupt = interrupted_sessions[session_id]
        if datetime.now() - last_interrupt < INTERRUPTED_SESSION_TIMEOUT:
            logger.warning(f"[Session Blocked] 会话 {session_id} 在5分钟内被中断过，拒绝重连")
            
            blocked_response = create_error_response(
                error_type="session_interrupted",
                message="会话已中断，请新建对话",
                code="SESSION_INTERRUPTED",
                retryable=False
            )
            yield blocked_response
            return
        else:
            # 超过5分钟，清除记录，允许重新连接
            logger.info(f"[Session Cleared] 会话 {session_id} 中断已超过5分钟，清除记录")
            del interrupted_sessions[session_id]
    
    # 每次对话开始，重置LLM调用计数器
    llm_call_count = 0
    
    # 优先使用前端传递的模型信息，fallback到配置文件
    if provider and model:
        ai_service = AIServiceFactory.get_service_for_model(provider, model)
    else:
        ai_service = AIServiceFactory.get_service()
    
    # 注册任务（包含ai_service引用，用于强制中断）
    async with running_tasks_lock:
        running_tasks[task_id] = {
            "status": "running", 
            "cancelled": False,
            "paused": False,
            "created_at": datetime.now(),
            "ai_service": ai_service
        }
    
    logger.info(f"[LLM Total Counter] ====== New conversation started, counter reset to 0 ======")
    
    # 步骤计数器（使用统一函数）
    next_step = create_step_counter()
    
    # 初始化 execution_steps 列表
    current_execution_steps: List[Dict] = []
    current_content: str = ""
    
    # 获取 display_name
    display_name = f"{ai_service.provider} ({ai_service.model})"
    
    # 缓存 display_name
    if session_id:
        cache_display_name(session_id, display_name)
    
    # 安全检查
    last_message = messages[-1]["content"] if messages else ""
    security_check_result = check_command_safety(last_message)
    
    # 发送 start 步骤
    user_message_preview = last_message[:40] if last_message else ""
    start_data = {
        'type': 'start',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'display_name': display_name,
        'provider': ai_service.provider,
        'model': ai_service.model,
        'task_id': task_id,
        'user_message': user_message_preview,
        'security_check': {
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    }
    logger.info(f"[Step start] 发送start步骤 - step={start_data['step']}")
    
    yield f"data: {json.dumps(start_data)}\n\n"
    
    # 将 start 添加到 execution_steps 并保存到数据库
    current_execution_steps.append(start_data)
    await save_execution_steps_to_db(session_id, current_execution_steps, "")
    
    # 安全检查未通过，返回错误
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
        await save_execution_steps_to_db(session_id, current_execution_steps, f"错误: {risk}")
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
        # 构建历史消息
        history = []
        if len(messages) > 1:
            for msg in messages[:-1]:
                history.append(Message(role=msg["role"], content=msg["content"]))
        
        # 检查中断
        is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
        if is_interrupted:
            yield interrupt_msg
            return
        
        # 暂停检查
        async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
            yield pause_event
        
        # 【阶段2】直接使用 FileReactAgent（意图检测已移至 chat_router.py）
        session_id = session_id or str(uuid.uuid4())
        
        async def llm_client(message, history=None):
            response = await ai_service.chat(message, history)
            return type('obj', (object,), {'content': response.content})()
        
        from app.services.agent import FileReactAgent
        agent = FileReactAgent(
            llm_client=llm_client,
            session_id=session_id
        )
        
        try:
            async for sse_data in agent.ver1_run_stream(
                task=last_message,
                model=ai_service.model,
                provider=ai_service.provider,
                get_next_step=next_step
            ):
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        break
                
                if sse_data.startswith("data: "):
                    step_data = json.loads(sse_data[6:])
                    current_execution_steps.append(step_data)
                    if step_data.get('type') == 'final':
                        current_content = step_data.get('content', '')
                    elif step_data.get('type') == 'chunk':
                        current_content = (current_content or '') + (step_data.get('content', '') or '')
                    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
                
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
            await save_execution_steps_to_db(session_id, current_execution_steps, "文件操作执行失败")
            yield create_error_response(
                error_type="file_operation_error",
                message="文件操作执行失败",
                model=ai_service.model,
                provider=ai_service.provider,
                retryable=False
            )
    
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
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
        yield f"data: {json.dumps(interrupted_data)}\n\n"
    
    except Exception as e:
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
        await save_execution_steps_to_db(session_id, current_execution_steps, f"错误: {error_info.get('message', '服务调用失败')}")
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
        logger.info(f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {llm_call_count} ======")
        
        async with running_tasks_lock:
            if task_id in running_tasks:
                del running_tasks[task_id]


# ============================================================
# 任务控制函数（供外部调用）
# ============================================================

async def cancel_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    中断指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选，用于阻止重连）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        interrupted_sessions[session_id] = datetime.now()
        logger.info(f"[Session Interrupted] 会话 {session_id} 已标记为中断，5分钟内禁止重连")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            task_info["cancelled"] = True
            task_info["status"] = "cancelled"
            
            # 强制关闭HTTP连接
            if "ai_service" in task_info and task_info["ai_service"]:
                ai_service = task_info["ai_service"]
                try:
                    ai_service.cancel()
                    logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
                except Exception as e:
                    logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
            
            logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为中断")
            return {"success": True, "message": f"任务 {task_id} 已中断"}
    
    if session_id:
        return {"success": True, "message": f"会话 {session_id} 已标记为中断（任务可能已完成）"}
    
    return {"success": False, "message": f"任务 {task_id} 不存在"}


async def pause_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    暂停指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Pause] 会话 {session_id} 暂停任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = True
            running_tasks[task_id]["status"] = "paused"
            logger.info(f"[Pause] 任务 {task_id} 已暂停")
            return {"success": True, "message": f"任务 {task_id} 已暂停"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}


async def resume_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    继续指定的流式任务
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选）
    
    Returns:
        {"success": bool, "message": str}
    """
    if session_id:
        logger.info(f"[Resume] 会话 {session_id} 恢复任务 {task_id}")
    
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
