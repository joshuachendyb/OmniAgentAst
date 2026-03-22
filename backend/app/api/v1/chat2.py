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
from app.chat_stream.chat_stream_query import chat_stream_query  # 【重构优化】复用 chat_stream_query 模块
from app.chat_stream.incident_handler import check_and_yield_if_interrupted, check_and_yield_if_paused, create_incident_data  # 【重构优化】复用 incident_handler 模块
from app.chat_stream.error_handler import create_error_response, get_user_friendly_error  # 【重构优化】复用 error_handler 模块
from app.chat_stream.chat_helpers import create_final_response  # 【重构优化】复用 chat_helpers 模块
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse  # 【重构优化】复用 SSE 格式化函数
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
        
        # 如果安全检查未通过，直接返回错误
        if not security_check_result.get('is_safe', True):
            risk = security_check_result.get('risk', '未知风险')
            logger.info(f"[Step error] 发送error步骤(安全检测拦截)")
            yield create_error_response(
                error_type="security",
                message=f'危险操作需确认: {risk}',
                code='SECURITY_BLOCKED',
                model=request.model,
                provider=request.provider,
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
            
            # 步骤计数器
            step_counter = 0
            
            def next_step():
                nonlocal step_counter
                step_counter += 1
                return step_counter
            
            # 【重构优化】chat_stream_query 需要的变量
            current_execution_steps: List[Dict] = []  # 执行步骤列表
            current_content: str = ""  # 当前累积内容
            last_is_reasoning: Optional[bool] = None  # 上一个is_reasoning状态
            
            # 【重构优化】stub函数：chat2.py不需要保存到数据库
            async def save_execution_steps_to_db(execution_steps: List[Dict], content: str):
                pass
            
            async def add_step_and_save(step: Dict, content: str):
                pass
            
            # 1. 发送思考
            thought_data = {'type': 'thought', 'step': next_step(), 'thinking_prompt': '正在分析任务...'}
            logger.info(f"[Step thought] 发送thought步骤")
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
                # 文件操作：直接流式执行
                # 创建Agent
                session_id = str(uuid.uuid4())
                ai_service = AIServiceFactory.get_service()
                
                async def llm_client(message, history=None):
                    response = await ai_service.chat(message, history)
                    return type('obj', (object,), {'content': response.content})()
                
                agent = FileOperationAgent(
                    llm_client=llm_client,
                    session_id=session_id
                )
                
                try:
                    # 【Phase4核心修改】使用run_stream异步流式输出
                    async for event in agent.run_stream(last_message):
                        # 每步检查是否被中断
                        async with running_tasks_lock:
                            if running_tasks.get(task_id, {}).get("cancelled", False):
                                interrupted_data = create_incident_data('interrupted', '任务已被中断', step=next_step())
                                logger.info(f"[Step incident] 发送incident步骤(interrupted)")
                                yield f"data: {json.dumps(interrupted_data)}\n\n"
                                break
                        
                        event_type = event.get('type')
                        
                        if event_type == 'thought':
                            # Thought阶段
                            step = next_step()
                            logger.info(f"[Step thought] 发送thought步骤")
                            yield format_thought_sse(
                                step=step,
                                content=event.get('content', ''),
                                reasoning=event.get('reasoning', ''),
                                action_tool=event.get('action_tool', ''),
                                params=event.get('params', {})
                            )

                        elif event_type == 'action_tool':
                            # Action阶段
                            step = next_step()
                            logger.info(f"[Step action_tool] 发送action_tool步骤(执行工具)")
                            yield format_action_tool_sse(
                                step=step,
                                tool_name=event.get('tool_name', ''),
                                tool_params=event.get('tool_params', {}),
                                execution_status=event.get('execution_status', 'success'),
                                summary=event.get('summary', ''),
                                raw_data=event.get('raw_data'),
                                action_retry_count=event.get('action_retry_count', 0)
                            )

                        elif event_type == 'observation':
                            # Observation阶段
                            step = next_step()
                            logger.info(f"[Step observation] 发送observation步骤")
                            yield format_observation_sse(
                                step=step,
                                execution_status=event.get('execution_status', 'success'),
                                summary=event.get('summary', ''),
                                content=event.get('content', ''),
                                reasoning=event.get('reasoning', ''),
                                action_tool=event.get('action_tool', ''),
                                params=event.get('params', {}),
                                is_finished=event.get('is_finished', False),
                                raw_data=event.get('raw_data')
                            )
                        
                        elif event_type == 'final':
                            # 最终结果：使用 create_final_response
                            final_content = event.get('content', '')
                            logger.info(f"[Step final] 发送final步骤")
                            yield create_final_response(
                                content=final_content,
                                model=ai_service.model,
                                provider=ai_service.provider,
                                display_name=display_name
                            )
                            break
                        
                        elif event_type == 'error':
                            logger.info(f"[Step error] 发送error步骤")
                            yield create_error_response(
                                error_type="agent",
                                message=event.get('message', '未知错误'),
                                code='AGENT_ERROR',
                                model=request.model,
                                provider=request.provider,
                                retryable=event.get('retryable', False)
                            )
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
                # 普通对话：调用 chat_stream_query（复用公共逻辑）
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
                    save_execution_steps_to_db=save_execution_steps_to_db,
                    add_step_and_save=add_step_and_save,
                ):
                    yield chunk
                        
        except asyncio.CancelledError:
            # 客户端断开连接，任务被中断
            async with running_tasks_lock:
                running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
            interrupted_data = create_incident_data('interrupted', '客户端断开连接，任务中断')
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
    
    日志记录：
    - 开始时间、provider、model
    - 结束时间、结果、耗时
    """
    from datetime import datetime
    start_time = datetime.now()
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info(f"[检查服务] 开始验证 - 时间: {start_str}")
    
    try:
        # 获取当前服务（同时会加载当前配置）
        ai_service = AIServiceFactory.get_service()
        
        # 获取当前提供商（从工厂的内部状态）
        provider = AIServiceFactory.get_current_provider()
        
        # 获取当前模型名称
        current_model = ai_service.model
        
        logger.info(f"[检查服务] 加载配置完成 - provider: {provider}, model: {current_model}")
        
        # ⭐ 从全局状态获取 backup_path（由 update_config 设置）
        backup_path, config_path = AIServiceFactory.get_backup_paths()
        
        # 检查 API Key 是否为空
        if not ai_service.api_key or ai_service.api_key.strip() == "":
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            error_msg = f"AI 服务未配置：{provider} ({current_model}) 的 API Key 为空"
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(API Key为空), 消息: {error_msg}")
            
            return ValidateResponse(
                success=False,
                provider=provider,
                model=current_model,
                message=error_msg + "。请在 config/config.yaml 中配置。（配置已恢复到更新前的状态）"  # ⭐ 添加说明
            )
        
        # 验证服务
        logger.info(f"[检查服务] 开始调用 API 验证...")
        is_valid = await ai_service.validate()
        
        if is_valid:
            # ⭐ 验证成功：删除备份
            if backup_path:
                await _delete_backup_by_path(backup_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            success_msg = f"AI 服务验证成功，当前使用 {provider} ({current_model})"
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 成功, 消息: {success_msg}")
            
            return ValidateResponse(
                success=True,
                provider=provider,
                model=current_model,
                message=success_msg
            )
        else:
            # ⭐ 验证失败：恢复备份
            if backup_path and config_path:
                await _restore_backup_and_delete_by_path(backup_path, config_path)
            # ⭐ 清除全局状态
            AIServiceFactory.clear_backup_paths()
            
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()
            end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(验证返回False), provider: {provider}, model: {current_model}")
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
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"API Key无效：{provider} ({current_model}) 的API Key认证失败"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP 401), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请检查Key是否正确"
                    )
                elif test_response.status_code == 429:
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"速率限制：{provider} ({current_model}) API请求太频繁"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP 429), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请等待几分钟后重试"
                    )
                else:
                    end_time = datetime.now()
                    elapsed = (end_time - start_time).total_seconds()
                    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                    error_msg = f"API错误：{provider} ({current_model}) 返回HTTP {test_response.status_code}"
                    logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(HTTP {test_response.status_code}), 消息: {error_msg}")
                    
                    return ValidateResponse(
                        success=False,
                        provider=provider,
                        model=current_model,
                        message=error_msg + "，请检查配置"
                    )
            else:
                end_time = datetime.now()
                elapsed = (end_time - start_time).total_seconds()
                end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
                error_msg = f"连接失败：无法连接到 {provider} ({current_model}) API"
                logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(连接失败), 消息: {error_msg}")
                
                return ValidateResponse(
                    success=False,
                    provider=provider,
                    model=current_model,
                    message=error_msg + "，请检查网络或API地址配置"
                )
            
    except Exception as e:
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[检查服务] 结束 - 时间: {end_str}, 耗时: {elapsed:.2f}秒, 结果: 失败(异常), 错误: {str(e)}")
        
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
