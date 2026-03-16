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
from app.services.file_operations.tools import get_file_tools
from app.services.file_operations.agent import FileOperationAgent
from app.services.shell_security import check_command_safety
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name  # ⭐ 【小沈添加 2026-03-03】
from app.utils.retry_controller import RetryController  # 【小沈-2026-03-14添加】统一的空闲超时和重试控制器
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError  # 【小沈-2026-03-14添加】通用的空闲超时异步迭代器
from pathlib import Path
import shutil

# ⭐ 【小沈添加 2026-03-16 v11.0】导入sessions模块，用于流式过程中实时保存execution_steps和content
# 目的：解决页面切换/刷新导致的数据丢失问题 - 后端自动保存作为核心保障
from app.api.v1 import sessions

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

# ============================================================
# 统一错误处理工具函数 - 小沈代修改【Phase4重构】
# ============================================================

def create_error_response(
    error_type: str,
    message: str,
    code: str = "INTERNAL_ERROR",
    model: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[str] = None,
    stack: Optional[str] = None,
    retryable: bool = False,
    retry_after: Optional[int] = None
) -> str:
    """
    创建统一的错误响应格式
    
    Args:
        error_type: 错误类型（如 timeout_error, connection_error 等）
        message: 用户友好的错误信息
        code: 错误码（如 TIMEOUT, NOT_FOUND, SECURITY_BLOCKED）
        model: 模型名称（可选）
        provider: 提供商（可选）
        details: 详细错误信息（可选）
        stack: 堆栈信息（可选，仅用于调试）
        retryable: 是否可重试（可选）
        retry_after: 重试等待秒数（可选）
    
    Returns:
        SSE 格式的错误响应字符串
    """
    response: Dict[str, Any] = {
        'type': 'error',
        'code': code,
        'message': message,
        'error_type': error_type
    }
    if model is not None:
        response['model'] = model
    if provider is not None:
        response['provider'] = provider
    if details:
        response['details'] = details
    if stack:
        response['stack'] = stack
    if retryable:
        response['retryable'] = retryable  # type: ignore
    if retry_after is not None:
        response['retry_after'] = retry_after  # type: ignore
    # 添加timestamp字段
    response['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"data: {json.dumps(response)}\n\n"


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
    running_tasks_lock: asyncio.Lock
) -> tuple[bool, str]:
    """
    检查任务是否被中断，如果是则返回中断消息
    
    Args:
        task_id: 任务 ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
    
    Returns:
        (is_interrupted, interrupt_message) 元组
        - is_interrupted: 是否被中断
        - interrupt_message: 中断消息（如果未被中断则为空字符串）
    """
    async with running_tasks_lock:
        if running_tasks.get(task_id, {}).get("cancelled", False):
            # 【Phase4重构】使用新status格式
            return True, f"data: {json.dumps({'type': 'incident', 'incident_value': 'interrupted', 'message': '任务已被中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})}\n\n"
    return False, ""


async def check_and_yield_if_paused(task_id: str, running_tasks: dict, running_tasks_lock: asyncio.Lock) -> AsyncGenerator[str, None]:
    """
    检查任务是否被暂停，如果是则发送paused事件并等待恢复
    
    Args:
        task_id: 任务ID
        running_tasks: 运行中任务字典
        running_tasks_lock: 任务锁
    
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
                    # 【问题5修复】统一使用type='incident' + incident_value
                    yield f"data: {json.dumps({'type': 'incident', 'incident_value': 'resumed', 'message': '任务已恢复', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})}\n\n"
                    running_tasks[task_id]["_was_paused"] = False
                return
        
        # 暂停中，等待恢复
        if is_paused and not running_tasks.get(task_id, {}).get("_was_paused", False):
            # 刚进入暂停状态，发送paused事件
            # 【问题5修复】统一使用type='incident' + incident_value
            async with running_tasks_lock:
                running_tasks[task_id]["_was_paused"] = True
            yield f"data: {json.dumps({'type': 'incident', 'incident_value': 'paused', 'message': '任务已暂停', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})}\n\n"
        
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


# ============================================================
# 统一 final 响应工具函数 - 小沈代修改【修复问题 6】
# ============================================================

def create_final_response(
    content: str,
    model: str,
    provider: str,
    display_name: Optional[str] = None
) -> str:
    """
    创建统一的 final 响应格式
    
    Args:
        content: 最终内容
        model: 模型名称
        provider: 提供商
        display_name: 显示名称（可选）
    
    Returns:
    SSE 格式的 final 响应字符串
    """
    # 【问题5修复】final使用content字段（遵循设计文档7.5要求）
    # 【补充】添加display_name字段
    response = {
        'type': 'final',
        'content': content,
        'display_name': display_name if display_name else f"{provider} ({model})"
    }
    return f"data: {json.dumps(response)}\n\n"

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


def detect_file_operation_intent(message: str) -> tuple[bool, str, float]:
    """
    检测用户消息是否包含文件操作意图（优化版）
    
    【重写】修复问题：
    1. 子串匹配 → 完整词匹配
    2. 关键词太宽泛 → 只保留明确操作词
    3. 去掉加分项
    4. 降低阈值到0.2（提高检测灵敏度）
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型, 置信度0-1)
    """
    import re
    message_lower = message.lower().strip()
    
    # 【修复】扩展关键词列表，支持更多自然语言表达
    # 问题：完整词匹配导致"查看桌面目录的文件有什么"等自然语言无法识别
    # 解决：增加更多自然语言表达，同时保留完整词匹配逻辑
    intent_patterns = {
        "read": {
            "keywords": [
                # 中文明确表达
                '读取文件', '查看文件内容', '打开文件内容', '读文件内容', '显示文件内容',
                '读取', '查看文件', '打开文件', '读文件', '看文件',
                # 【新增】自然语言表达
                '看看文件', '看一下文件', '文件内容是什么', '查看一下文件',
                # 英文明确表达
                'read file', 'view file content', 'open file', 'show file content',
                'read the file', 'cat file',
            ],
        },
        "write": {
            "keywords": [
                # 中文明确表达
                '写入文件', '创建文件', '保存文件到', '写文件内容', '修改文件内容',
                '创建', '保存到', '写入', '新建文件', '新建文',
                # 【新增】自然语言表达
                '帮我写', '帮我创建', '新建一个文件', '创建一个文件',
                # 英文明确表达
                'write file', 'create file', 'save file', 'write to file', 'create a file',
            ],
        },
        "list": {
            "keywords": [
                # 中文明确表达
                '列出目录内容', '查看目录', '显示文件列表', '文件列表', '目录内容',
                '列出', '目录列表', '查看有哪些文件', '列出文件',
                # 【新增】自然语言表达（重点解决桌面查看问题）
                '查看桌面', '桌面有什么', '桌面有哪些', '桌面目录',
                '看看桌面', '看一下桌面', '查看D盘', 'D盘有什么',
                '看看有什么', '有哪些文件', '有什么文件', '目录里有什么',
                '查看一下目录', '查看文件夹', '文件夹里有什么', '看看文件夹',
                # 英文明确表达
                'list directory', 'list files', 'show file list', 'ls -',
                'list all files', 'show files in', 'show desktop', 'what is on desktop',
            ],
        },
        "delete": {
            "keywords": [
                # 中文明确表达
                '删除文件', '删除这个文件', '删除指定文件', '移除文件', '删掉文件',
                '删除', '移除', '删掉', '清空', '删除目录',
                # 【新增】自然语言表达
                '帮我删除', '帮我删掉', '把文件删掉', '删掉这个',
                # 英文明确表达
                'delete file', 'remove file', 'delete this file', 'rm file',
                'delete the file', 'erase file',
            ],
        },
        "move": {
            "keywords": [
                # 中文明确表达
                '移动文件', '移动到', '重命名文件', '改名文件', '转移文件',
                '复制文件', '剪切文件',
                '移动', '重命名', '转移', '复制', '改名',
                # 【新增】自然语言表达
                '帮我移动', '帮我复制', '帮我重命名', '移到', '复制到',
                # 英文明确表达
                'move file', 'rename file', 'move to', 'copy file', 'mv file',
            ],
        },
        "search": {
            "keywords": [
                # 中文明确表达
                '搜索文件', '查找文件内容', '全文搜索', '搜索内容', '查找文件',
                '搜索', '查找', '搜文件', '搜索文件内容',
                # 【新增】自然语言表达
                '帮我搜索', '帮我查找', '找一下文件', '找找文件',
                # 英文明确表达
                'search file', 'search content', 'find file', 'grep file',
                'search in file', 'find content',
            ],
        }
    }
    
    # 完整词匹配：单词边界匹配
    best_intent = None
    best_score = 0.0
    
    for intent, config in intent_patterns.items():
        score = 0.0
        matched_keywords = []
        
        for keyword in config["keywords"]:
            # 使用单词边界匹配，确保是完整词
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                # 完整词匹配，得1.0分
                score += 1.0
                matched_keywords.append(keyword)
        
        # 应用权重
        weight = 1.0
        score *= weight
        
        if score > best_score:
            best_score = score
            best_intent = intent
    
    # 【修复】降低阈值到0.2，提高意图检测灵敏度
    # 原因：完整词匹配导致自然语言输入无法识别（如"查看桌面目录的文件有什么"）
    # 旧阈值0.6太高，导致意图检测失败后走普通LLM路径，LLM不知道有工具可用
    # 降低到0.2后，即使匹配一个完整关键词也能触发文件操作Agent
    CONFIDENCE_THRESHOLD = 0.2
    
    if best_score >= CONFIDENCE_THRESHOLD and best_intent is not None:
        return True, best_intent, min(best_score, 1.0)
    
    return False, "", 0.0


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
                # 调用sessions模块的save_execution_steps函数
                # 注意：这是一个异步函数调用
                result = await sessions.save_execution_steps(
                    request.session_id,
                    sessions.ExecutionStepsUpdate(
                        execution_steps=execution_steps,
                        content=content
                    )
                )
                logger.debug(f"[Save] 保存成功: session_id={request.session_id}, "
                           f"steps_count={len(execution_steps)}, has_content={content is not None}")
            except Exception as e:
                # 保存失败不中断流式响应，只记录日志
                logger.error(f"[Save] 保存失败: {e}")
        
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
        
        # 【前端小新代修改】在流式响应开始时发送start事件
        display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
        
        # 缓存 display_name
        if request.session_id:
            cache_display_name(request.session_id, display_name)
        
        # 【问题1修复】在start阶段添加安全检查
        # 获取最后一条用户消息进行安全检查
        last_message = request.messages[-1].content if request.messages else ""
        security_check_result = check_command_safety(last_message)
        
        # 发送 start 步骤（包含security_check）
        start_data = {
            'type': 'start',
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
        logger.info(f"[Step start] 发送start步骤")
        
        yield f"data: {json.dumps(start_data)}\n\n"
        
        # ⭐ 【小沈添加 2026-03-16 v11.0】start步骤后保存到数据库
        # 目的：解决页面切换/刷新导致的数据丢失问题 - 后端自动保存作为核心保障
        current_execution_steps.append(start_data)
        await save_execution_steps_to_db(current_execution_steps, current_content)
        
        # 如果安全检查未通过，直接返回错误
        if not security_check_result.get('is_safe', True):
            risk = security_check_result.get('risk', '未知风险')
            error_data = {
                'type': 'error',
                'code': 'SECURITY_BLOCKED',
                'message': f'危险操作需确认: {risk}',
                'error_type': 'security',
                'details': f"risk_level: {security_check_result.get('risk_level')}",
                'retryable': False,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'model': request.model,
                'provider': request.provider
            }
            logger.info(f"[Step error] 发送error步骤(安全检测拦截)")
            yield f"data: {json.dumps(error_data)}\n\n"
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
            
            # 步骤计数器
            step_counter = 0
            
            def next_step():
                nonlocal step_counter
                step_counter += 1
                return step_counter
            
            # 1. 发送思考
            thought_data = {'type': 'thought', 'step': next_step(), 'thinking_prompt': '正在分析任务...'}
            logger.info(f"[Step thought] 发送thought步骤")
            yield f"data: {json.dumps(thought_data)}\n\n"
            
            # ⭐ 【小沈添加 2026-03-16 v11.0】thought步骤后保存到数据库
            current_execution_steps.append(thought_data)
            await save_execution_steps_to_db(current_execution_steps, current_content)
            
            await asyncio.sleep(0.3)
            
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
                # 文件操作：逐步推送执行步骤
                # 【问题2修复】type改为action_tool，添加必需字段
                action1_data = {
                    'type': 'action_tool',
                    'step': next_step(),
                    'tool_name': 'notification',
                    'tool_params': {'description': '检测到文件操作意图，开始执行...'},
                    'execution_status': 'success',
                    'summary': '检测到文件操作意图，开始执行...',
                    'raw_data': None,
                    'action_retry_count': 0
                }
                yield f"data: {json.dumps(action1_data)}\n\n"
                
                # ⭐ 【小沈添加 2026-03-16 v11.0】action1步骤后保存到数据库
                current_execution_steps.append(action1_data)
                await save_execution_steps_to_db(current_execution_steps, current_content)
                
                await asyncio.sleep(0.3)
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        # 【问题5修复】统一使用type='incident' + incident_value
                        interrupted_data = {'type': 'incident', 'incident_value': 'interrupted', 'message': '任务已被中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                        logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        return
                
                # 安全检测
                is_safe, risk = check_command_safety(last_message)
                if not is_safe:
                    # 【问题6修复】使用统一错误格式
                    logger.info(f"[Step error] 发送error步骤(安全检测)")
                    yield create_error_response(
                        error_type="security_error",
                        message=f"危险操作需确认: {risk}",
                        code="SECURITY_BLOCKED",
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=False
                    )
                    return
                
                # 【小健检查修复】遵循字段设计原则5：禁止兼容字段
                # 【问题4修复】observation使用设计文档字段
                # 【2026-03-11 重命名】字段加 obs_ 前缀，避免与其他type字段混淆
                observation1_data = {
                    'type': 'observation',
                    'step': next_step(),
                    'obs_execution_status': 'success',
                    'obs_summary': f'安全检测{"通过" if is_safe else "未通过"}',
                    'obs_raw_data': {'is_safe': is_safe, 'risk': risk},
                    'content': '',  # 安全检测没有思考过程
                    'obs_reasoning': '',
                    'obs_action_tool': 'security_check',
                    'obs_params': {},
                    'is_finished': True
                }
                logger.info(f"[Step observation] 发送observation步骤")
                yield f"data: {json.dumps(observation1_data)}\n\n"
                
                # ⭐ 【小沈添加 2026-03-16 v11.0】observation1步骤后保存到数据库
                current_execution_steps.append(observation1_data)
                await save_execution_steps_to_db(current_execution_steps, current_content)
                
                await asyncio.sleep(0.3)
                
                # 创建Agent执行
                session_id = str(uuid.uuid4())
                ai_service = AIServiceFactory.get_service()
                
                # 定义llm_client函数（适配FileOperationAgent）
                async def llm_client(message, history=None):
                    response = await ai_service.chat(message, history)
                    # 转换为Agent需要的格式
                    return type('obj', (object,), {'content': response.content})()
                
                agent = FileOperationAgent(
                    llm_client=llm_client,
                    session_id=session_id
                )
                
                # 【问题2修复】type改为action_tool，添加必需字段
                action2_data = {
                    'type': 'action_tool',
                    'step': next_step(),
                    'tool_name': 'notification',
                    'tool_params': {'description': '执行文件操作...'},
                    'execution_status': 'success',
                    'summary': '执行文件操作...',
                    'raw_data': None,
                    'action_retry_count': 0
                }
                yield f"data: {json.dumps(action2_data)}\n\n"
                
                # ⭐ 【小沈添加 2026-03-16 v11.0】action2步骤后保存到数据库
                current_execution_steps.append(action2_data)
                await save_execution_steps_to_db(current_execution_steps, current_content)
                
                # 流式执行（每步检查中断）
                try:
                    # 【Phase4核心修改】使用run_stream异步流式输出
                    async for event in agent.run_stream(last_message):
                        # 每步检查是否被中断
                        async with running_tasks_lock:
                            if running_tasks.get(task_id, {}).get("cancelled", False):
                                # 【2026-03-11 重命名】status_value -> incident_value
                                interrupted_data = {'type': 'incident', 'incident_value': 'interrupted', 'message': '任务已被中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                                logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                                yield f"data: {json.dumps(interrupted_data)}\n\n"
                                break
                        
                        event_type = event.get('type')
                        
                        if event_type == 'thought':
                            # Thought阶段
                            thought_data = {
                                'type': 'thought',
                                'step': event.get('step', 0),
                                'content': event.get('content', ''),
                                'reasoning': event.get('reasoning', ''),
                                'action_tool': event.get('action_tool', ''),
                                'params': event.get('params', {})
                            }
                            logger.info(f"[Step thought] 发送thought步骤")
                            yield f"data: {json.dumps(thought_data)}\n\n"
                            
                            # ⭐ 【小沈添加 2026-03-16 v11.0】thought步骤后保存到数据库
                            current_execution_steps.append(thought_data)
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                        
                        elif event_type == 'action_tool':
                            # Action阶段
                            action_data = {
                                'type': 'action_tool',
                                'step': event.get('step', 0),
                                'tool_name': event.get('tool_name', ''),
                                'tool_params': event.get('tool_params', {}),
                                'execution_status': event.get('execution_status', 'success'),
                                'summary': event.get('summary', ''),
                                'raw_data': event.get('raw_data'),
                                'action_retry_count': event.get('action_retry_count', 0)
                            }
                            logger.info(f"[Step action_tool] 发送action_tool步骤(执行工具)")
                            yield f"data: {json.dumps(action_data)}\n\n"
                            
                            # ⭐ 【小沈添加 2026-03-16 v11.0】action_tool步骤后保存到数据库
                            current_execution_steps.append(action_data)
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                        
                        elif event_type == 'observation':
                            # Observation阶段
                            # 【2026-03-11 重命名】字段加 obs_ 前缀，避免与其他type字段混淆
                            observation_data = {
                                'type': 'observation',
                                'step': event.get('step', 0),
                                'obs_execution_status': event.get('execution_status', 'success'),
                                'obs_summary': event.get('summary', ''),
                                'obs_raw_data': event.get('raw_data'),
                                'content': event.get('content', ''),
                                'obs_reasoning': event.get('reasoning', ''),
                                'obs_action_tool': event.get('action_tool', ''),
                                'obs_params': event.get('params', {}),
                                'is_finished': event.get('is_finished', False)
                            }
                            logger.info(f"[Step observation] 发送observation步骤")
                            yield f"data: {json.dumps(observation_data)}\n\n"
                            
                            # ⭐ 【小沈添加 2026-03-16 v11.0】observation步骤后保存到数据库
                            current_execution_steps.append(observation_data)
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                        
                        elif event_type == 'final':
                            # 最终结果
                            final_data = {
                                'type': 'final',
                                'content': event.get('content', '')
                            }
                            logger.info(f"[Step final] 发送final步骤")
                            yield f"data: {json.dumps(final_data)}\n\n"
                            
                            # ⭐ 【小沈添加 2026-03-16 v11.0】final步骤后保存完整数据到数据库
                            # 保存完整的execution_steps和content
                            current_content = final_data.get('content', '')
                            await save_execution_steps_to_db(current_execution_steps, current_content)
                            break
                        
                        elif event_type == 'error':
                            # 错误
                            error_data = {
                                'type': 'error',
                                'code': 'AGENT_ERROR',
                                'message': event.get('message', '未知错误'),
                                'error_type': 'agent',
                                'retryable': event.get('retryable', False),
                                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                'model': request.model,
                                'provider': request.provider
                            }
                            logger.info(f"[Step error] 发送error步骤")
                            yield f"data: {json.dumps(error_data)}\n\n"
                            break
                        
                        await asyncio.sleep(0.05)
                    
                    # 检查是否被中断（在循环内已处理）
                    
                except Exception as e:
                    # 【小沈代修改 - 修复问题4】统一错误处理格式，记录日志
                    logger.error(f"文件操作执行出错：task_id={task_id}, error={e}", exc_info=True)
                    yield create_error_response(
                        error_type="file_operation_error",
                        message="文件操作执行失败",
                        model=ai_service.model,
                        provider=ai_service.provider,
                        retryable=False
                    )
            else:
                # 普通对话：调用AI服务（流式）
                # 【优化1版修复】不发送action_tool，直接发送chunk
                # 符合5-9章设计：普通对话只有chunk → final
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        # 【原则4整改】字段拆分：content → message
                        interrupted_data = {'type': 'incident', 'incident_value': 'interrupted', 'message': '任务已被中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                        logger.info(f"[Step incident] 发送interrupted步骤")
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
                
                for retry_attempt in range(max_retries + 1):
                    if retry_attempt > 0:
                        # 发送重试提示给前端
                        retry_data = {
                            'type': 'incident',
                            'incident_value': 'retrying',
                            'message': f'请求超时，正在重试 ({retry_attempt}/{max_retries})...',
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
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
                        
                        # 【小沈-2026-03-14修复】使用 IdleTimeoutIterator 包装流式迭代器，实现实时空闲超时检测
                        idle_timeout_stream = IdleTimeoutIterator(
                            ai_service.chat_stream(message=last_message, history=history),
                            timeout_seconds=30.0,
                            name=f"AI-Stream-{retry_attempt + 1}"
                        )
                        
                        async for chunk in idle_timeout_stream:
                            # 注意：IdleTimeoutIterator 自动检测空闲超时，收到内容时自动重置计时器
                            # 如果30秒内没有下一个 chunk，会抛出 IdleTimeoutError
                            
                            chunk_count += 1
                            # 检查是否被中断
                            # 【原则4整改】content → message
                            async with running_tasks_lock:
                                if running_tasks.get(task_id, {}).get("cancelled", False):
                                    interrupted_data = {'type': 'incident', 'incident_value': 'interrupted', 'message': '任务已被中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                                    logger.info(f"[Step incident] 发送interrupted步骤")
                                    yield f"data: {json.dumps(interrupted_data)}\n\n"
                                    return
                            
                            # ⭐ 暂停检查：AI流式响应过程中也检查暂停状态
                            async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
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
                            
                            if chunk.content:
                                has_received_content = True
                                full_content += chunk.content
                                
                                # ⭐ 【小沈添加 2026-03-16 v11.0】跟踪content和is_reasoning变化
                                # 目的：解决content覆盖问题 - 在is_reasoning变化时保存
                                current_content = full_content  # 累积content
                                current_is_reasoning = getattr(chunk, 'is_reasoning', False)
                                
                                # ⭐ 【小沈添加 2026-03-16 v11.0】检测is_reasoning变化，变化时保存
                                # 目的：解决content覆盖问题 - 在is_reasoning变化时保存到数据库
                                if last_is_reasoning != current_is_reasoning:
                                    # is_reasoning状态变化，保存当前累积的content
                                    logger.info(f"[Save] is_reasoning变化: {last_is_reasoning} -> {current_is_reasoning}，保存content到数据库")
                                    await save_execution_steps_to_db(current_execution_steps, current_content)
                                    last_is_reasoning = current_is_reasoning
                                
                                # ⭐ 【调试日志】记录每个chunk
                                logger.debug(f"[AI Chunk] #{chunk_count}: {chunk.content[:100]}..." if len(chunk.content) > 100 else f"[AI Chunk] #{chunk_count}: {chunk.content}")
                                # 逐token发送到前端
                                # 【重要】清晰接口：只使用 content 和 is_reasoning 两个字段
                                chunk_data = {
                                    'type': 'chunk', 
                                    'content': chunk.content,                    # 显示的文本内容
                                    'is_reasoning': current_is_reasoning  # true=思考，false=回答
                                }
                                logger.info(f"[Step chunk] 发送chunk步骤#{chunk_count}: content长度={len(chunk.content)}, is_reasoning={chunk_data['is_reasoning']}")
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
                                yield create_error_response(
                                    error_type="empty_response",
                                    message="模型未能生成有效回复，请尝试更换问题或稍后重试",
                                    model=ai_service.model,
                                    provider=ai_service.provider,
                                    retryable=True,
                                    retry_after=3
                                )
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
                        retry_after=3
                    )
                    return  # 直接返回，不再发送final步骤
                
                # 发送最终结果，【新增】添加provider字段作为兜底
                content_preview = full_content[:200] + "..." if len(full_content) > 200 else full_content
                logger.info(f"[Step final] 🚀 发送final步骤, content长度={len(full_content)}, content预览={content_preview}")
                yield create_final_response(
                    content=full_content,
                    model=ai_service.model,
                    provider=ai_service.provider,
                    display_name=display_name
                )
                
                # ⭐ 【小沈添加 2026-03-16 v11.0】final步骤后保存完整数据到数据库
                # 保存完整的execution_steps和content
                current_content = full_content
                await save_execution_steps_to_db(current_execution_steps, current_content)
                        
        except asyncio.CancelledError:
            # 客户端断开连接，任务被中断
            async with running_tasks_lock:
                running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
            # 【原则4整改】content → message
            interrupted_data = {'type': 'incident', 'incident_value': 'interrupted', 'message': '客户端断开连接，任务中断', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开)")
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            
        except Exception as e:
            # 【小沈代修改 - 统一错误处理】使用 get_user_friendly_error 和 create_error_response
            logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
            error_info = get_user_friendly_error(e)
            logger.info(f"[Step error] 发送error步骤")
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

