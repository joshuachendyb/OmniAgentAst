"""
智谱AI服务实现
"""

import httpx
import json
from typing import List, Optional
from .base import BaseAIService, Message, ChatResponse

class ZhipuAIService(BaseAIService):
    """智谱AI服务"""
    
    def __init__(self, api_key: str, model: str = "glm-4.7-flash", 
                 api_base: str = "https://open.bigmodel.cn/api/paas/v4", 
                 timeout: int = 30):
        super().__init__(api_key, model, api_base, timeout)
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        调用智谱GLM API进行对话
        """
        try:
            # 构建消息列表
            messages = []
            
            # 添加历史消息
            if history:
                for msg in history:
                    messages.append(msg.to_dict())
            
            # 添加当前消息
            messages.append({"role": "user", "content": message})
            
            # 构建请求
            request_data = {
                "model": self.model,
                "messages": messages
            }
            
            # 发送请求
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            # 检查响应
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return ChatResponse(
                    content=content,
                    model=self.model
                )
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except:
                    pass
                return ChatResponse(
                    content="",
                    model=self.model,
                    error=error_msg
                )
                
        except httpx.TimeoutException:
            return ChatResponse(
                content="",
                model=self.model,
                error="请求超时，请稍后重试"
            )
        except Exception as e:
            return ChatResponse(
                content="",
                model=self.model,
                error=f"调用失败: {str(e)}"
            )
    
    async def validate(self) -> bool:
        """
        验证API Key是否有效
        """
        try:
            # 发送简单请求验证
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
        except:
            return False
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
