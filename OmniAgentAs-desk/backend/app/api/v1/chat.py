"""
对话API路由
支持智谱GLM和OpenCode模型
集成文件操作Agent
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.services import AIServiceFactory
from app.services.file_operations.tools import get_file_tools
from app.services.file_operations.agent import FileOperationAgent
from app.services.shell_security import check_command_safety
from app.utils.logger import logger

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

class ChatResponse(BaseModel):
    """聊天响应"""
    success: bool = Field(..., description="是否成功")
    content: str = Field(default="", description="回复内容")
    model: str = Field(default="", description="使用的模型")
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
        # 获取最后一条用户消息
        last_message = request.messages[-1].content if request.messages else ""
        
        # 【修复】检测文件操作意图（返回3个值：是否文件操作、操作类型、置信度）
        is_file_op, op_type, confidence = detect_file_operation_intent(last_message)
        
        # 【修复】只有在置信度足够高时才执行文件操作
        if is_file_op and confidence >= 0.3:
            # 【修复】文件操作路由到 FileTools
            return await handle_file_operation(last_message, op_type)
        
        # 【修复】非文件操作，正常调用AI服务
        # 获取AI服务实例
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
            error=response.error
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"对话请求失败: {str(e)}"
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


@router.get("/chat/validate", response_model=ValidateResponse)
async def validate_ai_service():
    """
    验证AI服务配置是否正确
    
    用于测试API密钥是否有效
    """
    try:
        # 获取当前服务（同时会加载当前配置）
        ai_service = AIServiceFactory.get_service()
        
        # 获取当前提供商（从工厂的内部状态）
        provider = AIServiceFactory.get_current_provider()
        
        # 获取当前模型名称
        current_model = ai_service.model
        
        # 检查API Key是否为空
        if not ai_service.api_key or ai_service.api_key.strip() == "":
            return ValidateResponse(
                success=False,
                provider=provider,
                model=current_model,
                message=f"AI服务未配置：{provider} ({current_model}) 的API Key为空。请在 config/config.yaml 中配置。"
            )
        
        # 验证服务
        is_valid = await ai_service.validate()
        
        if is_valid:
            return ValidateResponse(
                success=True,
                provider=provider,
                model=current_model,
                message=f"AI服务验证成功，当前使用 {provider} ({current_model})"
            )
        else:
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
    
    - **provider**: 提供商名称 (zhipuai | opencode)
    
    用于在智谱和OpenCode之间切换
    """
    try:
        # 验证提供商名称
        if provider not in ["zhipuai", "opencode"]:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的提供商: {provider}，支持的选项: zhipuai, opencode"
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
