"""
对话API路由
支持智谱GLM和OpenCode模型
集成文件操作Agent
支持SSE流式响应
"""

import httpx
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.services import AIServiceFactory
from app.services.file_operations.tools import get_file_tools
from app.services.file_operations.agent import FileOperationAgent
from app.services.shell_security import check_command_safety
from app.utils.logger import logger
from pathlib import Path
import shutil

# Provider 显示名称映射
PROVIDER_DISPLAY_NAMES = {
    "longcat": "LongCat",
    "opencode": "OpenCode",
    "zhipuai": "智谱 GLM"
}

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
    return f"data: {json.dumps(response)}\\n\\n"


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
            return True, f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\\n\\n"
    return False, ""


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
    return f"data: {json.dumps(response)}\\n\\n"

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
    
    # 【前端小新代修改】优先使用前端传递的task_id，没有才自己生成
    task_id = request.task_id if request.task_id else str(uuid.uuid4())
    
    async def generate():
        """生成SSE流，支持中断"""
        # 注册任务
        async with running_tasks_lock:
            running_tasks[task_id] = {
                "status": "running", 
                "cancelled": False,
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
        
        # 【前端小新代修改】在流式响应开始时发送start事件，返回display_name、provider、model、task_id
        display_name = f"{PROVIDER_DISPLAY_NAMES.get(ai_service.provider, ai_service.provider)} ({ai_service.model})"
        yield f"data: {json.dumps({
            'type': 'start',
            'display_name': display_name,
            'provider': ai_service.provider,
            'model': ai_service.model,
            'task_id': task_id
        })}\n\n"
        
        try:
            # 获取最后一条用户消息
            last_message = request.messages[-1].content if request.messages else ""
            
            # 1. 发送思考 - 正在分析任务
            yield f"data: {json.dumps({'type': 'thought', 'content': '正在分析任务...'})}\n\n"
            await asyncio.sleep(0.3)
            
            # 【小沈代修改 - 修复问题 5】统一中断检查
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            # 【小沈代修改 - 修复问题 5】统一中断检查
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            # 【小沈代修改 - 修复问题 5】统一中断检查
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            # 【小沈代修改 - 修复问题 5】统一中断检查
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            # 【小沈代修改 - 修复问题 5】统一中断检查
            is_interrupted, interrupt_msg = await check_and_yield_if_interrupted(task_id, running_tasks, running_tasks_lock)
            if is_interrupted:
                yield interrupt_msg
                return
            
            # 检测文件操作意图
            is_file_op, _, confidence = detect_file_operation_intent(last_message)
            
            if is_file_op and confidence >= 0.3:
                # 文件操作：逐步推送执行步骤
                yield f"data: {json.dumps({'type': 'action', 'step': 1, 'content': '检测到文件操作意图，开始执行...'})}\n\n"
                await asyncio.sleep(0.3)
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        yield f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
                        return
                
                # 安全检测
                is_safe, risk = check_command_safety(last_message)
                if not is_safe:
                    yield f"data: {json.dumps({'type': 'error', 'content': f'危险操作需确认: {risk}'})}\n\n"
                    return
                
                yield f"data: {json.dumps({'type': 'observation', 'step': 1, 'content': '安全检测通过'})}\n\n"
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
                
                yield f"data: {json.dumps({'type': 'action', 'step': 2, 'content': '执行文件操作...'})}\n\n"
                
                # 流式执行（每步检查中断）
                try:
                    result = await agent.run(last_message)
                    
                    # 推送执行步骤详情
                    if hasattr(result, 'steps') and result.steps:
                        for i, step in enumerate(result.steps, 1):
                            # 每步检查是否被中断
                            async with running_tasks_lock:
                                if running_tasks.get(task_id, {}).get("cancelled", False):
                                    yield f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
                                    break
                            
                            # Step是对象，使用属性访问
                            step_thought = getattr(step, 'thought', '')
                            step_action = getattr(step, 'action', '')
                            step_observation = getattr(step, 'observation', '')
                            
                            yield f"data: {json.dumps({
                                'type': 'observation',
                                'step': i + 2,
                                'thought': step_thought,
                                'action': step_action,
                                'observation': step_observation
                            })}\n\n"
                            await asyncio.sleep(0.5)
                    
                    # 检查是否被中断
                    async with running_tasks_lock:
                        if running_tasks.get(task_id, {}).get("cancelled", False):
                            yield f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
                        else:
                            # 发送最终结果
                            if result.success:
                                result_content = getattr(result, 'content', '')
                                display_name = f"{PROVIDER_DISPLAY_NAMES.get(ai_service.provider, ai_service.provider)} ({ai_service.model})"
                                yield create_final_response(
                                    content=result_content,
                                    model=ai_service.model,
                                    provider=ai_service.provider,
                                    display_name=display_name
                                )
                            else:
                                result_error = getattr(result, 'error', '执行失败')
                                display_name = f"{PROVIDER_DISPLAY_NAMES.get(ai_service.provider, ai_service.provider)} ({ai_service.model})"
                                yield f"data: {json.dumps({'type': 'error', 'content': result_error, 'model': ai_service.model, 'display_name': display_name, 'provider': ai_service.provider})}\n\n"
                            
                except Exception as e:
                    # 【小沈代修改 - 修复问题 4】统一错误处理格式，记录日志
                    logger.error(f"文件操作执行出错：task_id={task_id}, error={e}", exc_info=True)
                    yield create_error_response(
                        error_type="file_operation_error",
                        content="文件操作执行失败"
                    )
            else:
                # 普通对话：调用AI服务（流式）
                yield f"data: {json.dumps({'type': 'action', 'step': 1, 'content': '正在调用AI服务...'})}\n\n"
                await asyncio.sleep(0.3)
                
                # 检查是否被中断
                async with running_tasks_lock:
                    if running_tasks.get(task_id, {}).get("cancelled", False):
                        yield f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
                        return
                
                ai_service = AIServiceFactory.get_service()
                from app.services.base import Message
                history = []
                if len(request.messages) > 1:
                    for msg in request.messages[:-1]:
                        history.append(Message(role=msg.role, content=msg.content))
                # 【修复-小沈】使用流式API，逐token返回
                full_content = ""
                async for chunk in ai_service.chat_stream(
                    message=last_message,
                    history=history
                ):
                    # 检查是否被中断
                    async with running_tasks_lock:
                        if running_tasks.get(task_id, {}).get("cancelled", False):
                            yield f"data: {json.dumps({'type': 'interrupted', 'content': '任务已被中断'})}\n\n"
                            return
                    
                    if chunk.content:
                        full_content += chunk.content
                        # 逐token发送到前端，【新增】添加provider字段作为兜底
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.content, 'model': chunk.model, 'provider': ai_service.provider})}\n\n"
                    
                    if chunk.is_done:
                        break
                    # 发送最终结果，【新增】添加provider字段作为兜底
                yield f"data: {json.dumps({'type': 'final', 'content': full_content, 'model': ai_service.model, 'provider': ai_service.provider})}\n\n"
                        
        except asyncio.CancelledError:
            # 客户端断开连接，任务被中断
            async with running_tasks_lock:
                running_tasks[task_id] = {"status": "cancelled", "cancelled": True}
            yield f"data: {json.dumps({'type': 'interrupted', 'content': '客户端断开连接，任务中断'})}\n\n"
            
        except Exception as e:
            # 【小沈代修改 - 统一错误处理】使用 get_user_friendly_error 和 create_error_response
            logger.error(f"流式响应异常：task_id={task_id}, error={e}", exc_info=True)
            error_type, error_message = get_user_friendly_error(e)
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
            # 构建详细响应
            content = result.message
            
            # 【修复】将执行步骤作为独立字段返回，而不是拼接到content中
            execution_steps_list = None
            if result.steps:
                execution_steps_list = []
                for step in result.steps:
                    execution_steps_list.append({
                        "step": step.step_number,
                        "thought": step.thought,
                        "action": step.action,
                        "action_input": step.action_input,
                        "observation": step.observation
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
                message=f"AI 服务未配置：{provider} ({current_model}) 的 API Key 为空。请在 config/config.yaml 中配置。"
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
            # 验证失败，尝试获取详细错误信息
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


@router.post("/chat/switch/{provider}", response_model=ValidateResponse)
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
