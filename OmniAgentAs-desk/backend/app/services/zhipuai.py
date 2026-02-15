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
            print(f"[ZhipuAI] 开始请求: model={self.model}, message_len={len(message)}")
            
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
            
            print(f"[ZhipuAI] 发送请求到: {self.api_base}/chat/completions")
            
            # 发送请求
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key[:10]}...",
                    "Content-Type": "application/json"
                },
                json=request_data
            )
            
            print(f"[ZhipuAI] 收到响应: status={response.status_code}")
            
            # 检查响应
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"[ZhipuAI] 请求成功: content_len={len(content)}")
                return ChatResponse(
                    content=content,
                    model=self.model
                )
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", error_msg)
                    print(f"[ZhipuAI] API错误: {error_msg}")
                except Exception as e:
                    print(f"[ZhipuAI] 解析错误响应失败: {e}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    error=error_msg
                )
                
        except httpx.TimeoutException as e:
            print(f"[ZhipuAI] 请求超时: {e}")
            return ChatResponse(
                content="",
                model=self.model,
                error="请求超时：智谱API在60秒内未响应。可能原因：1) 网络延迟 2) 智谱服务器繁忙 3) 账户被限速。请稍后重试或切换到OpenCode"
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
