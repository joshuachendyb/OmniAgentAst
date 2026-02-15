"""
OpenCode Zen AI服务实现（备选方案）
"""

import httpx
from typing import List, Optional
from .base import BaseAIService, Message, ChatResponse

class OpenCodeService(BaseAIService):
    """OpenCode Zen AI服务（备选）"""
    
    def __init__(self, api_key: str, model: str = "kimi-k2.5-free", 
                 api_base: str = "https://api.opencode.ai/v1", 
                 timeout: int = 30):
        super().__init__(api_key, model, api_base, timeout)
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        调用OpenCode Zen API进行对话
        注意: 这是备选方案，接口可能需要根据实际API调整
        """
        try:
            # 构建消息列表
            messages = []
            
            if history:
                for msg in history:
                    messages.append(msg.to_dict())
            
            messages.append({"role": "user", "content": message})
            
            # 发送请求
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return ChatResponse(content=content, model=self.model)
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                return ChatResponse(content="", model=self.model, error=error_msg)
                
        except httpx.TimeoutException:
            return ChatResponse(content="", model=self.model, error="请求超时")
        except Exception as e:
            return ChatResponse(content="", model=self.model, error=f"调用失败: {str(e)}")
    
    async def validate(self) -> bool:
        """验证API Key"""
        try:
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": [{"role": "user", "content": "test"}]}
            )
            return response.status_code == 200
        except:
            return False
    
    async def close(self):
        await self.client.aclose()
