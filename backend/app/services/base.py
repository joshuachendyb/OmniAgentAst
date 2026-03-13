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

# 使用统一的日志配置
from app.utils.logger import logger


class Message:
    """消息类"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    """聊天响应类"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None):
        self.content = content
        self.model = model
        self.provider = provider  # 新增
        self.error = error
        self.success = error is None


class StreamChunk:
    """流式响应片段 - 小沈代修改【修复问题 7】"""
    def __init__(self, content: str, model: str, is_done: bool = False, 
                 error: Optional[str] = None, error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False):
        self.content = content
        self.model = model
        self.is_done = is_done
        self.error = error  # 新增：错误信息
        self.error_type = error_type  # 新增：错误类型
        self.reasoning = reasoning  # 新增：思考过程内容
        self.is_reasoning = is_reasoning  # 新增：是否是思考过程


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
    
    def __init__(self, api_key: str, model: str, api_base: str, provider: str = "", timeout: int = 60):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider  # 新增：记录当前使用的provider
        
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
            return ChatResponse(content=full_content, model=self.model, provider=self.provider)
        except Exception as e:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）"""
        
        messages = self._build_messages(message, history)
        
        # 【调试日志】记录发送给LLM的原始信息
        logger.info(f"[LLM Request] model={self.model}, messages数量={len(messages)}, 首条消息={messages[0] if messages else '无'}")
        
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
                    
                    # 【重要修复】API返回的是 "data:{" 而不是 "data: {"
                    # 需要同时处理两种情况
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        continue
                    
                    if data_str.strip() == "[DONE]":
                        yield StreamChunk(content="", model=self.model, is_done=True)
                        return
                    
                    try:
                        data = json.loads(data_str)
                        
                        # 【调试日志】记录LLM返回的原始信息（精简版）
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_val = delta.get("content", "") or ""
                            reasoning_val = delta.get("reasoning_content") or delta.get("reasoning") or ""
                            finish_reason = choices[0].get("finish_reason", "")
                            logger.info(f"[LLM Response] content长度={len(content_val)}, reasoning长度={len(reasoning_val)}, finish_reason={finish_reason}")
                            
                            content = delta.get("content", "")
                            reasoning_content = (
                                delta.get("reasoning_content") or 
                                delta.get("reasoning") or 
                                delta.get("thought") or
                                ""
                            )
                            
                            # 【修复】保持 reasoning_content 和 content 独立，不要混在一起
                            # reasoning_content 是思考过程，content 是正式回答
                            # LongCat 等模型在流式模式下使用 reasoning_content
                            # 不再将 reasoning_content 赋给 content
                            
                            # 注意：不再使用 outer_content，避免重复累积问题
                            
                            finish_reason = choices[0].get("finish_reason", "")
                            
                            # 【小沈修复】分别返回思考过程和最终内容
                            # 统一使用 content 字段，is_reasoning 区分类型
                            if reasoning_content:
                                yield StreamChunk(
                                    content=reasoning_content, 
                                    model=self.model, 
                                    is_done=False,
                                    reasoning="",  # 清空，不冗余
                                    is_reasoning=True
                                )
                            # 再返回实际内容（如果有）
                            if content:
                                yield StreamChunk(
                                    content=content, 
                                    model=self.model, 
                                    is_done=False,
                                    reasoning="",  # 清空，不冗余
                                    is_reasoning=False
                                )
                        else:
                            logger.warning("[AI Response] WARNING: choices is empty!")
                    except json.JSONDecodeError as e:
                        logger.warning(f"[AI Response] JSON解析失败: {e}, data_str={data_str[:200]}")
                        continue
                
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except httpx.TimeoutException:
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                error="请求超时，请重试",
                error_type="timeout_error"
            )
        except httpx.ReadError as e:
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                error=f"读取响应失败: {str(e)[:50]}",
                error_type="read_error"
            )
        except httpx.ConnectError as e:
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                error=f"连接失败: {str(e)[:50]}",
                error_type="connect_error"
            )
        except httpx.ProtocolError as e:
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                error=f"协议错误: {str(e)[:50]}",
                error_type="protocol_error"
            )
        except Exception as e:
            # 【小沈代修改 - 修复问题 7】记录日志，返回用户友好错误
            import traceback
            error_type_name = type(e).__name__
            logger.error(f"[BaseAIService] 流式调用失败：{str(e)}, 异常类型: {error_type_name}, 堆栈: {traceback.format_exc()}")
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                error=f"AI 服务调用失败: {error_type_name}",
                error_type="unknown_error"
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
        except Exception:
            return False
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
