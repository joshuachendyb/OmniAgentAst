"""
对话API路由
支持智谱GLM和OpenCode模型
集成文件操作Agent
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from app.services import AIServiceFactory
from app.services.file_operations.tools import get_file_tools

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

class ValidateResponse(BaseModel):
    """验证响应"""
    success: bool = Field(..., description="验证是否通过")
    provider: str = Field(..., description="当前使用的提供商")
    model: str = Field(default="", description="当前使用的模型")
    message: str = Field(default="", description="验证消息")


def detect_file_operation_intent(message: str) -> tuple[bool, str]:
    """
    检测用户消息是否包含文件操作意图
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型)
    """
    message_lower = message.lower()
    
    # 文件读取意图
    read_keywords = ['读取文件', '查看文件', '打开文件', '读文件', '看文件内容', 
                     'read file', 'view file', 'open file', 'show file']
    for keyword in read_keywords:
        if keyword in message_lower:
            return True, "read"
    
    # 文件写入意图
    write_keywords = ['写入文件', '创建文件', '保存文件', '写文件', '修改文件',
                      'write file', 'create file', 'save file', 'update file']
    for keyword in write_keywords:
        if keyword in message_lower:
            return True, "write"
    
    # 目录列表意图
    list_keywords = ['列出目录', '查看目录', '显示文件', '有哪些文件', '文件列表',
                     'list directory', 'show files', 'list files', 'dir']
    for keyword in list_keywords:
        if keyword in message_lower:
            return True, "list"
    
    # 文件删除意图
    delete_keywords = ['删除文件', '移除文件', '删掉文件', '删除目录',
                       'delete file', 'remove file', 'del file']
    for keyword in delete_keywords:
        if keyword in message_lower:
            return True, "delete"
    
    # 文件移动/重命名意图
    move_keywords = ['移动文件', '重命名文件', '改名', '转移文件',
                     'move file', 'rename file', 'mv file']
    for keyword in move_keywords:
        if keyword in message_lower:
            return True, "move"
    
    # 文件搜索意图
    search_keywords = ['搜索文件', '查找文件', '找文件', '搜索内容',
                       'search file', 'find file', 'grep', 'search content']
    for keyword in search_keywords:
        if keyword in message_lower:
            return True, "search"
    
    return False, ""


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
        
        # 【修复】检测文件操作意图
        is_file_op, op_type = detect_file_operation_intent(last_message)
        
        if is_file_op:
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
    
    【修复】将文件操作从AI服务中分离，直接调用FileTools
    避免通过AI服务中转，提高效率和可靠性
    
    Args:
        message: 用户原始消息
        op_type: 操作类型 (read/write/list/delete/move/search)
        
    Returns:
        ChatResponse 格式的响应
    """
    try:
        # 初始化文件工具
        file_tools = get_file_tools()
        
        # 创建会话
        import uuid
        session_id = str(uuid.uuid4())
        file_tools.set_session(session_id)
        
        # 提取文件路径
        file_path = extract_file_path(message)
        
        if not file_path and op_type in ["read", "write", "delete", "move"]:
            return ChatResponse(
                success=False,
                content="",
                model="file_operation",
                error="未能从消息中提取到文件路径，请明确指定文件路径"
            )
        
        # 根据操作类型执行相应操作
        if op_type == "read" and file_path:
            result = await file_tools.read_file(file_path)
            if result["success"]:
                content = f"文件内容 ({result.get('total_lines', 0)} 行):\n```\n{result['content']}\n```"
                if result.get('has_more'):
                    content += f"\n(仅显示 {result.get('start_line', 0)}-{result.get('end_line', 0)} 行，文件还有更多内容)"
                return ChatResponse(
                    success=True,
                    content=content,
                    model="file_operation",
                    error=None
                )
            else:
                return ChatResponse(
                    success=False,
                    content="",
                    model="file_operation",
                    error=f"读取文件失败: {result.get('error', '未知错误')}"
                )
        
        elif op_type == "list":
            # 提取目录路径，默认为当前目录
            dir_path = file_path if file_path else "."
            result = await file_tools.list_directory(dir_path)
            if result["success"]:
                entries = result.get('entries', [])
                if not entries:
                    content = f"目录 '{dir_path}' 为空"
                else:
                    content = f"目录 '{dir_path}' 内容 ({len(entries)} 项):\n"
                    for entry in entries[:20]:  # 最多显示20项
                        type_icon = "📁" if entry["type"] == "directory" else "📄"
                        size_info = f" ({entry['size']} bytes)" if entry.get("size") else ""
                        content += f"{type_icon} {entry['name']}{size_info}\n"
                    if len(entries) > 20:
                        content += f"... 还有 {len(entries) - 20} 项\n"
                return ChatResponse(
                    success=True,
                    content=content,
                    model="file_operation",
                    error=None
                )
            else:
                return ChatResponse(
                    success=False,
                    content="",
                    model="file_operation",
                    error=f"列出目录失败: {result.get('error', '未知错误')}"
                )
        
        elif op_type == "search":
            # 提取搜索模式（简化处理，使用消息中的第一个单词作为模式）
            import re
            words = message.split()
            search_pattern = None
            for word in words:
                if len(word) > 2 and not any(kw in word.lower() for kw in ['搜索', '查找', 'search', 'find']):
                    search_pattern = word.strip('"\'，,.;:')
                    break
            
            if not search_pattern:
                return ChatResponse(
                    success=False,
                    content="",
                    model="file_operation",
                    error="请指定要搜索的内容"
                )
            
            search_path = file_path if file_path else "."
            result = await file_tools.search_files(
                pattern=search_pattern,
                path=search_path
            )
            
            if result["success"]:
                matches = result.get('matches', [])
                if not matches:
                    content = f"在 '{search_path}' 中未找到包含 '{search_pattern}' 的文件"
                else:
                    content = f"搜索 '{search_pattern}' 结果 ({result.get('files_matched', 0)} 个文件，{result.get('total_matches', 0)} 处匹配):\n"
                    for match in matches[:5]:  # 最多显示5个文件
                        content += f"\n📄 {match['file']} ({match['match_count']} 处匹配)\n"
                        for m in match['matches'][:2]:  # 每个文件最多显示2处
                            context = m.get('context', '').replace('\n', ' ')
                            content += f"  ...{context}...\n"
                return ChatResponse(
                    success=True,
                    content=content,
                    model="file_operation",
                    error=None
                )
            else:
                return ChatResponse(
                    success=False,
                    content="",
                    model="file_operation",
                    error=f"搜索失败: {result.get('error', '未知错误')}"
                )
        
        elif op_type in ["write", "delete", "move"]:
            # 这些操作需要更复杂的参数解析，暂时返回提示信息
            return ChatResponse(
                success=False,
                content="",
                model="file_operation",
                error=f"{op_type} 操作需要通过专门的API端点执行，当前仅支持查询类操作（read/list/search）"
            )
        
        else:
            return ChatResponse(
                success=False,
                content="",
                model="file_operation",
                error=f"不支持的操作类型: {op_type}"
            )
            
    except Exception as e:
        return ChatResponse(
            success=False,
            content="",
            model="file_operation",
            error=f"文件操作执行失败: {str(e)}"
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
                message=f"AI服务未配置：{provider} ({current_model}) 的API Key为空。请在 backend/config/config.yaml 中配置。"
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
                import httpx
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
            except:
                pass
            
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
