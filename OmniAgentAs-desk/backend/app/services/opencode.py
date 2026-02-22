"""
OpenCode Zen AI服务实现
支持流式输出
"""

import httpx
import json
from typing import List, Optional, AsyncGenerator
from .base import BaseAIService, Message, ChatResponse, StreamChunk

class OpenCodeService(BaseAIService):
    """OpenCode Zen AI服务"""
    
    def __init__(self, api_key: str, model: str = "kimi-k2.5-free", 
                 api_base: str = "https://api.opencode.ai/v1", 
                 timeout: int = 60):
        super().__init__(api_key, model, api_base, timeout)
        # 增加超时时间到60秒，与智谱GLM保持一致
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
    
    async def chat(self, message: str, history: Optional[List[Message]] = None) -> ChatResponse:
        """
        调用OpenCode Zen API进行对话（一次性返回）
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
                try:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return ChatResponse(content=content, model=self.model)
                except Exception as e:
                    # 打印调试信息
                    print(f"OpenCode响应解析错误: {e}")
                    print(f"响应内容: {response.text[:500]}")
                    return ChatResponse(content="", model=self.model, error=f"响应解析失败: {str(e)}")
            else:
                error_msg = f"API错误: HTTP {response.status_code}"
                print(f"OpenCode错误响应: {response.text[:500]}")
                return ChatResponse(content="", model=self.model, error=error_msg)
                
        except httpx.TimeoutException:
            return ChatResponse(content="", model=self.model, error="请求超时")
        except Exception as e:
            return ChatResponse(content="", model=self.model, error=f"调用失败: {str(e)}")
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """
        调用OpenCode Zen API进行对话（流式返回）
        
        Yields:
            StreamChunk: 流式响应片段，逐token返回
        """
        # 构建消息列表
        messages = []
        
        if history:
            for msg in history:
                messages.append(msg.to_dict())
        
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
            print(f"OpenCode流式调用失败: {str(e)}")
            yield StreamChunk(content="", model=self.model, is_done=True)
    
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
