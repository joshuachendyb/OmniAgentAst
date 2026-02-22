"""
智谱AI服务实现
支持流式输出
"""

import httpx
import json
from typing import List, Optional, AsyncGenerator
from .base import BaseAIService, Message, ChatResponse, StreamChunk
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
        调用智谱GLM API进行对话（一次性返回）
        """
        # 记录请求开始时间，获取request_id
        history_count = len(history) if history else 0
        request_id = api_logger.log_request_start("zhipuai", self.model, len(message), history_count)
        
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
                elapsed_time = api_logger.log_response_with_time(
                    request_id, "zhipuai", response.status_code, len(content)
                )
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
                api_logger.log_response_with_time(
                    request_id, "zhipuai", response.status_code, error=error_msg
                )
                return ChatResponse(
                    content="",
                    model=self.model,
                    error=error_msg
                )
                
        except httpx.TimeoutException as e:
            api_logger.log_response_with_time(
                request_id, "zhipuai", 0, error="请求超时(60s)"
            )
            return ChatResponse(
                content="",
                model=self.model,
                error="请求超时：智谱API在60秒内未响应。可能原因：1) 网络延迟 2) 智谱服务器繁忙 3) 账户被限速。请稍后重试或切换到OpenCode"
            )
        except Exception as e:
            error_msg = f"调用失败: {str(e)}"
            api_logger.log_response_with_time(
                request_id, "zhipuai", 0, error=error_msg
            )
            return ChatResponse(
                content="",
                model=self.model,
                error=error_msg
            )
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """
        调用智谱GLM API进行对话（流式返回）
        
        Yields:
            StreamChunk: 流式响应片段，逐token返回
        """
        # 构建消息列表
        messages = []
        
        # 添加历史消息
        if history:
            for msg in history:
                messages.append(msg.to_dict())
        
        # 添加当前消息
        messages.append({"role": "user", "content": message})
        
        try:
            # 使用流式API
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
                    "stream": True  # 关键：启用流式输出
                }
            ) as response:
                if response.status_code != 200:
                    error_msg = f"API错误: HTTP {response.status_code}"
                    yield StreamChunk(content="", model=self.model, is_done=True)
                    return
                
                # 逐行读取SSE响应
                async for line in response.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    
                    # SSE格式：data: {...}
                    if line.startswith("data: "):
                        data_str = line[6:]  # 去掉 "data: " 前缀
                        
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
                            # 忽略解析错误
                            continue
                
                # 流结束
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except httpx.TimeoutException:
            yield StreamChunk(content="", model=self.model, is_done=True)
        except Exception as e:
            api_logger.log_error("zhipuai", f"流式调用失败: {str(e)}")
            yield StreamChunk(content="", model=self.model, is_done=True)
    
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
