"""
智谱AI服务实现

继承基类，只需初始化客户端和实现 validate/close
"""

import httpx
from typing import List, Optional
from .base import BaseAIService, Message, ChatResponse
from app.utils.logger import api_logger

class ZhipuAIService(BaseAIService):
    """智谱AI服务"""
    
    def __init__(self, api_key: str, model: str = "glm-4.7-flash", 
                 api_base: str = "https://open.bigmodel.cn/api/paas/v4", 
                 timeout: int = 60):
        super().__init__(api_key, model, api_base, timeout)
        # 初始化HTTP客户端
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
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
        except:
            return False
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
