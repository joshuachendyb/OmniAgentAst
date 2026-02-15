"""
智谱AI服务实现
"""

import httpx
import json
from typing import List, Optional
from .base import BaseAIService, Message, ChatResponse
from app.utils.logger import api_logger

class ZhipuAIService(BaseAIService):
    """智谱AI服务"""
    
    def __init__(self, api_key: str, model: str = "glm-4.7-flash", 
                 api_base: str = "https://open.bigmodel.cn/api/paas/v4", 
                 timeout: int = 60):
        super().__init__(api_key, model, api_base, timeout)
        # 增加超时时间到60秒，连接超时10秒，读取超时60秒
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        调用智谱GLM API进行对话
        """
        try:
            history_count = len(history) if history else 0
            api_logger.log_request("zhipuai", self.model, len(message), history_count)
            
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
                api_logger.log_response("zhipuai", response.status_code, len(content))
                return ChatResponse(
                    content=content,
                    model=self.model
                )
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                except Exception as e:
                    api_logger.log_error("zhipuai", f"解析错误响应失败: {e}")
                api_logger.log_response("zhipuai", response.status_code, error=error_msg)
                return ChatResponse(
                    content="",
                    model=self.model,
                    error=error_msg
                )
                
        except httpx.TimeoutException as e:
            api_logger.log_timeout("zhipuai", 60)
            return ChatResponse(
                content="",
                model=self.model,
                error="请求超时：智谱API在60秒内未响应。可能原因：1) 网络延迟 2) 智谱服务器繁忙 3) 账户被限速。请稍后重试或切换到OpenCode"
            )
        except Exception as e:
            error_msg = f"调用失败: {str(e)}"
            api_logger.log_error("zhipuai", error_msg, e)
            return ChatResponse(
                content="",
                model=self.model,
                error=error_msg
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
