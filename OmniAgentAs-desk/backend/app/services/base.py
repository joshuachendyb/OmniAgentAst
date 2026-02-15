"""
AI服务接口抽象基类
支持多模型切换
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

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
        发送对话请求
        
        Args:
            message: 用户消息
            history: 历史消息列表
            
        Returns:
            ChatResponse: 响应对象
        """
        pass
    
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
