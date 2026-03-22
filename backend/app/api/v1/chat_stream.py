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
from typing import List, Dict, Optional, AsyncGenerator, Any, Callable
from app.services import AIServiceFactory
from app.services.base import Message  # ⭐ 【调试添加】用于日志记录
from app.services.tools.file.file_tools import get_file_tools
from app.services.agent.agent import IntentAgent
from app.services.shell_security import check_command_safety
from app.api.v1.intent_classifier import detect_file_operation_intent  # 【小沈引用原始函数 2026-03-17】
from app.api.v1.action1 import (
    build_action_notification,
    handle_action_event
)
from app.api.v1.observation1 import (
    build_observation_security,
    handle_observation_event
)
from app.api.v1.three_operation import (
    process_file_operation
)
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name  # ⭐ 【小沈添加 2026-03-03】
from app.utils.retry_controller import RetryController  # 【小沈-2026-03-14添加】统一的空闲超时和重试控制器
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError  # 【小沈-2026-03-14添加】通用的空闲超时异步迭代器
from app.chat_stream import (
    create_timestamp,
    get_provider_display_name,
    create_error_response,
    create_incident_data,
    create_final_response,
)  # 【小沈 2026-03-22】从统一模块导入
from pathlib import Path
import shutil

# ⭐ 【小沈添加 2026-03-16 v11.0】导入sessions模块，用于流式过程中实时保存execution_steps和content
# 目的：解决页面切换/刷新导致的数据丢失问题 - 后端自动保存作为核心保障
from app.api.v1 import sessions

# ============================================================
# 统一错误处理工具函数 - 已移至 app/chat_stream/error_handler.py
# ============================================================

# ============================================================
# Start1 函数 - 小沈添加【2026-03-19】
# 用于整理start阶段的逻辑，不带LLM调用
# 备用版本，可与 Start2（带LLM调用）相互替换调试
# ============================================================

async def start1(
    request,                 # ChatRequest
    ai_service,              # AIService
    task_id: str,            # 任务ID
    step_counter,             # 步骤计数器（引用）
    current_execution_steps,  # 执行步骤列表（引用）
    current_content,         # 当前内容（引用）
    save_func,               # 保存到数据库的函数
    add_step_func,           # 添加步骤到数据库的函数
    next_step                # next_step()函数（外部传入）
) -> AsyncGenerator[dict, None]:
    """
    处理start阶段（Start1版本，不带LLM调用）
    
    功能：
    1. 构建 display_name
    2. security_check
    3. 构建 start_data
    4. yield start_data（第一次）
    5. 保存数据库
    6. if not is_safe → yield error, return
    
    Args:
        request: ChatRequest 用户请求
        ai_service: AIService AI服务
        task_id: str 任务ID
        step_counter: 步骤计数器（引用）
        current_execution_steps: 执行步骤列表（引用）
        current_content: 当前内容（引用）
        save_func: 保存到数据库的函数 save_execution_steps_to_db
        add_step_func: 添加步骤到数据库的函数 add_step_and_save
        next_step: next_step()函数（外部传入）
    
    Yields:
        dict: start_data 或 error_data
    """
    # 1. 构建 display_name（AI显示名称）
    display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
    
    # 缓存 display_name
    if request.session_id:
        cache_display_name(request.session_id, display_name)
    
    # 2. 执行 security_check → 安全检查结果
    last_message = request.messages[-1].content if request.messages else ""
    security_check_result = check_command_safety(last_message)
    
    # 4. 构建 start_data 字典
    start_data = {
        'type': 'start',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'display_name': display_name,
        'provider': ai_service.provider,
        'model': ai_service.model,
        'task_id': task_id,
        'security_check': {
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    }
    
    logger.info(f"[Step start] 发送start步骤 - step={start_data['step']}, model={ai_service.model}, provider={ai_service.provider}, task_id={task_id[:8]}..., security_check.is_safe={security_check_result.get('is_safe', True)}")
    
    # 5. yield start_data（第一次）
    yield start_data
    
    # 6. 保存到数据库
    current_execution_steps.append(start_data)
    await save_func(current_execution_steps, current_content)
    
    # 7. if not is_safe → yield error, return
    if not security_check_result.get('is_safe', True):
        risk = security_check_result.get('risk', '未知风险')
        error_data = {
            'type': 'error',
            'step': next_step(),
            'code': 'SECURITY_BLOCKED',
            'message': f'危险操作需确认: {risk}',
            'error_type': 'security',
            'details': f"risk_level: {security_check_result.get('risk_level')}",
            'retryable': False,
            'timestamp': create_timestamp(),
            'model': request.model,
            'provider': request.provider
        }
        logger.info(f"[Step error] 发送error步骤(安全检测拦截) - step={error_data['step']}, code={error_data['code']}, message={error_data['message']}, retryable={error_data['retryable']}")
        yield error_data
        
        # 保存error步骤到数据库
        error_step = {
            'type': 'error',
            'step': error_data['step'],
            'code': error_data['code'],
            'message': error_data['message'],
            'error_type': error_data['error_type'],
            'timestamp': create_timestamp()
        }
        await add_step_func(error_step, f"错误: {error_data['message']}")
        return
    
    # 返回 is_safe 标志和 display_name，供主流程判断
    yield {'_start_complete': True, 'is_safe': True, 'display_name': display_name}


# ============================================================
# thought1 函数 - Start1版本的thought处理（过渡用）
# ============================================================

async def thought1(
    task_id: str,                      # 任务ID
    next_step,                          # next_step()函数
    current_execution_steps,             # 执行步骤列表（引用）
    current_content,                     # 当前内容（引用）
    save_execution_steps_to_db,          # 保存到数据库的函数
    running_tasks,                       # 运行任务（用于检查中断）
    running_tasks_lock                   # 运行任务锁
) -> AsyncGenerator[Any, None]:
    """
    处理 thought 步骤（Start1版本，不含LLM调用）
    
    功能：
    1. 构建 thought_data（只有thinking_prompt）
    2. yield thought_data（调用方包装成SSE）
    3. 保存数据库
    4. sleep(0.3)
    5. 检查中断（yield SSE字符串）
    6. 暂停检查（yield SSE字符串）
    
    Args:
        task_id: 任务ID
        next_step: next_step()函数
        current_execution_steps: 执行步骤列表
        current_content: 当前内容
        save_execution_steps_to_db: 保存到数据库的函数
        running_tasks: 运行任务
        running_tasks_lock: 运行任务锁
    
    Yields:
        dict: thought_data 或 str: SSE格式的中断/暂停事件
    """
    # 1. 构建 thought_data
    thought_data = {
        'type': 'thought',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'thinking_prompt': '正在分析任务...'
    }
    logger.info(f"[Step thought] 发送thought步骤 - step={thought_data['step']}, thinking_prompt={thought_data['thinking_prompt']}")
    
    # 2. 保存数据库
    current_execution_steps.append(thought_data)
    await save_execution_steps_to_db(current_execution_steps, current_content)
    
    await asyncio.sleep(0.3)
    
    # 3. 检查中断
    is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(
        task_id, running_tasks, running_tasks_lock, next_step
    )
    if is_interrupted:
        yield interrupt_msg
        return
    
    # 4. 暂停检查
    async for pause_event in check_and_yield_if_paused(
        task_id, running_tasks, running_tasks_lock, next_step
    ):
        yield pause_event
    
    # 5. 返回 thought_data 供后续处理
    yield thought_data


# ============================================================
# handle_thought_event - 处理 Agent 返回的 thought 事件
# 对应 thought1 版本（不含 LLM 调用）
# ============================================================
def handle_thought_event(raw_event: Dict, step_func: Any) -> Dict:
    """
    处理 Agent 返回的 thought 事件，构建 thought_data

    设计文档字段对照（thought类型）：
    - type: thought
    - step: next_step()
    - timestamp: create_timestamp()
    - content: event.content
    - reasoning: event.reasoning
    - action_tool: event.action_tool
    - params: event.params

    Args:
        raw_event: Agent 返回的原始 event 字典
        step_func: next_step() 函数

    Returns:
        thought_data 字典
    """
    thought_data = {
        'type': 'thought',
        'step': step_func(),
        'timestamp': create_timestamp(),
        'content': raw_event.get('content', ''),
        'reasoning': raw_event.get('reasoning', ''),
        'action_tool': raw_event.get('action_tool', ''),
        'params': raw_event.get('params', {})
    }
    logger.info(
        f"[Step thought] 发送thought步骤 - step={thought_data['step']}, "
        f"action_tool={thought_data['action_tool']}, "
        f"reasoning长度={len(thought_data['reasoning'] or '')}, "
        f"content长度={len(thought_data['content'] or '')}"
    )
    return thought_data


def get_user_friendly_error(error: Exception) -> Dict[str, Any]:
    """
    获取用户友好的错误信息
    
    Args:
        error: 异常对象
    
    Returns:
        错误信息字典，包含 code, message, error_type, retryable
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # 【小沈-2026-03-14修复】优先处理 IdleTimeoutError
    from app.utils.idle_timeout import IdleTimeoutError
    if isinstance(error, IdleTimeoutError):
        return {
            "code": "IDLE_TIMEOUT",
            "message": "请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试",
            "error_type": "timeout",
            "retryable": True,
            "retry_after": 5
        }
    
    # 根据错误类型返回用户友好的错误信息
    if error_type == "TimeoutError" or "timeout" in error_msg:
        return {
            "code": "TIMEOUT",
            "message": "请求超时，请重试",
            "error_type": "network",
            "retryable": True,
            "retry_after": 5
        }
    elif error_type == "ConnectionError" or "connection" in error_msg:
        return {
            "code": "CONNECTION_ERROR",
            "message": "网络连接失败，请检查网络",
            "error_type": "network",
            "retryable": True,
            "retry_after": 10
        }
    elif error_type == "HTTPError" or "http" in error_msg:
        return {
            "code": "HTTP_ERROR",
            "message": "服务器响应异常，请稍后重试",
            "error_type": "network",
            "retryable": True,
            "retry_after": 10
        }
    elif error_type == "ValueError":
        return {
            "code": "VALIDATION_ERROR",
            "message": "参数值错误，请检查输入",
            "error_type": "validation",
            "retryable": False
        }
    elif "not found" in error_msg or "不存在" in error_msg:
        return {
            "code": "NOT_FOUND",
            "message": "文件或资源不存在",
            "error_type": "file_system",
            "retryable": False
        }
    elif "permission" in error_msg or "权限" in error_msg:
        return {
            "code": "PERMISSION_DENIED",
            "message": "权限不足，无法执行操作",
            "error_type": "security",
            "retryable": False
        }
    else:
        # 其他错误返回通用信息，不泄露技术细节
        return {
            "code": "UNKNOWN_ERROR",
            "message": "AI 处理异常，请稍后重试",
            "error_type": "unknown",
            "retryable": True,
            "retry_after": 5
        }


# ============================================================
# 统一中断检查工具函数 - 小沈代修改【修复问题 5】
# ============================================================

async def check_and_yield_if_interrupted(
    task_id: str, 
    running_tasks: dict, 
    running_tasks_lock: asyncio.Lock,
    next_step: Optional[Callable[[], int]] = None
) -> tuple[bool, str]:
    """
    检查任务是否被中断，如果是则返回中断消息
    
    Args:
        task_id: 任务 ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
        next_step: 步骤计数器函数（可选）
    
    Returns:
        (is_interrupted, interrupt_message) 元组
        - is_interrupted: 是否被中断
        - interrupt_message: 中断消息（如果未被中断则为空字符串）
    """
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            # 【使用统一函数】创建incident数据
            step_value = next_step() if next_step else None
            incident_data = create_incident_data('interrupted', '任务已被中断', step=step_value)
            return True, f"data: {json.dumps(incident_data)}\n\n"
    return False, ""


async def check_and_yield_if_paused(
    task_id: str, 
    running_tasks: dict, 
    running_tasks_lock: asyncio.Lock,
    next_step: Optional[Callable[[], int]] = None
) -> AsyncGenerator[str, None]:
    """
    检查任务是否被暂停，如果是则发送paused事件并等待恢复
    
    Args:
        task_id: 任务ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
        next_step: 步骤计数器函数（可选）
    
    Yields:
        SSE 格式的事件字符串 (paused/resumed)
    """
    while True:
        async with running_tasks_lock:
            is_paused = running_tasks.get(task_id, {}).get("paused", False)
            is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
            
            if is_cancelled:
                return  # 暂停期间被取消了
            
            if not is_paused:
                # 不再暂停，恢复发送
                if running_tasks.get(task_id, {}).get("_was_paused", False):
                    # 【使用统一函数】创建incident数据
                    step_value = next_step() if next_step else None
                    resumed_data = create_incident_data('resumed', '任务已恢复', step=step_value)
                    yield f"data: {json.dumps(resumed_data)}\n\n"
                    running_tasks[task_id]["_was_paused"] = False
                return
        
        # 暂停中，等待恢复
        if is_paused and not running_tasks.get(task_id, {}).get("_was_paused", False):
            # 刚进入暂停状态，发送paused事件
            async with running_tasks_lock:
                running_tasks[task_id]["_was_paused"] = True
            # 【使用统一函数】创建incident数据
            step_value = next_step() if next_step else None
            paused_data = create_incident_data('paused', '任务已暂停', step=step_value)
            yield f"data: {json.dumps(paused_data)}\n\n"
        
        await asyncio.sleep(0.5)  # 每0.5秒检查一次


# ============================================================
# observation 清洗函数 - 小沈添加【将复杂的observation简化为可读文本】
# ============================================================

def simplify_observation(observation: Any) -> str:
    """
    将 observation 简化为可读的文本
    
    处理各种情况：
    - 正常完成：提取 result 内容
    - list_directory：显示文件数量
    - 执行失败：返回错误信息
    - 空数据：返回默认文本
    
    Args:
        observation: Agent 返回的观察结果
        
    Returns:
        可读的文本字符串
    """
    if not observation:
        return "（无结果）"
    
    # 检查是否成功
    if not observation.get("success", True):
        error = observation.get("error", "未知错误")
        return f"❌ {error}"
    
    # 提取 result
    result = observation.get("result")
    if not result:
        return "（无结果）"
    
    # 根据 result 类型处理
    if isinstance(result, dict):
        # 文件列表
        if "entries" in result:
            count = result.get("total_count", len(result.get("entries", [])))
            return f"📁 列出了 {count} 个文件/目录"
        
        # finish 的结果
        if "result" in result:
            inner = result["result"]
            if isinstance(inner, str):
                return inner[:200]
        
        # 其他字典，转为简洁文本
        keys = list(result.keys())[:3]
        return f"{{ {', '.join(keys)} }}"
    
    elif isinstance(result, str):
        return result[:200]
    
    else:
        return str(result)[:200]


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


def extract_file_path(message: str) -> Optional[str]:
    """
    从消息中提取文件路径
    
    简单的路径提取逻辑，支持常见格式
    """
    import re
    
    # 尝试匹配常见的路径格式
    # Windows 路径: C:\path\to\file or D:/path/to/file
    # Unix 路径: /path/to/file or ./file or ../file
    path_patterns = [
        r'["\']([a-zA-Z]:[/\\][^"\']+)["\']',  # "C:\path" or "C:/path"
        r'["\']([/\\][^"\']+)["\']',  # "/path" or "\path"
        r'["\'](\.[/\\][^"\']+)["\']',  # "./path"
        r'(?:文件|file)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',  # 文件=path 或 file=path
        r'(?:路径|path)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',  # 路径=path 或 path=path
    ]
    
    for pattern in path_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # 如果没有匹配到，尝试提取消息中看起来像路径的部分
    # 简单的启发式：包含 / 或 \ 的单词
    words = message.split()
    for word in words:
        word = word.strip('"\'，,.;:')
        if ('/' in word or '\\' in word) and len(word) > 2:
            return word
    
    return None

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
        """
        生成SSE流，支持中断和暂停
        
        @author 小沈
        @update 2026-03-16 v11.0修改：添加实时保存功能，解决页面切换/刷新导致的数据丢失问题
        
        核心思路：
        1. 维护execution_steps列表，每次yield后保存到数据库
        2. 维护content内容，在is_reasoning变化时保存
        3. final步骤保存完整的execution_steps + content
        """
        # 【新增】每次对话开始，重置LLM调用计数器
        llm_call_count = 0
        
        # ⭐ 【小沈添加 2026-03-16 v11.0】跟踪execution_steps和content，用于实时保存
        # 目的：解决页面切换/刷新导致的数据丢失问题 - 后端自动保存作为核心保障
        current_execution_steps = []  # 累积execution_steps列表
        current_content = ""  # 累积AI生成的文本内容
        last_is_reasoning = None  # 上一个is_reasoning状态，用于检测变化
        
        # ⭐ 【小沈添加 2026-03-16 v11.0】保存辅助函数 - 在每个yield后调用
        async def save_execution_steps_to_db(execution_steps: list, content: Optional[str] = None):
            """
            保存execution_steps和content到数据库
            
            @author 小沈
            @update 2026-03-16 v11.0添加
            
            功能：
            - 实时保存execution_steps到数据库，作为数据持久化的核心保障
            - 支持同时保存content字段
            
            参数：
            - execution_steps: 执行步骤列表
            - content: AI生成的文本内容（可选）
            """
            # 只有当提供了session_id时才保存
            if request.session_id is None:
                logger.debug("[Save] 无session_id，跳过保存")
                return
            
            try:
                # 前端会传reply_to_message_id，但后端不使用，只用内存变量assistant_message_ids
                user_message_id = sessions._user_message_ids.get(request.session_id)
                
                # 调用sessions模块的save_execution_steps函数
                # 注意：这是一个异步函数调用
                result = await sessions.save_execution_steps(
                    request.session_id,
                    sessions.ExecutionStepsUpdate(
                        execution_steps=execution_steps,
                        content=content,
                        reply_to_message_id=user_message_id
                    )
                )
                logger.debug(f"[Save] 保存成功: session_id={request.session_id}, "
                           f"user_msg_id={user_message_id}, steps_count={len(execution_steps)}, has_content={content is not None}")
            except Exception as e:
                # ⭐ 【小沈修复 2026-03-16】保存失败记录详细错误，便于排查问题
                logger.error(f"[Save] 保存失败: {e}", exc_info=True)
                # 注意：不抛出异常，避免中断流式响应
        
        # ⭐ 【小沈重构 2026-03-16】统一的添加step并保存函数
        # 解决之前在每个错误处重复添加保存代码的问题
        async def add_step_and_save(step: dict, content: Optional[str] = None):
            """
            统一的添加step到execution_steps并保存到数据库的函数
            
            所有需要保存step的地方都调用此函数，避免代码重复
            
            参数：
            - step: step字典（包含type等字段）
            - content: 可选的content内容，用于覆盖current_content
            """
            current_execution_steps.append(step)
            # 【小健修复 2026-03-16】修复空字符串判断逻辑：使用bool判断，空字符串也使用current_content
            save_content = content if content else current_content
            await save_execution_steps_to_db(current_execution_steps, save_content)
        
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
        
        # 步骤计数器（用于统一生成step序号）- 定义在generate作用域内，供Start1和后续阶段共用
        step_counter = 0
        def next_step():
            nonlocal step_counter
            step_counter += 1
            return step_counter
        
        # 初始化 display_name（供后续阶段使用）
        display_name = ""
        
        # ⭐ 【start1调用】调用 start1 处理start阶段
        async for start_result in start1(
            request, ai_service, task_id,
            step_counter, current_execution_steps, current_content,
            save_execution_steps_to_db, add_step_and_save, next_step
        ):
            # 检查是否是控制消息
            if isinstance(start_result, dict) and start_result.get('_start_complete'):
                # Start阶段完成，安全检查通过，继续后续逻辑
                is_safe = start_result.get('is_safe', True)
                display_name = start_result.get('display_name', '')
                if is_safe:
                    logger.info(f"[Start1] start阶段完成，is_safe={is_safe}，display_name={display_name}，继续执行")
                continue
            
            # yield start_data 或 error_data
            yield f"data: {json.dumps(start_result)}\n\n"
            
            # 如果是error，直接return
            if isinstance(start_result, dict) and start_result.get('type') == 'error':
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
            
            # 1. 发送思考（使用thought1函数）
            async for thought_result in thought1(
                task_id=task_id,
                next_step=next_step,
                current_execution_steps=current_execution_steps,
                current_content=current_content,
                save_execution_steps_to_db=save_execution_steps_to_db,
                running_tasks=running_tasks,
                running_tasks_lock=running_tasks_lock
            ):
                if isinstance(thought_result, str):
                    # SSE格式的中断/暂停事件
                    yield thought_result
                    return
                else:
                    # thought_data 字典
                    yield f"data: {json.dumps(thought_result)}\n\n"
            
            # 检测文件操作意图
            is_file_op, _, confidence = detect_file_operation_intent(last_message)
            
            if is_file_op and confidence >= 0.3:
                # 【Phase5重构】使用 process_file_operation 处理文件操作
                async for event_data in process_file_operation(
                    last_message=last_message,
                    ai_service=ai_service,
                    task_id=task_id,
                    current_execution_steps=current_execution_steps,
                    current_content=current_content,
                    running_tasks=running_tasks,
                    running_tasks_lock=running_tasks_lock,
                    next_step=next_step,
                    add_step_and_save=add_step_and_save
                ):
                    event_keys = set(event_data.keys())

                    # 处理 action_tool 事件
                    if '_action' in event_keys:
                        action_data = event_data['_action']
                        yield f"data: {json.dumps(action_data)}\n\n"
                        continue

                    # 处理 observation 事件
                    if '_observation' in event_keys:
                        observation_data = event_data['_observation']
                        yield f"data: {json.dumps(observation_data)}\n\n"
                        continue

                    # 处理错误事件
                    if '_error' in event_keys:
                        yield event_data['_error']
                        continue

                    # 处理中断事件
                    if '_incident' in event_keys:
                        yield f"data: {json.dumps(event_data['_incident'])}\n\n"
                        continue

                    # 处理原始事件（thought/final/error）
                    if '_raw_event' in event_keys:
                        raw_event = event_data['_raw_event']
                        event_type = raw_event.get('type')

                        if event_type == 'thought':
                            thought_data = handle_thought_event(raw_event, next_step)
                            yield f"data: {json.dumps(thought_data)}\n\n"
                            current_execution_steps.append(thought_data)
                            await save_execution_steps_to_db(current_execution_steps, current_content)

                        elif event_type == 'final':
                            final_data = {
                                'type': 'final',
                                'step': next_step(),
                                'timestamp': create_timestamp(),
                                'content': raw_event.get('content', '')
                            }
                            logger.info(
                                f"[Step final] 发送final步骤 - step={final_data['step']}, "
                                f"content长度={len(final_data['content'])}"
                            )
                            yield f"data: {json.dumps(final_data)}\n\n"
                            current_execution_steps.append(final_data)
                            current_content = final_data.get('content', '')
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                            break

                        elif event_type == 'error':
                            error_data = {
                                'type': 'error',
                                'step': next_step(),
                                'code': 'AGENT_ERROR',
                                'message': raw_event.get('message', '未知错误'),
                                'error_type': 'agent',
                                'retryable': raw_event.get('retryable', False),
                                'timestamp': create_timestamp(),
                                'model': request.model,
                                'provider': request.provider
                            }
                            logger.info(
                                f"[Step error] 发送error步骤 - step={error_data['step']}, "
                                f"code={error_data['code']}, "
                                f"message={error_data['message']}, "
                                f"retryable={error_data['retryable']}"
                            )
                            yield f"data: {json.dumps(error_data)}\n\n"
                            error_step = {
                                'type': 'error',
                                'step': error_data['step'],
                                'error_type': 'agent',
                                'message': raw_event.get('message', '未知错误'),
                                'code': 'AGENT_ERROR',
                                'timestamp': create_timestamp()
                            }
                            await add_step_and_save(error_step, f"Agent错误: {raw_event.get('message', '未知错误')}")
                            break
                        continue

                    # 文件操作完成信号
                    if '_file_operation_complete' in event_keys:
                        continue
            else:
                # 普通对话：调用AI服务（流式）
                # 【优化1版修复】不发送action_tool，直接发送chunk
                # 符合5-9章设计：普通对话只有chunk → final
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        # 【使用统一函数】创建incident数据
                        interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                        logger.info(f"[Step incident] 发送incident步骤 - incident_type=interrupted, message=任务已被中断")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        return
                
                from app.services.base import Message
                history = []
                if len(request.messages) > 1:
                    for msg in request.messages[:-1]:
                        history.append(Message(role=msg.role, content=msg.content))
                
                # 【小沈-2026-03-14修复】统一的空闲超时和重试机制
                # 空闲超时由 IdleTimeoutIterator 实时检测，重试次数由 RetryController 管理
                max_retries = 3  # 最大重试次数：3次（总共4次调用）
                retry_controller = RetryController(max_retries=max_retries)
                ai_call_successful = False
                last_error = None
                last_error_type = None
                
                full_content = ""
                chunk_count = 0
                # ⭐ 【小沈修复 2026-03-17】添加保护机制：防止AI一直输出reasoning导致流式不结束
                max_chunk_count = 5000  # 最大chunk数量
                empty_content_count = 0  # 连续空content次数
                max_empty_content_count = 100  # 最大连续空content次数
                
                for retry_attempt in range(max_retries + 1):
                    if retry_attempt > 0:
                        # 发送重试提示给前端
                        # 【使用统一函数】创建incident数据
                        retry_data = create_incident_data('retrying', f'请求超时，正在重试 ({retry_attempt}/{max_retries})...', step=next_step())
                        yield f"data: {json.dumps(retry_data)}\n\n"
                        logger.info(f"[Retry] 开始第{retry_attempt + 1}次AI调用（共{max_retries + 1}次）")
                    
                    # 使用流式API，逐token返回
                    full_content = ""
                    chunk_count = 0
                    has_received_content = False  # 本次调用是否收到内容
                    chunk = None  # 初始化
                    idle_timeout_stream = None  # 初始化，用于异常处理中获取空闲时间
                    
                    try:
                        llm_call_count += 1
                        logger.info(f"[LLM Total Counter] >>> Stream AI called, count: {llm_call_count}")
                        
                        # 【小沈修复】使用 IdleTimeoutIterator 包装流式迭代器，实现实时空闲超时检测
                        # 【修改】超时时间从120秒调整为60秒（每次），3次重试合计3分钟
                        idle_timeout_stream = IdleTimeoutIterator(
                            ai_service.chat_stream(message=last_message, history=history),
                            timeout_seconds=60.0,
                            name=f"AI-Stream-{retry_attempt + 1}"
                        )
                        
                        async for chunk in idle_timeout_stream:
                            # 注意：IdleTimeoutIterator 自动检测空闲超时，收到内容时自动重置计时器
                            # 如果30秒内没有下一个 chunk，会抛出 IdleTimeoutError
                            
                            chunk_count += 1
                            
                            # ⭐ 【小沈修复 2026-03-17】保护机制：防止AI一直输出reasoning导致流式不结束
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
                            # 【原则4整改】content → message
                            async with running_tasks_lock:
                                if running_tasks.get(task_id, {}).get("cancelled", False):
                                    # 【使用统一函数】创建incident数据
                                    interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                                    logger.info(f"[Step incident] 发送incident步骤 - incident_type=interrupted, message=任务已被中断")
                                    yield f"data: {json.dumps(interrupted_data)}\n\n"
                                    return
                            
                            # ⭐ 暂停检查：AI流式响应过程中也检查暂停状态
                            async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock, next_step):
                                yield pause_event
                            
                            # ⭐ 检查chunk是否有错误（非空闲超时错误）
                            if chunk.stream_error:
                                last_error = chunk.stream_error
                                last_error_type = getattr(chunk, 'stream_error_type', 'unknown')
                                logger.warning(f"[AI Call] 流式请求返回错误: {chunk.stream_error}, error_type: {last_error_type}")
                                # 非空闲超时错误，直接报错不重试
                                logger.error(f"[AI Call] 检测到错误，不重试: {chunk.stream_error}")
                                ai_call_successful = False
                                break
                            
                            # ⭐ 【小沈修复 2026-03-16】无论content是否为空，都处理chunk并添加到列表
                            # 避免某些chunk被跳过导致steps不完整
                            current_is_reasoning = getattr(chunk, 'is_reasoning', False)
                            
                            # 无论content是否为空，都创建chunk_data并添加到列表
                            chunk_data = {
                                'type': 'chunk',
                                'step': next_step(),  # 添加step字段
                                'timestamp': create_timestamp(),
                                'content': chunk.content or '',  # 确保content不为None
                                'is_reasoning': current_is_reasoning
                            }
                            current_execution_steps.append(chunk_data)
                            
                            if chunk.content:
                                has_received_content = True
                                full_content += chunk.content
                                current_content = full_content  # 累积content
                                
                                # ⭐ 【小沈修复 2026-03-16】is_reasoning变化时保存，确保回答部分完整
                                if last_is_reasoning != current_is_reasoning:
                                    logger.info(f"[Save] is_reasoning变化: {last_is_reasoning} -> {current_is_reasoning}，准备保存 {len(current_execution_steps)} steps")
                                    try:
                                        await save_execution_steps_to_db(current_execution_steps, current_content)
                                        logger.info(f"[Save] is_reasoning变化保存成功: {len(current_execution_steps)} steps")
                                    except Exception as e:
                                        logger.error(f"[Save] is_reasoning变化保存失败: {e}", exc_info=True)
                                    last_is_reasoning = current_is_reasoning
                            
                            # ⭐ 发送chunk给前端
                            logger.info(f"[Step chunk] 发送chunk步骤#{chunk_count}: content长度={len(chunk.content or '')}, is_reasoning={chunk_data['is_reasoning']}")
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                            if chunk.is_done:
                                break
                    
                    except IdleTimeoutError as e:
                        # ⭐ 【关键】空闲超时异常 - 30秒无内容（由 IdleTimeoutIterator 实时检测）
                        last_error = str(e)
                        last_error_type = 'idle_timeout'
                        elapsed = idle_timeout_stream.get_elapsed_time() if idle_timeout_stream else 30.0
                        logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时：{elapsed:.1f}秒无内容")
                        # 空闲超时进入后面的重试判断逻辑
                    
                    except Exception as e:
                        last_error = str(e)
                        last_error_type = 'network_error'
                        logger.error(f"[AI Call] 第{retry_attempt + 1}次调用异常: {e}")
                        # 其他异常进入后面的错误判断逻辑
                    
                    # ⭐ 【小沈-2026-03-14重构】统一的重试判断逻辑
                    # 判断优先级：1.收到内容成功 → 2.空闲超时重试 → 3.网络错误重试 → 4.其他错误失败
                    
                    if has_received_content:
                        # ✅ 已经收到过内容，说明模型在工作
                        ai_call_successful = True
                        logger.info(f"[AI Call] 第{retry_attempt + 1}次调用成功（已收到内容）")
                        break  # 【关键】成功后立即退出重试循环
                    
                    elif last_error_type == 'idle_timeout':
                        # ⚠️ 空闲超时（30秒无内容）
                        if retry_controller.can_retry():
                            # 还能重试
                            retry_controller.increment_retry()
                            logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时30秒，准备第{retry_controller.get_retry_count() + 1}次重试...")
                            continue
                        else:
                            # 已达最大重试次数
                            logger.error(f"[AI Call] 第{retry_attempt + 1}次调用空闲超时，已达最大重试次数{max_retries}")
                            last_error = "空闲超时：模型30秒未响应"
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
                            logger.info(f"[AI Call] 第{retry_attempt + 1}次调用完成，收到内容长度={len(full_content)}")
                            break
                        else:
                            # 【修复】未收到内容，视为错误，发送error步骤
                            logger.warning(f"[AI Call] 第{retry_attempt + 1}次调用完成但无内容（流结束，模型未返回有效内容）")
                            if retry_controller.can_retry():
                                # 还能重试
                                retry_controller.increment_retry()
                                logger.info(f"[AI Call] 空响应，准备第{retry_controller.get_retry_count() + 1}次重试...")
                                continue
                            else:
                                # 已达最大重试次数，发送error步骤
                                logger.error(f"[AI Call] 空响应重试失败，已达最大重试次数{max_retries}")
                                error_message = "模型未能生成有效回复，请尝试更换问题或稍后重试"
                                yield create_error_response(
                                    error_type="empty_response",
                                    message=error_message,
                                    model=ai_service.model,
                                    provider=ai_service.provider,
                                    retryable=True,
                                    retry_after=3,
                                    step=next_step()
                                )
                                
                                # 【使用统一函数】保存error步骤到数据库
                                # 【小强修复 2026-03-18】添加step字段
                                error_step = {
                                    'type': 'error',
                                    'step': next_step(),  # 添加step字段
                                    'error_type': 'empty_response',
                                    'message': error_message,
                                    'code': 'EMPTY_RESPONSE',
                                    'timestamp': create_timestamp()
                                }
                                await add_step_and_save(error_step, f"错误: {error_message}")
                                return  # 直接返回，不再发送final步骤
                    
                    # ⭐ 【新增-重试机制】重试循环结束，检查最终结果
                if not ai_call_successful:
                    logger.error(f"[AI Call] 重试失败，ai_call_successful={ai_call_successful}")
                    # 根据错误原因返回不同的错误提示
                    if last_error:
                        logger.error(f"[AI Call] 所有重试失败，最后错误: {last_error}, 类型: {last_error_type}")
                        # 使用之前保存的 error_type
                        error_type_map = {
                            'idle_timeout': ('timeout', '请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试'),
                            'timeout_error': ('timeout', '请求超时，请重试'),
                            'read_error': ('server', '读取响应失败，请重试'),
                            'connect_error': ('network', '连接失败，请检查网络'),
                            'protocol_error': ('server', '协议错误，请重试'),
                            'proxy_error': ('network', '代理错误，请检查网络配置'),
                            'write_error': ('server', '发送请求失败'),
                            'network_error': ('network', '网络错误，请检查网络连接'),
                        }
                        if last_error_type in error_type_map:
                            code, error_message = error_type_map[last_error_type]
                        else:
                            code, error_message = 'server', f"服务调用失败: {last_error}"
                        error_type = code
                    else:
                        # 没有错误但也没有收到有效内容，可能是模型返回空响应
                        logger.error(f"[AI Call] 所有重试失败，无有效响应（模型返回空内容）")
                        error_type, error_message = "empty_response", "模型未能生成有效回复，请尝试更换问题或稍后重试"
                    
                    # 发送error步骤而不是final步骤
                    logger.info(f"[Step error] 发送error步骤: error_type={error_type}, message={error_message}")
                    yield create_error_response(
                        error_type=error_type,
                        message=error_message,
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=True,
                        retry_after=3,
                        step=next_step()
                    )
                    
                    # 【使用统一函数】保存error步骤到数据库
                    # 【小强修复 2026-03-18】添加step字段
                    error_step = {
                        'type': 'error',
                        'step': next_step(),  # 添加step字段
                        'error_type': error_type,
                        'message': error_message,
                        'code': 'AI_CALL_ERROR',
                        'timestamp': create_timestamp()
                    }
                    await add_step_and_save(error_step, f"错误: {error_message}")
                    return  # 直接返回，不再发送final步骤
                
                # ═══════════════════════════════════════════════════════════════════════════════
                # ⭐ 【小沈修复 2026-03-17 问题分析与修复说明】
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
                final_step_value = next_step()  # 【小沈修复 2026-03-22】先获取step值，只调用一次
                final_step = {
                    'type': 'final',
                    'step': final_step_value,  # 使用已获取的step值
                    'content': full_content,
                    'model': ai_service.model,
                    'provider': ai_service.provider,
                    'timestamp': create_timestamp()
                }
                current_execution_steps.append(final_step)
                
                # final前强制保存一次，确保所有steps都写入数据库
                logger.info(f"[Step final] 💾 final前强制保存: {len(current_execution_steps)} steps, step={final_step_value}")
                await save_execution_steps_to_db(current_execution_steps, full_content)
                
                # 发送最终结果，【新增】添加provider字段作为兜底
                content_preview = full_content[:200] + "..." if len(full_content) > 200 else full_content
                logger.info(f"[Step final] 🚀 发送final步骤, content长度={len(full_content)}, content预览={content_preview}, step={final_step_value}")
                yield create_final_response(
                    content=full_content,
                    model=ai_service.model,
                    provider=ai_service.provider,
                    display_name=display_name,
                    step=final_step_value  # 使用同一个step值
                )
                
                # 删除重复保存：上面已经保存过，不需要再保存一次
                        
        except asyncio.CancelledError:
            # 【小沈修复】客户端断开连接，记录断开事实并保存数据
            # 说明：
            # 1. 前端断开后，SSE流会被Cancel，此时会进入此异常处理
            # 2. 标记 frontend_disconnected = True，记录断开事实
            # 3. 保存当前的 execution_steps 到数据库（已处理的内容会保留）
            # 4. 由于外层循环会结束，不会真正"继续运行"
            logger.warning("[前端断开] 检测到前端断开，正在保存数据...")
            
            # 标记状态，但不停止后端
            async with running_tasks_lock:
                if task_id in running_tasks:
                    running_tasks[task_id]["frontend_disconnected"] = True
            
            # 尝试保存断开记录到数据库（如果还能保存的话）
            try:
                incident_step = {
                    'type': 'incident',
                    'incident_value': 'interrupted',
                    'message': '客户端断开连接，数据已保存',
                    'timestamp': create_timestamp()
                }
                current_execution_steps.append(incident_step)
                await save_execution_steps_to_db(current_execution_steps, current_content)
                logger.info("[前端断开] 数据已保存，等待外层循环结束...")
            except Exception as e:
                logger.warning(f"[前端断开] 保存断开记录失败: {e}")
            
            # 不 return，让外层循环自然结束
            # 注意：不会继续与LLM通讯，因为流已被取消
            
        except Exception as e:
            # 【小沈代修改 - 统一错误处理】使用 get_user_friendly_error 和 create_error_response
            logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
            error_info = get_user_friendly_error(e)
            error_message = error_info.get("message", "服务调用失败")
            logger.info(f"[Step error] 发送error步骤 - error_type={error_info.get('error_type')}, message={error_message}, code={error_info.get('code')}")
            yield create_error_response(
                error_type=error_info.get("error_type", "server"),
                message=error_message,
                code=error_info.get("code", "INTERNAL_ERROR"),
                model=ai_service.model,
                provider=ai_service.provider,
                retryable=error_info.get("retryable", False),
                retry_after=error_info.get("retry_after"),
                step=next_step()
            )
            
            # 【使用统一函数】保存error步骤到数据库
            # 【小强修复 2026-03-18】添加step字段
            error_step = {
                'type': 'error',
                'step': next_step(),  # 添加step字段
                'error_type': error_info.get("error_type", "server"),
                'message': error_message,
                'code': error_info.get("code", "INTERNAL_ERROR"),
                'timestamp': create_timestamp()
            }
            await add_step_and_save(error_step, f"错误: {error_message}")
        
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

