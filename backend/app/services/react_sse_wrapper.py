# -*- coding: utf-8 -*-
"""
React SSE Wrapper - SSE 流式包装层

【阶段6实现 - 2026-03-27 小沈】
从 chat2.py 复制，删除路由判断，保留通用职责。

架构：
- 第一层：chat_router.py - 路由入口（发送start步骤）
- 第二层：react_sse_wrapper.py - SSE 包装（本文件，根据intent_type分发）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【阶段6目标】
- 添加 intent_type 和 confidence 参数
- 根据 intent_type 分发到不同 Agent
- 使用 agent.run_stream() 返回 event dict
- 添加 SSE 格式化逻辑
- 注意：start 步骤由 chat_router 发送，本层不重复发送

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
from app.services.llm_core import Message
from app.services.command_security import check_command_safety
from app.config import get_config
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused, create_incident_data
from app.chat_stream.error_handler import create_error_response
from app.services.agent.reasoning_steps import StepFactory
from app.chat_stream.chat_helpers import create_final_response, create_timestamp, create_step_counter
from app.chat_stream.message_saver import save_execution_steps_to_db, add_step_and_save, create_add_step_and_save, parse_and_save_sse
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse, format_sse_event
from app.services.agent.base_react import DEFAULT_MAX_STEPS
from app.services.intents.crss_scorer import CRSS_CONFIDENCE_THRESHOLD  # 【修复 2026-05-13 小沈】H2: 改为从crss_scorer导入，切断与chat_router的循环依赖


# ============================================================
# LLMClientWrapper - 统一 LLM 客户端接口
# ============================================================

class LLMClientWrapper:
    """
    LLM 客户端包装器，提供统一的接口
    
    修复 P6/P7 问题：llm_client 缺少 chat_with_tools 和 chat_with_response_format 方法
    """
    
    def __init__(self, ai_service):
        self.ai_service = ai_service
        # 【修复 2026-05-10 小健】透传ai_service属性，供strategy日志诊断使用
        self.model = getattr(ai_service, 'model', None)
        self.api_base = getattr(ai_service, 'api_base', None)
        self.api_key = getattr(ai_service, 'api_key', None)
        self.provider = getattr(ai_service, 'provider', None)
    
    async def chat(self, message, history=None):
        """基础聊天方法"""
        return await self.ai_service.chat(message, history)
    
    async def chat_with_tools(self, message, history, tools):
        """带工具调用的聊天方法"""
        return await self.ai_service.chat_with_tools(message, history, tools)
    
    async def chat_with_response_format(self, message, history, response_format):
        """带响应格式的聊天方法"""
        return await self.ai_service.chat_with_response_format(message, history, response_format)
    
    async def __call__(self, message, history=None):
        """使对象可被调用（实现 Callable 接口）
        
        用于兼容 llm_strategies.py 中 llm_client() 的调用方式
        """
        return await self.chat(message, history)


# ============================================================
# SSE 格式化函数
# ============================================================

def _format_sse_event(event: Dict[str, Any], step: int, model: str, provider: str) -> str:
    """
    将 event dict 格式化为 SSE 字符串
    
    Args:
        event: event dict from agent.run_stream()
        step: 步骤编号
        model: 模型名称（用于 final/error 响应）
        provider: 提供商（用于 final/error 响应）
    
    Returns:
        SSE 格式的字符串
    """
    event_type = event.get('type', '')
    
    if event_type == 'thought':
        return format_thought_sse(
            step=step,
            content=event.get('content', ''),
            thought=event.get('thought', ''),
            reasoning=event.get('reasoning', ''),
            tool_name=event.get('tool_name', event.get('action_tool', '')),
            tool_params=event.get('tool_params', event.get('params', {}))
        )
    elif event_type == 'action_tool':
        return format_action_tool_sse(
            step=step,
            tool_name=event.get('tool_name', ''),
            tool_params=event.get('tool_params', {}),
            execution_status=event.get('execution_status', 'success'),
            summary=event.get('summary', ''),
            execution_result=event.get('execution_result'),  # 【15.7修改】raw_data替换为execution_result
            error_message=event.get('error_message', ''),  # 【15.7新增】
            execution_time_ms=event.get('execution_time_ms', 0),  # 【15.7新增】
            action_retry_count=event.get('action_retry_count', 0)
        )
    elif event_type == 'observation':
        return format_observation_sse(
            step=step,
            observation=event.get('observation', ''),  # 【15.7修改】content替换为observation
            tool_name=event.get('tool_name', ''),
            tool_params=event.get('tool_params', {}),  # 【15.7新增】
            return_direct=event.get('return_direct', False),  # 【15.7新增】
            timestamp=event.get('timestamp', '')
        )
    elif event_type == 'final':
        # 【15.7修改】final字段：content→response，新增is_finished/thought/is_streaming/is_reasoning
        return create_final_response(
            content=event.get('response', ''),  # content替换为response
            step=step,
            display_name=f"{provider} ({model})",
            provider=provider,
            model=model,
            is_finished=event.get('is_finished', True),  # 【15.7新增】
            thought=event.get('thought', ''),  # 【15.7新增】
            is_streaming=event.get('is_streaming', False),  # 【15.7新增】
            is_reasoning=event.get('is_reasoning', False)  # 【15.7新增】
        )
    elif event_type == 'incident':
        # 【问题2修复】incident类型直接格式化为SSE（base_react.py已使用create_incident_data产生标准格式）
        return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    elif event_type == 'interrupted':
        # 【兼容层】处理仍发送type="interrupted"的旧代码路径，转换为incident格式
        incident_data = create_incident_data(
            'interrupted',
            event.get('message', '用户取消了任务'),
            step=step
        )
        return f"data: {json.dumps(incident_data, ensure_ascii=False)}\n\n"
    elif event_type == 'error':
        # 【15.7修改】error字段：删除code和message，使用新字段
        return create_error_response(
            error_type=event.get('error_type', 'agent'),
            error_message=event.get('error_message', '未知错误'),  # 改为error_message
            model=model,
            provider=provider,
            recoverable=event.get('recoverable', event.get('retryable', False)),
            step=step
        )
    elif event_type == 'chunk':
        # 【问题1修复】chunk类型：流式文本片段，支持统一ReAct流程
        return format_chunk_sse(
            event=event,
            step=step,
            model=model,
            provider=provider
        )
    else:
        # 未知类型，返回空字符串
        return ""


# ============================================================
# SSE 格式化函数 - chunk 类型处理
# ============================================================

def format_chunk_sse(event: Dict[str, Any], step: int, model: str, provider: str) -> str:
    """
    格式化chunk类型的SSE事件
    
    Args:
        event: chunk事件 dict，包含content/thought/reasoning/timestamp/is_reasoning
        step: 步骤编号
        model: 模型名称
        provider: 提供商
    
    Returns:
        SSE格式的字符串
    
    Author: 小沈-2026-04-25（参考文档问题1修复）
    """
    chunk_data = {
        "type": "chunk",
        "step": step,
        "content": event.get("content", ""),
        "thought": event.get("thought", ""),
        "reasoning": event.get("reasoning", ""),
        "timestamp": event.get("timestamp", ""),
        "is_reasoning": event.get("is_reasoning", False),
        "_thinking": event.get("_thinking", "")
    }
    return f"data: {json.dumps(chunk_data, ensure_ascii=False)}\n\n"


# ============================================================
# 任务管理相关（服务层可被外部调用）
# ============================================================

# 任务管理字典（存储运行中的任务，用于中断）
running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}

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
# 通用Agent SSE执行器 - 【提取 2026-04-30 小沈】消除4处重复代码
# file/time/network/desktop分支逻辑完全一致，只差intent_type和日志标签
# ============================================================

async def _run_agent_sse_stream(
    intent_type: str,
    llm_client,
    task_id: str,
    ai_service,
    candidates: list,
    last_message: str,
    next_step,
    running_tasks: dict,
    running_tasks_lock,
    session_id: str,
    current_execution_steps: list,
    current_content: str,
    agent_llm_holder: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """
    通用Agent SSE执行器：创建Agent → 运行run_stream → 格式化SSE → yield
    
    AgentFactory未注册的intent_type会自动回退到FileReactAgent。
    
    Args:
        intent_type: 意图类型(file/time/network/desktop等)
        其余: 与generate_sse_stream中的同名变量含义一致
        
    Yields:
        SSE格式字符串
    """
    from app.services.agent.agent_factory import AgentFactory
    
    _LOG_TAG = f"[{intent_type.upper()}Op]"
    _ERROR_LABEL = f"{intent_type}操作执行失败"
    
    agent = None  # 【修复 2026-05-13 小沈】M8: 预初始化，防止AgentFactory.create()抛异常时finally块中agent未绑定
    agent = AgentFactory.create(
        intent_type=intent_type,
        llm_client=llm_client,
        task_id=task_id,
        api_base=ai_service.api_base,
        api_key=ai_service.api_key,
        model=ai_service.model,
        candidates=candidates
    )
    
    config = get_config()
    max_steps = config.get_max_steps(DEFAULT_MAX_STEPS)  # 使用统一方法
    
    try:
        async for event in agent.run_stream(
            task=last_message, context=None,
            max_steps=max_steps, task_id=task_id,
            running_tasks=running_tasks
        ):
            # 检查中断
            async with running_tasks_lock:
                is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                if is_cancelled:
                    logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: {is_cancelled}")
                    interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                    logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                    yield f"data: {json.dumps(interrupted_data)}\n\n"
                    current_execution_steps.append(interrupted_data)
                    await save_execution_steps_to_db(session_id, current_execution_steps, current_content or "")
                    break
            
            # SSE 格式化 - 使用event自带step编号，与Agent内部计数一致
            sse_data = _format_sse_event(event, next_step(), ai_service.model, ai_service.provider)
            if sse_data:
                if sse_data.startswith("data: "):
                    step_data = json.loads(sse_data[6:])
                    current_execution_steps.append(step_data)
                    if step_data.get('type') == 'final':
                        current_content = step_data.get('response', '')
                    elif step_data.get('type') == 'chunk':
                        current_content = step_data.get('content', current_content)
                    await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
                
                logger.info(f"{_LOG_TAG} SSE发送数据")
                yield sse_data
                await asyncio.sleep(0.05)
    
    except Exception as e:
        logger.error(f"{_LOG_TAG} 执行出错：task_id={task_id}, error={e}", exc_info=True)
        error_step_obj = StepFactory.create_error_step(
            step=next_step(),
            error_type=f'{intent_type}_operation_error',
            error_message=_ERROR_LABEL,
            recoverable=False,
            model=ai_service.model,
            provider=ai_service.provider
        )
        error_step_dict = error_step_obj.to_dict()
        error_response = format_sse_event('error', error_step_obj.step, error_step_dict)
        current_execution_steps.append(error_step_dict)
        await save_execution_steps_to_db(session_id, current_execution_steps, _ERROR_LABEL)
        yield error_response
    finally:
        # 【修复 2026-05-10 小沈】将 Agent 内真实 LLM 调用次数回传给外层日志（generate_sse_stream 中 llm_call_count 从未递增）
        if agent_llm_holder is not None and agent is not None:
            agent_llm_holder["n"] = getattr(agent, "llm_call_count", 0)


# ============================================================
# 通用SSE流式处理（intent_type未注册AgentFactory时的兜底）
# 使用TextStrategy纯文本对话，不涉及工具调用
# 小沈 - 2026-05-13
# ============================================================

async def _run_generic_sse_stream(
    llm_client,
    task_id: str,
    ai_service,
    last_message: str,
    next_step,
    running_tasks: dict,
    running_tasks_lock,
    session_id: str,
    current_execution_steps: list,
) -> AsyncGenerator[str, None]:
    """
    通用SSE流式处理：用于未注册AgentFactory的intent_type
    - 使用TextStrategy纯文本对话
    - 复用base_react.run_stream()（通过简单BaseAgent子类）
    - 不涉及工具调用
    """
    from app.services.agent.base_react import BaseAgent
    from app.services.agent.llm_strategies import TextStrategy
    from app.services.agent.reasoning_steps import StepFactory
    
    _LOG_TAG = "[GenericOp]"
    _ERROR_LABEL = "操作执行失败"
    
    # 【L13修复 2026-05-13 小沈】从config读取max_steps
    _generic_max_steps = get_config().get('app.max_steps', DEFAULT_MAX_STEPS)
    
    # 创建一个简单的Agent：复用BaseAgent.run_stream()，ToolCategory=None
    # 注意：不用ReactAgentMixin（不涉及工具，直接调TextStrategy）
    class _GenericAgent(BaseAgent):
        def __init__(self, llm_client, task_id, strategy, **kwargs):
            super().__init__(llm_client=llm_client, task_id=task_id, tool_category=None, **kwargs)
            self._strategy = strategy
        
        async def _get_llm_response(self) -> str:
            self.llm_call_count += 1
            if self._strategy:
                last_msg = self.conversation_history[-1]["content"] if self.conversation_history else ""
                history = self.conversation_history[:-1] if len(self.conversation_history) > 1 else []
                return await self._strategy.call(
                    llm_client=self.llm_client,
                    message=last_msg,
                    history_dicts=history,
                    conversation_history=self.conversation_history
                )
            return ""
        
        async def _execute_tool(self, action, params):
            return {}
        
        def _get_system_prompt(self):
            return "你是一个有用的AI助手，直接回答用户的问题。"
        
        def _get_task_prompt(self, task, context=None):
            return task
    
    strategy = TextStrategy() if ai_service else None
    agent = _GenericAgent(
        llm_client=llm_client,
        task_id=task_id,
        strategy=strategy,
    )
    
    try:
        async for event in agent.run_stream(
            task=last_message, context=None,
            max_steps=_generic_max_steps, task_id=task_id,
            running_tasks=running_tasks
        ):
            # 中断检查
            async with running_tasks_lock:
                is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                if is_cancelled:
                    from app.chat_stream.error_handler import create_incident_data
                    logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: {is_cancelled}")
                    interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                    yield f"data: {json.dumps(interrupted_data)}\n\n"
                    current_execution_steps.append(interrupted_data)
                    await save_execution_steps_to_db(session_id, current_execution_steps, "")
                    break
            
            sse_data = _format_sse_event(event, next_step(), ai_service.model, ai_service.provider)
            if sse_data:
                if sse_data.startswith("data: "):
                    step_data = json.loads(sse_data[6:])
                    current_execution_steps.append(step_data)
                    await save_execution_steps_to_db(session_id, current_execution_steps, step_data.get('response', step_data.get('content', '')))
                yield sse_data
                await asyncio.sleep(0.05)
    
    except Exception as e:
        logger.error(f"{_LOG_TAG} 执行出错：task_id={task_id}, error={e}", exc_info=True)
        error_step_obj = StepFactory.create_error_step(
            step=next_step(),
            error_type='generic_operation_error',
            error_message=_ERROR_LABEL,
            recoverable=False,
            model=ai_service.model,
            provider=ai_service.provider
        )
        error_step_dict = error_step_obj.to_dict()
        error_response = format_sse_event('error', error_step_obj.step, error_step_dict)
        current_execution_steps.append(error_step_dict)
        await save_execution_steps_to_db(session_id, current_execution_steps, _ERROR_LABEL)
        yield error_response


# ============================================================
# SSE 流式生成器函数（供 chat_router.py 调用）
# ============================================================

async def generate_sse_stream(
    messages: List[Dict[str, str]],
    intent_type: str = "generic",
    confidence: float = 0.0,
    candidates: Optional[List[str]] = None,  # 【新增 2026-04-30 小沈】候选意图列表
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ai_service: Optional[Any] = None,
    next_step: Optional[Callable[[], int]] = None,
    running_tasks: Optional[Dict[str, Any]] = None,
    running_tasks_lock: Optional[asyncio.Lock] = None,
    current_execution_steps: Optional[List[Dict]] = None
) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成器 - 实时展示ReAct执行步骤
    
    供 chat_router.py 调用，返回 AsyncGenerator 用于 SSE 流式输出。
    
    【阶段6修改】添加 intent_type 和 confidence 参数实现分发逻辑。
    【2026-04-30 小沈】新增 candidates 参数，传递候选意图列表。
    注意：start 步骤由 chat_router 发送，本层只处理分发后的逻辑。
    
    Args:
        messages: 消息列表
        intent_type: 意图类型
        confidence: 意图置信度
        candidates: 候选意图列表
        provider: AI 服务提供商
        model: AI 模型
        temperature: 创造性参数
        task_id: 任务ID
        session_id: 会话ID
        ai_service: AI服务实例
        next_step: 步骤计数器函数
        running_tasks: 任务字典
        running_tasks_lock: 任务锁
        current_execution_steps: 执行步骤列表
    
    Yields:
        SSE 格式的数据字符串
    """
    # 如果没传入 candidates，设置默认值
    if candidates is None:
        candidates = []
    
    # 如果没传入，使用默认值
    if running_tasks is None:
        running_tasks = {}
    if running_tasks_lock is None:
        running_tasks_lock = asyncio.Lock()
    if current_execution_steps is None:
        current_execution_steps = []
    if next_step is None:
        next_step = create_step_counter()
    
    # 生成 task_id
    if not task_id:
        task_id = str(uuid.uuid4())
    
    # ===== Prompt Logger 记录 =====
    # 获取用户消息
    user_message = ""
    for msg in messages:
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
    
    # 从 sessions.py 获取 AI 消息 ID（user_message_id + 1）
    from app.api.v1.sessions import _assistant_message_ids, _user_message_ids
    ai_message_id = _assistant_message_ids.get(session_id)
    if not ai_message_id and session_id in _user_message_ids:
        ai_message_id = _user_message_ids[session_id] + 1
    
    # 启动 prompt logger（只记录非 chat 意图）
    from app.utils.prompt_logger import get_prompt_logger
    prompt_logger = get_prompt_logger()
    if intent_type not in ("", "generic") and ai_message_id:
        prompt_logger.start_request(
            user_message=user_message,
            user_message_id=str(ai_message_id),
            session_id=session_id or task_id
        )
        # 记录系统 prompt（根据 intent_type 动态选择对应的 prompt 类）
        # 【修复 2026-05-07 小沈】完善intent_type→Prompt类映射，处理chat意图
        if intent_type in ("", "generic", "chat"):
            prompts_instance = None
            source_name = "通用意图：无系统Prompt"
        elif intent_type == "time":
            from app.services.prompts.time import TimePrompts
            prompts_instance = TimePrompts()
            source_name = "time_prompts.py"
        elif intent_type == "shell":
            from app.services.prompts.shell import ShellPrompts
            prompts_instance = ShellPrompts()
            source_name = "shell_prompts.py"
        elif intent_type == "network":
            from app.services.prompts.network import NetworkPrompts
            prompts_instance = NetworkPrompts()
            source_name = "network_prompts.py"
        elif intent_type == "desktop":
            from app.services.prompts.desktop import DesktopPrompts
            prompts_instance = DesktopPrompts()
            source_name = "desktop_prompts.py"
        else:
            from app.services.prompts.file import FileOperationPrompts
            prompts_instance = FileOperationPrompts()
            source_name = "file_prompts.py"
        
        if prompts_instance and intent_type not in ("", "generic"):
            full_prompt = prompts_instance.build_full_system_prompt()
            prompt_logger.log_system_prompt(
                step_name="系统Prompt生成",
                prompt_content=full_prompt,
                source=source_name,
                details={"intent_type": intent_type, "confidence": confidence, "note": "含OUTPUT_FORMAT(含退出规则)+TOOL_CALL_RULES+SAFETY+ROLLBACK"}
            )
        # 记录任务 prompt
        prompt_logger.log_task_prompt(
            task_content=user_message,
            context={"intent_type": intent_type, "confidence": confidence}
        )
    
    # 每次对话开始，重置LLM调用计数器（file/time 等路径由 Agent.llm_call_count 回填 — 小沈-2026-05-10）
    llm_call_count = 0
    agent_llm_holder: Dict[str, Any] = {"n": 0}
    
    # 【重要】严格规则：ai_service 必须由 chat_router 传入，禁止在此处创建
    if ai_service is None:
        raise ValueError("[AIServiceFactory] react_sse_wrapper 禁止创建 ai_service，必须由 chat_router 传入")
    logger.info(f"[AIServiceFactory] 使用 router 传入的 ai_service（复用）")
    
    # 注册任务（包含ai_service引用+asyncio.Task引用，用于强制中断）
    async with running_tasks_lock:
        running_tasks[task_id] = {
            "status": "running", 
            "cancelled": False,
            "paused": False,
            "created_at": datetime.now(),
            "ai_service": ai_service,
            "_task": asyncio.current_task()  # 存储asyncio.Task引用，用于task.cancel()真正中断
        }
    
    logger.info(f"[LLM Total Counter] ====== New conversation started, counter reset to 0 ======")
    
    # 注意：不重复创建 next_step 和 current_execution_steps
    # 因为 router 已经创建并传入，如果没传入才使用默认值（在函数开头已处理）
    current_content: str = ""
    
    # 获取 display_name
    display_name = f"{ai_service.provider} ({ai_service.model})"
    
    # 缓存 display_name
    if session_id:
        cache_display_name(session_id, display_name)
    
    # 安全检查（注意：chat_router.py 已经做过安全检测，这里是冗余检查，保留以防直接调用）
    last_message = messages[-1]["content"] if messages else ""
    security_check_result = check_command_safety(last_message)
    
    # 注意：start 步骤已在 chat_router.py 中发送，这里不再重复发送
    # 避免导致 start 步骤重复 (step=1 和 step=2 都是 start)
    
    # 安全检查未通过，返回错误
    if not security_check_result.get('is_safe', True):
        risk = security_check_result.get('risk', '未知风险')
        risk_level = security_check_result.get('risk_level', 'unknown')
        blocked = security_check_result.get('blocked', False)
        is_need_confirm = security_check_result.get('is_need_confirm', False)
        
        logger.info(f"[Step error] 发送error步骤(安全检测拦截), level={risk_level}, blocked={blocked}")
        
        # 获取详细的CRSS评分信息
        from app.services.command_security import calculate_risk_score_v2
        risk_detail = calculate_risk_score_v2(last_message)
        
        # 构建专业的CRSS评分报告
        risk_level_text = {
            "safe": "安全",
            "low": "低风险",
            "medium": "中等风险",
            "high": "高风险",
            "critical": "极高风险"
        }.get(risk_level, "未知")
        
        action_text = "已拦截" if blocked else ("需确认" if is_need_confirm else "警告")
        
        # 构建专业的安全评估报告
        security_context = {
            "crss_report": {
                "risk_score": risk_detail.get('score', 0),
                "risk_level": risk_level,
                "risk_level_text": f"[{risk_level_text}]",
                "action_required": action_text,
                "is_safe": security_check_result.get('is_safe', True),
                "is_blocked": blocked,
                "need_confirmation": is_need_confirm,
            },
            "analysis": {
                "operation_type": risk_detail.get('details', {}).get('operation_type', 'UNKNOWN'),
                "operation_target": risk_detail.get('details', {}).get('target', 'UNKNOWN'),
                "impact_scope": risk_detail.get('details', {}).get('scope', 'UNKNOWN'),
            },
            "matched_rule": security_check_result.get('rule_matched'),
            "original_command": last_message,
            "suggestions": risk_detail.get('suggestions', []),
        }
        
        error_step_obj = StepFactory.create_error_step(
            step=next_step(),
            error_type="security",
            error_message=f"危险操作需确认: {risk}",
            recoverable=False,
            model=ai_service.model,
            provider=ai_service.provider,
            context=security_context
        )
        error_step_dict = error_step_obj.to_dict()
        error_response = format_sse_event('error', error_step_obj.step, error_step_dict)
        current_execution_steps.append(error_step_dict)
        await save_execution_steps_to_db(session_id, current_execution_steps, f"错误: {risk}")
        yield error_response
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
            # 保存 interrupted 步骤到数据库
            if interrupt_msg.startswith("data: "):
                step_data = json.loads(interrupt_msg[6:])
                current_execution_steps.append(step_data)
                await save_execution_steps_to_db(session_id, current_execution_steps, current_content or "")
            return
        
        # 暂停检查
        async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
            yield pause_event
            # 保存 paused 步骤到数据库
            if pause_event.startswith("data: "):
                step_data = json.loads(pause_event[6:])
                current_execution_steps.append(step_data)
                await save_execution_steps_to_db(session_id, current_execution_steps, current_content or "")
        
        # 【阶段6】根据 intent_type 分发到不同 Agent
        session_id = session_id or str(uuid.uuid4())
        
        llm_client = LLMClientWrapper(ai_service)
        
        # 分发逻辑
        # 【2026-05-13 小沈】改为try AgentFactory + 兜底通用Agent（不再限4个意图，不报"not_implemented"）
        try:
            from app.services.agent.agent_factory import AgentFactory
            async for sse_chunk in _run_agent_sse_stream(
                intent_type=intent_type,
                llm_client=llm_client,
                task_id=task_id,
                ai_service=ai_service,
                candidates=candidates,
                last_message=last_message,
                next_step=next_step,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                session_id=session_id,
                current_execution_steps=current_execution_steps,
                current_content=current_content,
                agent_llm_holder=agent_llm_holder,
            ):
                yield sse_chunk
        except ValueError:
            # intent_type未注册AgentFactory → 用通用TextStrategy Agent兜底
            logger.info(f"[ChatOp] intent_type='{intent_type}' 无专用Agent，使用通用TextStrategy兜底")
            async for sse_chunk in _run_generic_sse_stream(
                llm_client=llm_client,
                task_id=task_id,
                ai_service=ai_service,
                last_message=last_message,
                next_step=next_step,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock,
                session_id=session_id,
                current_execution_steps=current_execution_steps,
            ):
                yield sse_chunk
    
    except asyncio.CancelledError:
        # 【问题3修复】客户端断开连接，任务被中断
        # 用try-catch包裹yield，防止客户端已断开导致失败
        async with running_tasks_lock:
            running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
        interrupted_step = create_incident_data(
            incident_value='interrupted',
            message='客户端断开连接，任务中断',
            step=next_step()
        )
        current_execution_steps.append(interrupted_step)
        await save_execution_steps_to_db(session_id, current_execution_steps, current_content)
        
        try:
            interrupted_data = create_incident_data('interrupted', '客户端断开连接，任务中断')
            logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开)")
            yield f"data: {json.dumps(interrupted_data)}\n\n"
        except Exception:
            # 客户端已断开，yield失败是正常的，记录日志但不中断
            logger.info(f"[Step interrupted] 客户端已断开，跳过yield")
    
    except Exception as e:
        logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
        
        # 【改造 2026-04-17 小沈】使用StepFactory统一Step封装
        error_step_value = next_step()
        error_step_obj = StepFactory.create_error_step(
            step=error_step_value,
            error_type="stream_error",
            error_message=str(e),
            recoverable=False,
            model=ai_service.model,
            provider=ai_service.provider
        )
        error_step_dict = error_step_obj.to_dict()
        error_response = format_sse_event('error', error_step_value, error_step_dict)
        
        logger.info(f"[Step error] 发送error步骤")
        current_execution_steps.append(error_step_dict)
        await save_execution_steps_to_db(session_id, current_execution_steps, f"错误: {error_step_dict['error_message']}")
        yield error_response
    
    finally:
        reported_llm = agent_llm_holder.get("n", 0) if agent_llm_holder.get("n", 0) > 0 else llm_call_count
        logger.info(
            f"[LLM Total Counter] ====== Conversation finished, total LLM calls: {reported_llm} ======"
        )
        
        # 清理任务：如果任务状态不是cancelled，则删除
        # cancelled状态的任务由cancel_task保留记录
        async with running_tasks_lock:
            if task_id in running_tasks:
                task_status = running_tasks[task_id].get("status")
                if task_status != "cancelled":
                    del running_tasks[task_id]
                    logger.info(f"[Cleanup] 任务 {task_id} 正常完成，已清理")
                else:
                    logger.info(f"[Cleanup] 任务 {task_id} 已被中断，保留记录")


# ============================================================
# 任务控制函数（供外部调用）
# ============================================================

async def cancel_task(task_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    中断指定的流式任务
    
    【方案4改进】增强中断响应机制：
    1. 立即设置cancelled状态
    2. 强制关闭LLM HTTP连接
    3. 返回详细的状态信息
    
    Args:
        task_id: 任务ID
        session_id: 会话ID（可选，用于阻止重连）
    
    Returns:
        {"success": bool, "message": str, "task_status": str}
    """
    # 记录中断时间戳
    interrupt_time = datetime.now()
    
    async with running_tasks_lock:
        logger.info(f"[TaskControl] 当前running_tasks数量: {len(running_tasks)}, keys: {list(running_tasks.keys())}")
        
        if task_id in running_tasks:
            task_info = running_tasks[task_id]
            task_info["cancelled"] = True
            task_info["status"] = "cancelled"
            task_info["interrupt_time"] = interrupt_time.isoformat()  # 【方案4】记录中断时间
            task_info["cancel_request_time"] = interrupt_time.timestamp()  # 【时间测量】记录取消请求时间
            
            # 【日志增强】记录任务详细信息和时间差
            now_ts = interrupt_time.timestamp()
            logger.info(f"[TaskControl] 中断任务 {task_id}，时间戳: {now_ts}")
            logger.info(f"[TaskControl] ai_service存在: {'ai_service' in task_info}")
            logger.info(f"[TaskControl] 任务步骤: {task_info.get('current_step', 'unknown')}")
            
            # 【2026-05-13 小沈】优先用asyncio.Task.cancel()真正中断运行中的生成器
            running_task = task_info.pop("_task", None)
            if running_task is not None and not running_task.done():
                running_task.cancel()
                logger.info(f"[Task Cancelled] 任务 {task_id} asyncio.Task.cancel() 已调用")
            
            # 【方案4】强制关闭HTTP连接（兜底）
            if "ai_service" in task_info and task_info["ai_service"]:
                ai_service = task_info["ai_service"]
                try:
                    ai_service.cancel()
                    logger.info(f"[Task Cancelled] 任务 {task_id} HTTP连接已强制关闭")
                except Exception as e:
                    logger.error(f"[Task Cancelled] 关闭HTTP连接失败: {e}")
            
            # 从 running_tasks 中移除任务（避免内存泄漏）
            # 修改：不立即删除，设置为cancelled状态保留记录
            # del running_tasks[task_id]  # 不要立即删除
            # 改为设置状态为已取消，但保留记录
            task_info["status"] = "cancelled"
            task_info["cancelled"] = True
            task_info["interrupt_time"] = interrupt_time.isoformat()
            logger.info(f"[Task Cancelled] 任务 {task_id} 已标记为cancelled，保留记录")
            
            # 返回更详细的状态信息
            return {
                "success": True, 
                "message": f"任务 {task_id} 已中断",
                "task_status": "cancelled",
                "interrupt_time": interrupt_time.isoformat()
            }
        else:
            logger.warning(f"[TaskControl] 任务 {task_id} 不在running_tasks中，可能已结束")
            return {"success": False, "message": f"任务 {task_id} 不存在", "task_status": "not_found"}
    
    return {"success": True, "message": f"任务 {task_id} 已中断", "task_status": "cancelled"}


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
            # 如果任务已被中断，不能暂停
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法暂停"}
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
            # 如果任务已被中断，不能恢复
            if running_tasks[task_id].get("cancelled", False):
                return {"success": False, "message": f"任务 {task_id} 已被中断，无法恢复"}
            # 如果任务没有暂停，不能恢复
            if not running_tasks[task_id].get("paused", False):
                return {"success": False, "message": f"任务 {task_id} 未暂停，无法恢复"}
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
        return {"success": False, "message": f"任务 {task_id} 不存在"}
