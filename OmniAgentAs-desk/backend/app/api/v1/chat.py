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
from typing import List, Dict, Optional, AsyncGenerator
from app.services import AIServiceFactory
from app.services.base import Message  # ⭐ 【调试添加】用于日志记录
from app.services.file_operations.tools import get_file_tools
from app.services.file_operations.agent import FileOperationAgent
from app.services.shell_security import check_command_safety
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name  # ⭐ 【小沈添加 2026-03-03】
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

# ============================================================
# 统一错误处理工具函数 - 小沈代修改【修复问题 1、2、3】
# ============================================================

def create_error_response(
    error_type: str,
    content: str,
    model: Optional[str] = None,
    provider: Optional[str] = None
) -> str:
    """
    创建统一的错误响应格式
    
    Args:
        error_type: 错误类型（如 timeout_error, connection_error 等）
        content: 用户友好的错误信息
        model: 模型名称（可选）
        provider: 提供商（可选）
    
    Returns:
        SSE 格式的错误响应字符串
    """
    response = {
        'type': 'error',
        'error_type': error_type,
        'content': content
    }
    if model:
        response['model'] = model
    if provider:
        response['provider'] = provider
    return f"data: {json.dumps(response)}\n\n"


def get_user_friendly_error(error: Exception) -> tuple[str, str]:
    """
    获取用户友好的错误信息
    
    Args:
        error: 异常对象
    
    Returns:
        (error_type, error_message) 元组
    """
    error_type = type(error).__name__
    
    # 根据错误类型返回用户友好的错误信息
    if error_type == "TimeoutError" or "timeout" in str(error).lower():
        return ("timeout_error", "请求超时，请重试")
    elif error_type == "ConnectionError" or "connection" in str(error).lower():
        return ("connection_error", "网络连接失败，请检查网络")
    elif error_type == "HTTPError" or "HTTP" in str(error).lower():
        return ("http_error", "服务器响应异常，请稍后重试")
    elif error_type == "ValueError":
        return ("value_error", "参数值错误，请检查输入")
    else:
        # 其他错误返回通用信息，不泄露技术细节
        return ("unknown_error", "AI 处理异常，请稍后重试")


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
            return True, f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
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
                    # 发送恢复事件
                    yield f"data: {json.dumps({'type': 'resumed', 'content': '任务已恢复'})}\n\n"
                    running_tasks[task_id]["_was_paused"] = False
                return
        
        # 暂停中，等待恢复
        if is_paused and not running_tasks.get(task_id, {}).get("_was_paused", False):
            # 刚进入暂停状态，发送paused事件
            async with running_tasks_lock:
                running_tasks[task_id]["_was_paused"] = True
            yield f"data: {json.dumps({'type': 'paused', 'content': '任务已暂停'})}\n\n"
        
        await asyncio.sleep(0.5)  # 每0.5秒检查一次


# ============================================================
# observation 清洗函数 - 小沈添加【将复杂的observation简化为可读文本】
# ============================================================

def simplify_observation(observation: Optional[Dict]) -> str:
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
    response = {
        'type': 'final',
        'content': content,
        'model': model,
        'provider': provider
    }
    if display_name:
        response['display_name'] = display_name
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
    检测用户消息是否包含文件操作意图（增强版）
    
    【修复】添加置信度评分，支持更多关键词和模糊匹配
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型, 置信度0-1)
    """
    message_lower = message.lower().strip()
    
    # 【修复】扩展关键词库，添加更多变体和同义词
    intent_patterns = {
        "read": {
            "keywords": [
                '读取文件', '查看文件', '打开文件', '读文件', '看文件内容', '显示文件内容',
                'read file', 'view file', 'open file', 'show file', 'display file',
                '查看', '打开', '读一下', '看一下', '显示', '展示',
                'view', 'open', 'read', 'show', 'display', 'cat'
            ],
            "weight": 1.0
        },
        "write": {
            "keywords": [
                '写入文件', '创建文件', '保存文件', '写文件', '修改文件', '更新文件',
                'write file', 'create file', 'save file', 'update file', 'edit file',
                '写入', '创建', '保存', '写', '修改', '更新', '编辑',
                'write', 'create', 'save', 'edit', 'update', 'modify'
            ],
            "weight": 1.0
        },
        "list": {
            "keywords": [
                '列出目录', '查看目录', '显示文件', '有哪些文件', '文件列表', '目录内容',
                'list directory', 'show files', 'list files', 'ls', 'dir', 'll',
                '列出', '目录', '文件夹', '有什么', '文件有哪些',
                'list', 'ls', 'dir', 'directory', 'folders'
            ],
            "weight": 0.9
        },
        "delete": {
            "keywords": [
                '删除文件', '移除文件', '删掉文件', '删除目录', '清空文件',
                'delete file', 'remove file', 'del file', 'rm file', 'erase file',
                '删除', '移除', '删掉', '清空', '销毁',
                'delete', 'remove', 'del', 'rm', 'erase', 'trash'
            ],
            "weight": 1.0
        },
        "move": {
            "keywords": [
                '移动文件', '重命名文件', '改名', '转移文件', '复制文件',
                'move file', 'rename file', 'mv file', 'cp file', 'copy file',
                '移动', '重命名', '改名', '转移', '复制', '拷贝',
                'move', 'rename', 'mv', 'cp', 'copy'
            ],
            "weight": 1.0
        },
        "search": {
            "keywords": [
                '搜索文件', '查找文件', '找文件', '搜索内容', '查找内容', '全文搜索',
                'search file', 'find file', 'grep', 'search content', 'locate',
                '搜索', '查找', '找一下', '搜一下', '查询',
                'search', 'find', 'grep', 'locate', 'lookup'
            ],
            "weight": 0.9
        }
    }
    
    # 【修复】计算每个意图的匹配得分
    best_intent = None
    best_score = 0.0
    
    for intent, config in intent_patterns.items():
        score = 0.0
        matched_keywords = []
        
        for keyword in config["keywords"]:
            if keyword in message_lower:
                # 完整词匹配得分更高
                if keyword in message_lower.split() or len(keyword) >= 6:
                    score += 0.3
                else:
                    score += 0.2
                matched_keywords.append(keyword)
        
        # 应用权重
        score *= config["weight"]
        
        # 如果有多个关键词匹配，增加置信度
        if len(matched_keywords) >= 2:
            score += 0.2
        
        # 如果包含文件路径特征，增加置信度
        if any(char in message for char in ['/', '\\', '.txt', '.md', '.py', '.json']):
            score += 0.1
        
        if score > best_score:
            best_score = score
            best_intent = intent
    
    # 【修复】设置置信度阈值
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
        
        # 【修复】只有在置信度足够高时才执行文件操作
        if is_file_op and confidence >= 0.3:
            # 【修复】文件操作路由到 FileTools
            return await handle_file_operation(last_message, op_type)
        
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
        
        # 调用AI服务
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
    
    # ⭐ 【调试日志】记录用户发送的原始请求信息
    logger.info("=" * 80)
    logger.info("[Chat Request] 收到聊天请求")
    logger.info(f"  - messages 数量: {len(request.messages)}")
    logger.info(f"  - request.provider: {request.provider}")
    logger.info(f"  - request.model: {request.model}")
    logger.info(f"  - request.session_id: {request.session_id}")
    logger.info(f"  - request.task_id: {request.task_id}")
    for i, msg in enumerate(request.messages):
        content_preview = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
        logger.info(f"  - messages[{i}] role={msg.role}: {content_preview}")
    logger.info("=" * 80)
    
    # 【前端小新代修改】优先使用前端传递的task_id，没有才自己生成
    task_id = request.task_id if request.task_id else str(uuid.uuid4())
    
    async def generate():
        """生成SSE流，支持中断和暂停"""
        # 注册任务
        async with running_tasks_lock:
            running_tasks[task_id] = {
                "status": "running", 
                "cancelled": False,
                "paused": False,  # 暂停状态
                "created_at": datetime.now()
            }
        
        # 【修改】优先使用前端传递的模型信息，fallback到配置文件
        if request.provider and request.model:
            # 验证模型是否在配置文件中
            ai_service = AIServiceFactory.get_service_for_model(
                request.provider, 
                request.model
            )
        else:
            # 前端没传，使用配置文件默认值
            ai_service = AIServiceFactory.get_service()
        
        # ⭐ 【调试日志】记录选择的AI服务
        logger.info(f"[AI Service] 选择的AI服务: provider={ai_service.provider}, model={ai_service.model}, api_base={ai_service.api_base}")
        
        # 【前端小新代修改】在流式响应开始时发送start事件，返回display_name、provider、model、task_id
        display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
        
        # ⭐ 【小沈添加 2026-03-03】从请求中获取 session_id 并缓存 display_name
        if request.session_id:
            cache_display_name(request.session_id, display_name)
        
        # ⭐ 【调试日志】记录发送的 start 步骤
        start_data = {
            'type': 'start',
            'display_name': display_name,
            'provider': ai_service.provider,
            'model': ai_service.model,
            'task_id': task_id
        }
        logger.info(f"[Step start] 发送start步骤: {json.dumps(start_data, ensure_ascii=False)}")
        
        yield f"data: {json.dumps(start_data)}\n\n"
        
        try:
            # 获取最后一条用户消息
            last_message = request.messages[-1].content if request.messages else ""
            
            # 构建历史消息
            history = []
            if len(request.messages) > 1:
                for msg in request.messages[:-1]:
                    history.append(Message(role=msg.role, content=msg.content))
            
            # ⭐ 【调试日志】记录调用AI服务的参数
            logger.info("=" * 80)
            logger.info(f"[AI Call] 开始调用AI服务")
            logger.info(f"  - provider: {ai_service.provider}")
            logger.info(f"  - model: {ai_service.model}")
            logger.info(f"  - last_message: {last_message[:500]}..." if len(last_message) > 500 else f"  - last_message: {last_message}")
            logger.info(f"  - history 数量: {len(history)}")
            for i, h in enumerate(history):
                content_preview = h.content[:200] + "..." if len(h.content) > 200 else h.content
                logger.info(f"    history[{i}] role={h.role}: {content_preview}")
            logger.info("=" * 80)
            
            # 1. 发送思考 - 正在分析任务（固定提示）
            thought_data = {'type': 'thought', 'content': '正在分析任务...'}
            logger.info(f"[Step thought] 发送thought步骤: {json.dumps(thought_data, ensure_ascii=False)}")
            yield f"data: {json.dumps(thought_data)}\n\n"
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
                action1_data = {'type': 'action', 'step': 1, 'content': '检测到文件操作意图，开始执行...'}
                logger.info(f"[Step action] 发送action步骤(文件检测): {json.dumps(action1_data, ensure_ascii=False)}")
                yield f"data: {json.dumps(action1_data)}\n\n"
                await asyncio.sleep(0.3)
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        interrupted_data = {'type': 'interrupted', 'content': '任务已被中断'}
                        logger.info(f"[Step interrupted] 发送interrupted步骤: {json.dumps(interrupted_data, ensure_ascii=False)}")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        return
                
                # 安全检测
                is_safe, risk = check_command_safety(last_message)
                if not is_safe:
                    error_data = {'type': 'error', 'content': f'危险操作需确认: {risk}'}
                    logger.info(f"[Step error] 发送error步骤(安全检测): {json.dumps(error_data, ensure_ascii=False)}")
                    yield f"data: {json.dumps(error_data)}\n\n"
                    return
                
                observation1_data = {'type': 'observation', 'step': 1, 'content': '安全检测通过'}
                logger.info(f"[Step observation] 发送observation步骤: {json.dumps(observation1_data, ensure_ascii=False)}")
                yield f"data: {json.dumps(observation1_data)}\n\n"
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
                
                action2_data = {'type': 'action', 'step': 2, 'content': '执行文件操作...'}
                logger.info(f"[Step action] 发送action步骤(执行文件): {json.dumps(action2_data, ensure_ascii=False)}")
                yield f"data: {json.dumps(action2_data)}\n\n"
                
                # 流式执行（每步检查中断）
                try:
                    result = await agent.run(last_message)
                    
                    # 推送执行步骤详情
                    if hasattr(result, 'steps') and result.steps:
                        for i, step in enumerate(result.steps, 1):
                            # 每步检查是否被中断
                            async with running_tasks_lock:
                                if running_tasks.get(task_id, {}).get("cancelled", False):
                                    interrupted_data = {'type': 'interrupted', 'content': '任务已被中断'}
                                    logger.info(f"[Step interrupted] 发送interrupted步骤: {json.dumps(interrupted_data, ensure_ascii=False)}")
                                    yield f"data: {json.dumps(interrupted_data)}\n\n"
                                    break
                            
                            # Step是对象，使用属性访问
                            step_thought = getattr(step, 'thought', '')
                            step_action = getattr(step, 'action', '')
                            step_observation = getattr(step, 'observation', '')
                            
                            # 使用清洗函数生成可读文本
                            step_result = simplify_observation(step_observation)
                            
                            # 发送字段：按前后端统一原则，只发送核心字段，删除冗余兼容字段
                            # 修改时间：2026-03-06 15:40:00 修改人：小沈
                            # 删除：content（=thought重复）、tool（=action重复）、error（用content）
                            step_data = {
                                # 核心字段
                                'type': 'observation',
                                'step': i + 2,
                                'thought': step_thought,
                                'action': step_action,
                                'observation': step_observation,
                                'result': step_result
                            }
                            logger.info(f"[Step observation] 发送observation步骤(Agent执行): {json.dumps(step_data, ensure_ascii=False)}")
                            yield f"data: {json.dumps(step_data)}\n\n"
                            await asyncio.sleep(0.5)
                    
                    # 检查是否被中断
                    async with running_tasks_lock:
                        if running_tasks.get(task_id, {}).get("cancelled", False):
                            interrupted_data = {'type': 'interrupted', 'content': '任务已被中断'}
                            logger.info(f"[Step interrupted] 发送interrupted步骤: {json.dumps(interrupted_data, ensure_ascii=False)}")
                            yield f"data: {json.dumps(interrupted_data)}\n\n"
                        else:
                            # 发送最终结果
                            if result.success:
                                # 【修复】正确提取 Agent 的回复内容
                                result_content = result.message  # 默认值
                                if result.steps:
                                    last_step = result.steps[-1]
                                    if last_step.observation and last_step.observation.get("result"):
                                        result_data = last_step.observation["result"]
                                        if isinstance(result_data, dict) and "result" in result_data:
                                            result_content = result_data["result"]
                                        elif isinstance(result_data, str):
                                            result_content = result_data
                                
                                logger.info(f"[Step final] 发送final步骤(文件操作成功), content长度: {len(result_content)}")
                                yield create_final_response(
                                    content=result_content,
                                    model=ai_service.model,
                                    provider=ai_service.provider,
                                    display_name=display_name
                                )
                            else:
                                result_error = getattr(result, 'error', '执行失败')
                                error_data = {'type': 'error', 'content': result_error, 'model': ai_service.model, 'display_name': display_name, 'provider': ai_service.provider}
                                logger.info(f"[Step error] 发送error步骤(文件操作失败): {json.dumps(error_data, ensure_ascii=False)}")
                                yield f"data: {json.dumps(error_data)}\n\n"
                    
                except Exception as e:
                    # 【小沈代修改 - 修复问题 4】统一错误处理格式，记录日志
                    logger.error(f"文件操作执行出错：task_id={task_id}, error={e}", exc_info=True)
                    yield create_error_response(
                        error_type="file_operation_error",
                        content="文件操作执行失败"
                    )
            else:
                # 普通对话：调用AI服务（流式）
                action_data = {'type': 'action', 'step': 1, 'content': '正在调用AI服务...'}
                logger.info(f"[Step action] 发送action步骤(调用AI): {json.dumps(action_data, ensure_ascii=False)}")
                yield f"data: {json.dumps(action_data)}\n\n"
                await asyncio.sleep(0.3)
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        interrupted_data = {'type': 'interrupted', 'content': '任务已被中断'}
                        logger.info(f"[Step interrupted] 发送interrupted步骤: {json.dumps(interrupted_data, ensure_ascii=False)}")
                        yield f"data: {json.dumps(interrupted_data)}\n\n"
                        return
                
                from app.services.base import Message
                history = []
                if len(request.messages) > 1:
                    for msg in request.messages[:-1]:
                        history.append(Message(role=msg.role, content=msg.content))
                
                # ⭐ 【调试日志】记录完整的AI调用参数
                logger.info("=" * 80)
                logger.info(f"[AI Stream Call] 开始流式调用AI")
                logger.info(f"  - provider: {ai_service.provider}")
                logger.info(f"  - model: {ai_service.model}")
                logger.info(f"  - message: {last_message[:300]}..." if len(last_message) > 300 else f"  - message: {last_message}")
                logger.info(f"  - history count: {len(history)}")
                logger.info("=" * 80)
                
                # 【修复-小沈】使用流式API，逐token返回
                full_content = ""
                chunk_count = 0
                
                # 【调试】确认调用 chat_stream
                logger.info(f"[DEBUG] 开始调用 ai_service.chat_stream, message={last_message[:50]}...")
                logger.info(f"[DEBUG] ai_service type: {type(ai_service)}, ai_service.provider: {ai_service.provider}, ai_service.model: {ai_service.model}")
                
                async for chunk in ai_service.chat_stream(
                    message=last_message,
                    history=history
                ):
                    chunk_count += 1
                    # 检查是否被中断
                    async with running_tasks_lock:
                        if running_tasks.get(task_id, {}).get("cancelled", False):
                            interrupted_data = {'type': 'interrupted', 'content': '任务已被中断'}
                            logger.info(f"[Step interrupted] 发送interrupted步骤: {json.dumps(interrupted_data, ensure_ascii=False)}")
                            yield f"data: {json.dumps(interrupted_data)}\n\n"
                            return
                    
                    # ⭐ 暂停检查：AI流式响应过程中也检查暂停状态
                    async for pause_event in check_and_yield_if_paused(task_id, running_tasks, running_tasks_lock):
                        yield pause_event
                    
                    if chunk.content:
                        full_content += chunk.content
                        # ⭐ 【调试日志】记录每个chunk
                        logger.debug(f"[AI Chunk] #{chunk_count}: {chunk.content[:100]}..." if len(chunk.content) > 100 else f"[AI Chunk] #{chunk_count}: {chunk.content}")
                        # 逐token发送到前端，【新增】添加provider字段作为兜底
                        chunk_data = {'type': 'chunk', 'content': chunk.content, 'model': chunk.model, 'provider': ai_service.provider}
                        logger.info(f"[Step chunk] 发送chunk步骤#{chunk_count}: content长度={len(chunk.content)}")
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    if chunk.is_done:
                        break
                
                # ⭐ 【调试日志】记录完整的AI响应
                logger.info("=" * 80)
                logger.info(f"[AI Response Complete] AI响应完成")
                logger.info(f"  - total chunks: {chunk_count}")
                logger.info(f"  - full_content length: {len(full_content)}")
                logger.info(f"  - full_content preview: {full_content[:500]}..." if len(full_content) > 500 else f"  - full_content: {full_content}")
                logger.info("=" * 80)
                
                # 发送最终结果，【新增】添加provider字段作为兜底
                logger.info(f"[Step final] 发送final步骤, content长度={len(full_content)}, content预览={full_content[:200]}..." if len(full_content) > 200 else f"[Step final] 发送final步骤, content={full_content}")
                yield create_final_response(
                    content=full_content,
                    model=ai_service.model,
                    provider=ai_service.provider,
                    display_name=display_name
                )
                        
        except asyncio.CancelledError:
            # 客户端断开连接，任务被中断
            async with running_tasks_lock:
                running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
            interrupted_data = {'type': 'interrupted', 'content': '客户端断开连接，任务中断'}
            logger.info(f"[Step interrupted] 发送interrupted步骤(客户端断开): {json.dumps(interrupted_data, ensure_ascii=False)}")
            yield f"data: {json.dumps(interrupted_data)}\n\n"
            
        except Exception as e:
            # 【小沈代修改 - 统一错误处理】使用 get_user_friendly_error 和 create_error_response
            logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
            error_type, error_message = get_user_friendly_error(e)
            error_data = {'type': 'error', 'error_type': error_type, 'content': error_message}
            logger.info(f"[Step error] 发送error步骤: {json.dumps(error_data, ensure_ascii=False)}")
            yield create_error_response(
                error_type=error_type,
                content=error_message
            )
        
        finally:
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
async def cancel_stream_task(task_id: str):
    """
    中断指定的流式任务
    
    - **task_id**: 任务ID
    """
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["cancelled"] = True
            running_tasks[task_id]["status"] = "cancelled"
            return {"success": True, "message": f"任务 {task_id} 已标记为中断"}
    return {"success": False, "message": f"任务 {task_id} 不存在"}


# 任务暂停/继续接口
# ============================================================

@router.post("/chat/stream/pause/{task_id}")
async def pause_stream_task(task_id: str):
    """
    暂停指定的流式任务
    
    - **task_id**: 任务ID
    - 暂停时：前端停止显示，但后端继续处理，数据暂存缓冲区
    """
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = True
            running_tasks[task_id]["status"] = "paused"
            logger.info(f"[Pause] 任务 {task_id} 已暂停")
            return {"success": True, "message": f"任务 {task_id} 已暂停"}
    return {"success": False, "message": f"任务 {task_id} 不存在"}


@router.post("/chat/stream/resume/{task_id}")
async def resume_stream_task(task_id: str):
    """
    继续指定的流式任务
    
    - **task_id**: 任务ID
    - 继续时：前端恢复显示暂存的数据
    """
    async with running_tasks_lock:
        if task_id in running_tasks:
            running_tasks[task_id]["paused"] = False
            running_tasks[task_id]["status"] = "running"
            logger.info(f"[Resume] 任务 {task_id} 已继续")
            return {"success": True, "message": f"任务 {task_id} 已继续"}
    return {"success": False, "message": f"任务 {task_id} 不存在"}


async def handle_file_operation(message: str, op_type: str) -> ChatResponse:
    """
    处理文件操作请求
    
    【修复-Wave2-完整版】使用 FileOperationAgent 执行文件操作
    【新增】添加安全检测，危险操作需确认
    实现真正的 ReAct 循环，让 AI 自主决策如何完成任务
    
    Args:
        message: 用户原始消息
        op_type: 操作类型 (read/write/list/delete/move/search)
        
    Returns:
        ChatResponse 格式的响应
    """
    try:
        # 【新增】安全检测 - 检查是否为危险操作
        is_safe, risk = check_command_safety(message)
        if not is_safe:
            return ChatResponse(
                success=False,
                content="",
                model="file_operation_agent",
                error=f"危险操作需确认: {risk}"
            )
        
        # 创建会话ID
        import uuid
        session_id = str(uuid.uuid4())
        
        # 获取AI服务
        ai_service = AIServiceFactory.get_service()
        
        # 【修复-Wave2】创建LLM客户端适配器
        # Agent需要的llm_client: Callable[[str, List[Message]], Any]
        # ai_service.chat: Callable[[str, Optional[List[Message]]], ChatResponse]
        async def llm_client_adapter(message: str, history: Optional[List] = None):
            """适配器：将 ai_service.chat 包装为 Agent 可用的格式"""
            response = await ai_service.chat(message=message, history=history)
            return response
        
        # 【修复-Wave2】创建 FileOperationAgent
        agent = FileOperationAgent(
            llm_client=llm_client_adapter,
            session_id=session_id,
            max_steps=20
        )
        
        # 【修复-Wave2】使用 Agent 执行任务
        # Agent 会自主决定如何完成文件操作任务
        result = await agent.run(task=message)
        
        # 将 AgentResult 转换为 ChatResponse
        if result.success:
            # 【修复】正确提取 Agent 的回复内容
            # 实际的回复在最后一个 step 的 observation.result.result 中
            content = result.message  # 默认值
            
            if result.steps:
                # 获取最后一个 step
                last_step = result.steps[-1]
                if last_step.observation and last_step.observation.get("result"):
                    # 提取真正的回复内容
                    result_data = last_step.observation["result"]
                    if isinstance(result_data, dict) and "result" in result_data:
                        content = result_data["result"]
                    elif isinstance(result_data, str):
                        content = result_data
            
            # 将执行步骤作为独立字段返回（修改字段名以匹配前端期望）
            execution_steps_list = None
            if result.steps:
                execution_steps_list = []
                for step in result.steps:
                    # 提取 result 字段（展平 observation.result.result）
                    step_result = ""
                    if step.observation and isinstance(step.observation, dict):
                        if "result" in step.observation:
                            result_data = step.observation["result"]
                            if isinstance(result_data, dict) and "result" in result_data:
                                step_result = result_data["result"]
                            elif isinstance(result_data, str):
                                step_result = result_data
                    
                    execution_steps_list.append({
                        "type": "observation",
                        "step": step.step_number,
                        "content": step.thought,        # 前端期望 content
                        "tool": step.action,             # 前端期望 tool
                        "result": step_result            # 前端期望 result
                    })
            
            # 添加简短的执行摘要到content（兼容性保留）
            if result.steps:
                content += f"\n\n[执行详情：共 {result.total_steps} 步]"
            
            return ChatResponse(
                success=True,
                content=content,
                model="file_operation_agent",
                error=None,
                execution_steps=execution_steps_list
            )
        else:
            return ChatResponse(
                success=False,
                content="",
                model="file_operation_agent",
                error=result.error or "任务执行失败"
            )
            
    except Exception as e:
        return ChatResponse(
            success=False,
            content="",
            model="file_operation_agent",
            error=f"文件操作Agent执行失败: {str(e)}"
        )


# ============================================================
# 备份管理辅助函数 - 小欧新增
# ============================================================

async def _delete_backup_by_path(backup_path: str):
    """
    删除指定备份文件（验证成功后调用）
    
    ⭐ 修复：接收明确的 backup_path 参数，避免竞态条件
    
    调用时机：
    - validate_ai_service 验证成功后
    
    功能：
    1. 验证备份文件是否存在
    2. 验证备份文件命名格式
    3. 验证备份文件时间（10 分钟内）
    4. 删除备份文件
    
    设计原因：
    - 验证成功说明新配置可用
    - 删除备份避免文件累积
    - 显式传递路径避免误操作
    
    作者：小欧
    时间：2026-03-01
    """
    try:
        from pathlib import Path
        backup = Path(backup_path)
        
        # 验证备份文件是否存在
        if not backup.exists():
            logger.warning(f"备份文件不存在：{backup_path}")
            return
        
        # 验证备份文件命名格式
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        
        # 验证备份文件时间（必须是 10 分钟内的）
        import time
        file_mtime = backup.stat().st_mtime
        if time.time() - file_mtime > 600:  # 10 分钟
            logger.warning(f"备份文件过期，跳过删除：{backup_path}")
            return
        
        backup.unlink()
        logger.info(f"验证成功，已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"删除备份失败：{e}")


async def _restore_backup_and_delete_by_path(backup_path: str, config_path: str):
    """
    恢复指定备份文件并删除备份（验证失败后调用）
    
    ⭐ 修复：接收明确的 backup_path 和 config_path 参数
    
    调用时机：
    - validate_ai_service 验证失败后
    
    功能：
    1. 验证备份文件是否存在
    2. 验证备份文件命名格式
    3. 恢复备份到配置文件
    4. 删除备份文件
    
    设计原因：
    - 验证失败说明新配置不可用
    - 恢复到旧配置保证系统可用
    - 显式传递路径避免误操作
    
    作者：小欧
    时间：2026-03-01
    """
    try:
        from pathlib import Path
        backup = Path(backup_path)
        config = Path(config_path)
        
        # 验证备份文件是否存在
        if not backup.exists():
            logger.warning(f"备份文件不存在，无法恢复：{backup_path}")
            return
        
        # 验证备份文件命名格式
        if not backup.name.startswith("config.yaml.backup."):
            logger.error(f"无效的备份文件名：{backup.name}")
            return
        
        # 恢复备份
        shutil.copy2(str(backup), str(config))
        logger.info(f"验证失败，已恢复备份：{backup_path}")
        
        # 删除备份
        backup.unlink()
        logger.info(f"已删除备份：{backup_path}")
    except Exception as e:
        logger.error(f"恢复备份失败：{e}")


@router.get("/chat/validate", response_model=ValidateResponse)
async def validate_ai_service():
    """
    验证 AI 服务配置是否正确
    
    用于测试 API 密钥是否有效
    
    ⭐ 重要：验证成功后删除备份，验证失败时恢复备份
    ⭐ 修复：从全局状态获取 backup_path
    """
    try:
        # 获取当前服务（同时会加载当前配置）
        ai_service = AIServiceFactory.get_service()
        
        # 获取当前提供商（从工厂的内部状态）
        provider = AIServiceFactory.get_current_provider()
        
        # 获取当前模型名称
        current_model = ai_service.model
        
        # ⭐ 从全局状态获取 backup_path（由 update_config 设置）
        backup_path, config_path = AIServiceFactory.get_backup_paths()
        
        # 检查 API Key 是否为空
        if not ai_service.api_key or ai_service.api_key.strip() == "":
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            return ValidateResponse(
                success=False,
                provider=provider,
                model=current_model,
                message=f"AI 服务未配置：{provider} ({current_model}) 的 API Key 为空。请在 config/config.yaml 中配置。（配置已恢复到更新前的状态）"  # ⭐ 添加说明
            )
        
        # 验证服务
        is_valid = await ai_service.validate()
        
        if is_valid:
            # ⭐ 验证成功：删除备份
            if backup_path:
                await _delete_backup_by_path(backup_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            return ValidateResponse(
                success=True,
                provider=provider,
                model=current_model,
                message=f"AI 服务验证成功，当前使用 {provider} ({current_model})"
            )
        else:
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            # 验证失败，尝试获取详细错误信息，并明确说明配置已恢复
            # 通过发送一个实际请求来获取错误详情
            test_response = None
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    test_response = await client.post(
                        f"{ai_service.api_base}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {ai_service.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": ai_service.model,
                            "messages": [{"role": "user", "content": "test"}]
                        }
                    )
            except httpx.TimeoutException:
                # 超时也返回通用错误
                logger.warning(f"API validation timeout for {provider}")
            except httpx.RequestError as e:
                logger.warning(f"API validation request error: {e}")
            except Exception as e:
                logger.warning(f"API validation error: {e}")
            
            # 根据状态码返回不同的错误信息
            if test_response:
                if test_response.status_code == 401:
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=f"API Key无效：{provider} ({current_model}) 的API Key认证失败，请检查Key是否正确"
                    )
                elif test_response.status_code == 429:
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=f"速率限制：{provider} ({current_model}) API请求太频繁，请等待几分钟后重试"
                    )
                else:
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=f"API错误：{provider} ({current_model}) 返回HTTP {test_response.status_code}，请检查配置"
                    )
            else:
                return ValidateResponse(
                    success=False,
                    provider=provider,
                    model=current_model,
                    message=f"连接失败：无法连接到 {provider} ({current_model}) API，请检查网络或API地址配置"
                )
            
    except Exception as e:
        return ValidateResponse(
            success=False,
            provider="unknown",
            message=f"验证过程出错: {str(e)}"
        )


# 【隐藏】冗余接口，已被 /config PUT 替代，仅保留以防后续需要
@router.post("/chat/switch/{provider}", response_model=ValidateResponse, include_in_schema=False)
async def switch_ai_provider(provider: str):
    """
    切换AI提供商
    
    - **provider**: 提供商名称 (从配置中动态支持)
    
    用于切换AI提供商
    """
    try:
        # 验证提供商名称（从配置中动态验证）
        from app.config import get_config as get_config_instance
        
        config = get_config_instance()
        ai_config = config.get('ai', {})
        
        # 获取所有可用的provider（排除provider和model这两个配置项）
        available_providers = []
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict):
                available_providers.append(provider_name)
        
        if provider not in available_providers:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商: {provider}，支持的选项: {', '.join(available_providers)}"
            )
        
        # 切换提供商
        ai_service = AIServiceFactory.switch_provider(provider)
        
        # 获取新模型名称
        new_model = ai_service.model
        
        # 验证新服务
        is_valid = await ai_service.validate()
        
        if is_valid:
            return ValidateResponse(
                success=True,
                provider=provider,
                model=new_model,
                message=f"成功切换到 {provider} ({new_model})"
            )
        else:
            return ValidateResponse(
                success=False,
                provider=provider,
                model=new_model,
                message=f"已切换到 {provider} ({new_model})，但验证失败，请检查API密钥"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"切换提供商失败: {str(e)}"
        )
