"""
AI服务接口抽象基类
支持多模型切换、流式输出
OpenAI兼容API统一实现
"""

import json
import httpx
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
    """
    AI服务抽象基类
    
    实现了OpenAI兼容API的通用逻辑，子类只需：
    1. 调用 super().__init__(api_key, model, api_base, timeout)
    2. 初始化 self.client (httpx.AsyncClient)
    3. 实现 validate() 和 close()
    """
    
    def __init__(self, api_key: str, model: str, api_base: str, timeout: int = 60):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
    
    def _build_messages(self, message: str, history: Optional[List[Message]] = None) -> List[Dict]:
        """构建消息列表"""
        messages = []
        if history:
            for msg in history:
                messages.append(msg.to_dict())
        messages.append({"role": "user", "content": message})
        return messages
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        发送对话请求（一次性返回）
        
        使用流式API实现，收集所有chunk后返回完整响应
        """
        full_content = ""
        async for chunk in self.chat_stream(message, history):
            if chunk.content:
                full_content += chunk.content
            if chunk.is_done:
                break
        
        return ChatResponse(content=full_content, model=self.model)
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """
        发送对话请求（流式返回）- OpenAI兼容API通用实现
        
        适用于所有遵循OpenAI API格式的服务提供商：
        - 智谱GLM (zhipuai)
        - OpenCode
        - DeepSeek
        - Kimi
        - 其他OpenAI兼容服务
        
        Yields:
            StreamChunk: 流式响应片段，逐token返回
        """
        if not self.client:
            yield StreamChunk(content="", model=self.model, is_done=True)
            return
        
        messages = self._build_messages(message, history)
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    yield StreamChunk(content="", model=self.model, is_done=True)
                    return
                
                # 逐行读取SSE响应
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    
                    # SSE格式：data: {...}
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
                        # 检查是否结束
                        if data_str.strip() == "[DONE]":
                            yield StreamChunk(content="", model=self.model, is_done=True)
                            return
                        
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield StreamChunk(content=content, model=self.model, is_done=False)
                        except json.JSONDecodeError:
                            continue
                
                # 流结束
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except httpx.TimeoutException:
            yield StreamChunk(content="", model=self.model, is_done=True)
        except Exception as e:
            print(f"[{self.__class__.__name__}] 流式调用失败: {str(e)}")
            yield StreamChunk(content="", model=self.model, is_done=True)
    
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
