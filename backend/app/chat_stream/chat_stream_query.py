# -*- coding: utf-8 -*-
"""
流式问答处理模块

从 chat_stream.py 的 generate() 函数中拆分的流式问答逻辑
用于处理问答类消息（无文件操作）

Author: 小沈 - 2026-03-22
"""

import json
import asyncio
from typing import List, Dict, Optional, Any, Callable, AsyncGenerator

from app.services.llm_core import Message
from app.utils.retry_controller import RetryController
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError
from app.chat_stream.chat_helpers import create_timestamp, create_final_response
from app.chat_stream.error_handler import create_error_response, create_error_step, get_stream_error_info, resolve_http_error_type
from app.chat_stream.incident_handler import (
    create_incident_data,
    check_and_yield_if_paused,
    check_and_yield_if_interrupted,
)
from app.utils.logger import logger
from app.config import get_config


async def chat_stream_query(
    request,
    ai_service,
    task_id: str,
    llm_call_count: int,
    current_execution_steps: List[Dict],
    current_content: str,
    last_is_reasoning: Optional[bool],
    last_message: str,
    running_tasks: dict,
    running_tasks_lock: asyncio.Lock,
    next_step: Callable[[], int],
    display_name: str,
    session_id: Optional[str],  # 【小沈修复 2026-03-23】添加 session_id 参数
    save_execution_steps_to_db: Callable,
    add_step_and_save: Callable,
) -> AsyncGenerator[str, None]:
    """
    流式问答处理函数
    
    处理问答类消息的流式响应，无文件操作
    流程：start → thought → chunk → final
    
    参数：
    - request: ChatRequest 对象
    - ai_service: AI服务实例
    - task_id: 任务ID
    - llm_call_count: LLM调用计数器
    - current_execution_steps: 执行步骤列表
    - current_content: 当前累积内容
    - last_is_reasoning: 上一个is_reasoning状态
    - last_message: 最后一条用户消息
    - running_tasks: 运行中的任务字典
    - running_tasks_lock: 任务锁
    - next_step: 获取下一个步骤号的函数
    - display_name: 显示名称
    - save_execution_steps_to_db: 保存到数据库的函数
    - add_step_and_save: 添加步骤并保存的函数
    
    Author: 小沈 - 2026-03-22
    """
    
    # 检查是否被中断
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            interrupted_data = create_incident_data(
                'interrupted', 
                '任务已被中断', 
                step=next_step()
            )
            # logger.info(f"[Step incident] 发送incident步骤 - incident_type=interrupted, message=任务已被中断")
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            return
    
    # 构建历史消息
    history = []
    if len(request.messages) > 1:
        for msg in request.messages[:-1]:
            history.append(Message(role=msg.role, content=msg.content))
    
    # 统一的空闲超时和重试机制
    # 空闲超时由 IdleTimeoutIterator 实时检测，重试次数由 RetryController 管理
    # 使用 AI 服务提供商的超时配置（更准确）
    chat_timeout = ai_service.timeout if hasattr(ai_service, 'timeout') and ai_service.timeout else 60
    max_retries = 3  # 默认3次
    retry_controller = RetryController(max_retries=max_retries)
    ai_call_successful = False
    last_error = None
    last_error_type = None
    
    full_content = ""
    chunk_count = 0
    # 【小沈修复 2026-03-17】添加保护机制：防止AI一直输出reasoning导致流式不结束
    max_chunk_count = 5000  # 最大chunk数量
    empty_content_count = 0  # 连续空content次数
    max_empty_content_count = 100  # 最大连续空content次数
    
    for retry_attempt in range(max_retries + 1):
        if retry_attempt > 0:
            # 发送重试提示给前端
            retry_data = create_incident_data(
                'retrying', 
                f'请求超时，正在重试 ({retry_attempt}/{max_retries})...', 
                step=next_step()
            )
            yield f"data: {json.dumps(retry_data)}\n\n"
            # 保存 retrying 步骤到数据库
            await add_step_and_save(retry_data, None)
            # logger.info(f"[Retry] 开始第{retry_attempt + 1}次AI调用（共{max_retries + 1}次）")
        
        # 使用流式API，逐token返回
        full_content = ""
        chunk_count = 0
        has_received_content = False  # 本次调用是否收到内容
        chunk = None  # 初始化
        idle_timeout_stream = None  # 初始化，用于异常处理中获取空闲时间
        
        try:
            llm_call_count += 1
            # logger.info(f"[LLM Total Counter] >>> Stream AI called, count: {llm_call_count}")
            
            # 【小沈修复】使用 IdleTimeoutIterator 包装流式迭代器，实现实时空闲超时检测
            # 超时时间从配置读取
            idle_timeout_stream = IdleTimeoutIterator(
                ai_service.chat_stream(message=last_message, history=history),
                timeout_seconds=float(chat_timeout),
                name=f"AI-Stream-{retry_attempt + 1}"
            )
            
            async for chunk in idle_timeout_stream:
                # 注意：IdleTimeoutIterator 自动检测空闲超时，收到内容时自动重置计时器
                # 如果30秒内没有下一个 chunk，会抛出 IdleTimeoutError
                
                chunk_count += 1
                
                # 【小沈修复 2026-03-17】保护机制：防止AI一直输出reasoning导致流式不结束
                if chunk_count > max_chunk_count:
                    logger.warning(f"[AI Call] 超过最大chunk数量 {max_chunk_count}，强制结束")
                    break
                if not chunk.content and getattr(chunk, 'is_reasoning', False):
                    empty_content_count += 1
                    if empty_content_count > max_empty_content_count:
                        logger.warning(f"[AI Call] 连续 {max_empty_content_count} 次无实际内容，强制结束")
                        break
                else:
                    empty_content_count = 0
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        interrupted_data = create_incident_data(
                            'interrupted', 
                            '任务已被中断', 
                            step=next_step()
                        )
                        # logger.info(f"[Step incident] 发送incident步骤 - incident_type=interrupted, message=任务已被中断")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        return
                
                # 暂停检查：AI流式响应过程中也检查暂停状态
                async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock, next_step):
                    yield pause_event
                
                # 检查chunk是否有错误（非空闲超时错误）
                if chunk.stream_error:
                    last_error = chunk.stream_error
                    last_error_type = getattr(chunk, 'stream_error_type', 'unknown')
                    logger.warning(f"[AI Call] 流式请求返回错误: {chunk.stream_error}, error_type: {last_error_type}")
                    # 非空闲超时错误，直接报错不重试
                    logger.error(f"[AI Call] 检测到错误，不重试: {chunk.stream_error}")
                    ai_call_successful = False
                    break
                
                # 【小沈修复 2026-03-28】只处理有内容的chunk，空chunk不需要保存和发送
                # 空chunk：LLM在超时重试时确实没返回内容，既不显示也不需要保存
                current_is_reasoning = getattr(chunk, 'is_reasoning', False)
                
                # 只处理有内容的chunk
                if chunk.content:
                    chunk_data = {
                        'type': 'chunk', 
                        'step': next_step(),  # 添加step字段
                        'timestamp': create_timestamp(),
                        'content': chunk.content,
                        'is_reasoning': current_is_reasoning
                    }
                    current_execution_steps.append(chunk_data)
                    
                    has_received_content = True
                    full_content += chunk.content
                    current_content = full_content  # 累积content
                    
                    # 【小沈修复 2026-03-16】is_reasoning变化时保存，确保回答部分完整
                    if last_is_reasoning != current_is_reasoning:
                        try:
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                        except Exception as e:
                            logger.error(f"[Save] is_reasoning变化保存失败: {e}", exc_info=True)
                        last_is_reasoning = current_is_reasoning
                    
                    # 发送chunk给前端
                    yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                if chunk.is_done:
                    break
            
        except IdleTimeoutError as e:
            # 【关键】空闲超时异常 - 由 IdleTimeoutIterator 实时检测
            last_error = str(e)
            last_error_type = 'idle_timeout'
            elapsed = idle_timeout_stream.get_elapsed_time() if idle_timeout_stream else chat_timeout
            logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时：{elapsed:.1f}秒无内容")
            # 空闲超时进入后面的重试判断逻辑
        
        except Exception as e:
            last_error = str(e)
            last_error_type = 'network_error'
            logger.error(f"[AI Call] 第{retry_attempt + 1}次调用异常: {e}")
            # 其他异常进入后面的错误判断逻辑
        
        # 【小沈-2026-03-14重构】统一的重试判断逻辑
        # 判断优先级：1.收到内容成功 → 2.空闲超时重试 → 3.网络错误重试 → 4.其他错误失败
        
        if has_received_content:
            # ✅ 已经收到过内容，说明模型在工作
            ai_call_successful = True
            # logger.info(f"[AI Call] 第{retry_attempt + 1}次调用成功（已收到内容）")
            break  # 【关键】成功后立即退出重试循环
        
        elif last_error_type == 'idle_timeout':
            # ⚠️ 空闲超时（无内容）
            if retry_controller.can_retry():
                # 还能重试
                retry_controller.increment_retry()
                logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时{elapsed:.0f}秒，准备第{retry_controller.get_retry_count() + 1}次重试...")
                continue
            else:
                # 已达最大重试次数
                logger.error(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时，已达最大重试次数{max_retries}")
                last_error = f"空闲超时：模型{elapsed:.0f}秒未响应"
                ai_call_successful = False
                break
        
        elif last_error_type == 'network_error':
            # ⚠️ 网络错误（连接失败、读取失败等）
            if retry_controller.can_retry():
                # 还能重试
                retry_controller.increment_retry()
                logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用网络错误，准备第{retry_controller.get_retry_count() + 1}次重试...")
                continue
            else:
                # 已达最大重试次数
                logger.error(f"[AI Call] 第{retry_attempt + 1}次调用网络错误，已达最大重试次数{max_retries}")
                ai_call_successful = False
                break
        
        elif last_error:
            # ❌ 有其他错误（非空闲超时、非网络错误）
            logger.error(f"[AI Call] 第{retry_attempt + 1}次调用失败（其他错误）: {last_error}")
            ai_call_successful = False
            break
        
        else:
            # 【边界情况】流正常结束但无内容（模型思考中或空响应）
            # 【小沈&小新修复 2026-03-14】检查是否收到内容
            if has_received_content and full_content.strip():
                # 收到了有效内容，判断为成功
                ai_call_successful = True
                # logger.info(f"[AI Call] 第{retry_attempt + 1}次调用完成，收到内容长度={len(full_content)}")
                break
            else:
                # 【修复】未收到内容，视为错误，发送error步骤
                logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用完成但无内容（流结束，模型未返回有效内容）")
                if retry_controller.can_retry():
                    # 还能重试
                    retry_controller.increment_retry()
                    # logger.info(f"[AI Call] 空响应，准备第{retry_controller.get_retry_count() + 1}次重试...")
                    continue
                else:
                    # 已达最大重试次数，发送error步骤
                    # 【小沈修复 2026-03-23】只调用一次 next_step()，避免 step 多 1
                    logger.error(f"[AI Call] 空响应重试失败，已达最大重试次数{max_retries}")
                    error_message = "模型未能生成有效回复，请尝试更换问题或稍后重试"
                    error_step_value = next_step()
                    yield create_error_response(
                        error_type="empty_response",
                        message=error_message,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=True,
                        retry_after=3,
                        step=error_step_value
                    )
                    
                    # 保存error步骤到数据库【小沈修复 2026-03-28】使用create_error_step函数确保字段完整
                    error_step = create_error_step(
                        code='EMPTY_RESPONSE',
                        message=error_message,
                        error_type='empty_response',
                        step_num=error_step_value,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=True,
                        retry_after=3
                    )
                    await add_step_and_save(error_step, f"错误: {error_message}")
                    return  # 直接返回，不再发送final步骤
    
    # 【重试机制】重试循环结束，检查最终结果
    if not ai_call_successful:
        logger.error(f"[AI Call] 重试失败，ai_call_successful={ai_call_successful}")
        # 根据错误原因返回不同的错误提示
        if last_error:
            logger.error(f"[AI Call] 所有重试失败，最后错误: {last_error}, 类型: {last_error_type}")
            
            # 【小沈重构 2026-04-10】调用统一错误解析函数
            # 从 last_error 字符串中解析真实错误码，而不是依赖 stream_error_type
            resolved_error_type = resolve_http_error_type(last_error)
            
            # 如果解析到了具体错误类型，使用解析结果；否则使用 last_error_type
            final_error_type = resolved_error_type if resolved_error_type else last_error_type
            
            # 使用 get_stream_error_info() 获取错误信息
            error_type, error_message = get_stream_error_info(final_error_type)
            # idle_timeout 需要动态显示实际超时值和重试次数
            if last_error_type == 'idle_timeout':
                total_timeout = chat_timeout * max_retries
                error_type = 'timeout'
                error_message = f"请求超时：AI模型({display_name}) {chat_timeout}秒内未返回任何内容，已重试{max_retries}次，合计{total_timeout}秒，请更换问题或稍后重试"
        else:
            # 没有错误但也没有收到有效内容，可能是模型返回空响应
            logger.error(f"[AI Call] 所有重试失败，无有效响应（模型返回空内容）")
            error_type, error_message = "empty_response", "模型未能生成有效回复，请尝试更换问题或稍后重试"
        
        # 发送error步骤而不是final步骤
        # 【小沈修复 2026-03-23】只调用一次 next_step()，避免 step 多 1
        # logger.info(f"[Step error] 发送error步骤: error_type={error_type}, message={error_message}")
        error_step_value = next_step()
        yield create_error_response(
            error_type=error_type,
            message=error_message,
            model=ai_service.model,
            provider=ai_service.provider,
            retryable=True,
            retry_after=3,
            step=error_step_value
        )
        
        # 保存error步骤到数据库【小沈修复 2026-03-28】使用create_error_step函数确保字段完整
        error_step = create_error_step(
            code='AI_CALL_ERROR',
            message=error_message,
            error_type=error_type,
            step_num=error_step_value,
            model=ai_service.model,
            provider=ai_service.provider,
            retryable=True,
            retry_after=3
        )
        await add_step_and_save(error_step, f"错误: {error_message}")
        return  # 直接返回，不再发送final步骤
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # 【小沈修复 2026-03-17 问题分析与修复说明】
    #
    # 问题：AI消息的execution_steps数据丢失（完整数据112条→数据库只有99条）
    #
    # 根因分析：
    #   1. 后端在流式结束时自动保存完整数据（包含所有steps，112条）
    #   2. 前端onComplete也调用saveExecutionSteps，传99条覆盖后端数据
    #   3. 前后端重复保存，后保存的覆盖先保存的
    #
    # 修复方案：
    #   1. 先添加final步骤到current_execution_steps数组
    #   2. 保存一次到数据库（包含完整steps）
    #   3. 删除后续的重复保存代码
    #   4. 前端配合：删除onComplete中的saveExecutionSteps调用
    #
    # 数据流：后端生成steps → 后端保存1次 → 前端不再保存
    # 核心思想：数据由后端生成，后端自己知道完整数据，不需要前端指挥
    # ═══════════════════════════════════════════════════════════════════════════════
    
    # 先添加final步骤到数组，再保存
    # 【小沈修复 2026-03-23】只调用一次 next_step()，避免 final 步骤的 step 多 1
    final_step_value = next_step()
    final_step = {
        'type': 'final',
        'step': final_step_value,
        'content': full_content,
        'model': ai_service.model,
        'provider': ai_service.provider,
        'timestamp': create_timestamp()
    }
    current_execution_steps.append(final_step)
    
    # final前强制保存一次，确保所有steps都写入数据库
    # logger.info(f"[Step final] 💾 final前强制保存: {len(current_execution_steps)} steps")
    # 【警告 2026-03-23】此处调用存在参数错位问题：
    # save_execution_steps_to_db 期望签名：(session_id, execution_steps, content)
    # 但这里只传了2个参数：(current_execution_steps, full_content)
    # 导致：session_id=List[Dict], execution_steps=str
    # 在 chat2.py 调用 chat_stream_query 时，传递的是 wrapped_save_steps 闭包（已绑定session_id）
    # 所以这里不会执行到，只有直接调用 chat_stream_query 时才有问题
    await save_execution_steps_to_db(current_execution_steps, full_content)
    
    # 发送最终结果，【新增】添加provider字段作为兜底
    content_preview = full_content[:200] + "..." if len(full_content) > 200 else full_content
    # logger.info(f"[Step final] 🚀 发送final步骤, content长度={len(full_content)}, content预览={content_preview}")
    # 【小沈修复 2026-03-23】复用 final_step_value，避免 step 多 1
    yield create_final_response(
        content=full_content,
        model=ai_service.model,
        provider=ai_service.provider,
        display_name=display_name,
        step=final_step_value
    )
