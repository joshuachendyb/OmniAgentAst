"""
AI服务通用实现
支持所有OpenAI兼容API - 一个类，无限provider支持

使用方式：
1. 只需在 config.yaml 配置 api_base、model、api_key
2. 新增provider无需修改任何代码
"""

import json
import httpx
from typing import List, Dict, Optional, AsyncGenerator


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


class BaseAIService:
    """
    通用AI服务 - 一个类支持所有OpenAI兼容API
    
    适用于所有遵循OpenAI API格式的服务提供商：
    - 智谱GLM (zhipuai)
    - OpenCode
    - DeepSeek
    - Kimi
    - 月之暗面 (moonshot)
    - 通义千问 (qwen)
    - 无限可能...
    
    新增provider只需在配置文件中添加配置，零代码修改！
    """
    
    def __init__(self, api_key: str, model: str, api_base: str, timeout: int = 60):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        
        # 安全转换 timeout，处理非法字符串、None、空值等情况
        try:
            timeout_value = float(timeout) if timeout else 60.0
        except (ValueError, TypeError):
            timeout_value = 60.0
        self.timeout = int(timeout_value)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_value, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    def _build_messages(self, message: str, history: Optional[List[Message]] = None) -> List[Dict]:
        """构建消息列表"""
        messages = []
        if history:
            for msg in history:
                messages.append(msg.to_dict())
        messages.append({"role": "user", "content": message})
        return messages
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """发送对话请求（一次性返回）"""
        try:
            full_content = ""
            async for chunk in self.chat_stream(message, history):
                if chunk.content:
                    full_content += chunk.content
                if chunk.is_done:
                    break
            return ChatResponse(content=full_content, model=self.model)
        except Exception as e:
            return ChatResponse(content="", model=self.model, error=str(e))
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）"""
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
                
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        
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
                
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except httpx.TimeoutException:
            yield StreamChunk(content="", model=self.model, is_done=True)
        except Exception as e:
            print(f"[BaseAIService] 流式调用失败: {str(e)}")
            yield StreamChunk(content="", model=self.model, is_done=True)
    
    async def validate(self) -> bool:
        """验证API Key是否有效"""
        try:
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}]
                }
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
