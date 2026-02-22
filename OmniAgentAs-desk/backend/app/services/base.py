"""
AI服务接口抽象基类
支持多模型切换、流式输出
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator

class Message:
    """消息类"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}

class ChatResponse:
    """聊天响应类"""
    def __init__(self, content: str, model: str, error: Optional[str] = None):
        self.content = content
        self.model = model
        self.error = error
        self.success = error is None

class StreamChunk:
    """流式响应片段"""
    def __init__(self, content: str, model: str, is_done: bool = False):
        self.content = content
        self.model = model
        self.is_done = is_done

class BaseAIService(ABC):
    """AI服务抽象基类"""
    
    def __init__(self, api_key: str, model: str, api_base: str, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.timeout = timeout
    
    @abstractmethod
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        发送对话请求（一次性返回）
        
        Args:
            message: 用户消息
            history: 历史消息列表
            
        Returns:
            ChatResponse: 响应对象
        """
        pass
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """
        发送对话请求（流式返回）
        
        Args:
            message: 用户消息
            history: 历史消息列表
            
        Yields:
            StreamChunk: 流式响应片段
        """
        # 默认实现：调用非流式方法，一次性返回
        response = await self.chat(message, history)
        yield StreamChunk(content=response.content, model=response.model, is_done=True)
    
    @abstractmethod
    async def validate(self) -> bool:
        """
        验证服务配置是否正确
        
        Returns:
            bool: 验证是否通过
        """
        pass
    
    @abstractmethod
    async def close(self):
        """
        关闭服务，释放资源
        """
        pass
