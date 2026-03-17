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
from app.api.v1.intent_detector import detect_file_operation_intent  # 【小沈提取独立文件 2026-03-17】
from app.utils.logger import logger
from app.utils.display_name_cache import cache_display_name  # ⭐ 【小沈添加 2026-03-03】
from app.utils.retry_controller import RetryController  # 【小沈-2026-03-14添加】统一的空闲超时和重试控制器
from app.utils.idle_timeout import IdleTimeoutIterator, IdleTimeoutError  # 【小沈-2026-03-14添加】通用的空闲超时异步迭代器
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
                        "thought": step.thought,        # 前端期望 thought
                        "action": step.action,             # 前端期望 action
                        "result": step_result,            # 前端期望 result
                        "observation": step.observation   # 前端期望 observation 对象
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

