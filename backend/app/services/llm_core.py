"""
LLM 核心模块 - 提供通用的 LLM API 调用能力

包含：
- Message: 消息类
- ChatResponse: 非流式响应类
- StreamChunk: 流式响应片段类
- BaseAIService: 通用AI服务（支持所有OpenAI兼容API）

使用方式：
1. 只需在 config.yaml 配置 api_base、model、api_key
2. 新增provider无需修改任何代码

作者：小沈
创建时间：2026-03-27
"""

import json
import httpx
import httpcore
from typing import List, Dict, Optional, AsyncGenerator, Any

from app.utils.logger import logger


class Message:
    """消息类 - 用于构建 LLM 调用时的消息列表"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    """聊天响应类 - 非流式响应"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.error = error
        self.success = error is None


class StreamChunk:
    """流式响应片段"""
    def __init__(self, content: str, model: str, is_done: bool = False, 
                 stream_error: Optional[str] = None, stream_error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False):
        self.content = content
        self.model = model
        self.is_done = is_done
        self.stream_error = stream_error
        self.stream_error_type = stream_error_type
        self.reasoning = reasoning
        self.is_reasoning = is_reasoning


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
        self.provider = provider
        
        try:
            timeout_value = float(timeout) if timeout else 60.0
        except (ValueError, TypeError):
            timeout_value = 60.0
        self.timeout = int(timeout_value)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=None,
                write=10.0,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None
    
    def cancel(self):
        """强制取消当前请求"""
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")
    
    def reset_cancel(self):
        """重置取消状态（用于新请求）"""
        self._cancelled = False
        self._current_response = None
    
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
            stream_error = None
            async for chunk in self.chat_stream(message, history):
                if chunk.content:
                    full_content += chunk.content
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                if chunk.is_done:
                    break
            if stream_error:
                return ChatResponse(content="", model=self.model, provider=self.provider, error=stream_error)
            return ChatResponse(content=full_content, model=self.model, provider=self.provider)
        except Exception as e:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）"""
        self.reset_cancel()
        messages = self._build_messages(message, history)
        
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
                self._current_response = response
                
                if response.status_code != 200:
                    error_body = ""
                    try:
                        error_body = await response.aread()
                        error_text = error_body.decode("utf-8", errors="ignore")
                        logger.error(f"[chat_stream] HTTP {response.status_code} error response: {error_text[:500]}")
                        try:
                            error_json = json.loads(error_text)
                            error_msg = error_json.get("error", {}).get("message", "")
                            if error_msg:
                                yield StreamChunk(content="", model=self.model, is_done=True, 
                                    stream_error=f"API Error: {response.status_code}, {error_msg}",
                                    stream_error_type="api_error")
                                return
                        except json.JSONDecodeError:
                            pass
                        yield StreamChunk(content="", model=self.model, is_done=True,
                            stream_error=f"HTTP {response.status_code}: {error_text[:200]}",
                            stream_error_type="http_error")
                    except Exception as e:
                        logger.error(f"[chat_stream] Failed to read error response: {e}")
                        yield StreamChunk(content="", model=self.model, is_done=True,
                            stream_error=f"HTTP {response.status_code} error",
                            stream_error_type="http_error")
                    return
                
                async for line in response.aiter_lines():
                    if self._cancelled:
                        logger.info("[chat_stream] 检测到取消标志，中断流式响应")
                        yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                        return
                    if not line or line.strip() == "":
                        continue
                    
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
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content_val = delta.get("content", "") or ""
                            reasoning_val = delta.get("reasoning_content") or delta.get("reasoning") or ""
                            finish_reason = choices[0].get("finish_reason", "")
                            # 每个chunk都打印，太频繁，注释掉
                            # logger.info(f"[LLM Response] content长度={len(content_val)}, reasoning长度={len(reasoning_val)}, finish_reason={finish_reason}")
                            
                            content = delta.get("content", "")
                            reasoning_content = (
                                delta.get("reasoning_content") or 
                                delta.get("reasoning") or 
                                delta.get("thought") or
                                ""
                            )
                            
                            finish_reason = choices[0].get("finish_reason", "")
                            
                            if reasoning_content:
                                yield StreamChunk(
                                    content=reasoning_content, 
                                    model=self.model, 
                                    is_done=False,
                                    reasoning="",
                                    is_reasoning=True
                                )
                            if content:
                                yield StreamChunk(
                                    content=content, 
                                    model=self.model, 
                                    is_done=False,
                                    reasoning="",
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
                stream_error="请求超时，请重试",
                stream_error_type="timeout_error"
            )
        except (httpx.ReadError, httpcore.ReadError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="读取响应失败，请重试",
                stream_error_type="read_error"
            )
        except (httpx.ConnectError, httpcore.ConnectError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="连接失败，请检查网络",
                stream_error_type="connect_error"
            )
        except (httpx.ProtocolError, httpcore.ProtocolError, httpx.RemoteProtocolError, httpcore.RemoteProtocolError, httpx.LocalProtocolError, httpcore.LocalProtocolError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="协议错误，请重试",
                stream_error_type="protocol_error"
            )
        except (httpx.ProxyError, httpcore.ProxyError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="代理错误，请检查网络配置",
                stream_error_type="proxy_error"
            )
        except (httpx.WriteError, httpcore.WriteError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="发送请求失败",
                stream_error_type="write_error"
            )
        except (httpx.NetworkError, httpcore.NetworkError):
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error="网络错误，请检查网络连接",
                stream_error_type="network_error"
            )
        except Exception as e:
            import traceback
            error_type_name = type(e).__name__
            logger.error(f"[BaseAIService] 流式调用失败：{str(e)}, 异常类型: {error_type_name}, 堆栈: {traceback.format_exc()}")
            yield StreamChunk(
                content="", 
                model=self.model, 
                is_done=True,
                stream_error=f"AI 服务调用失败: {error_type_name}",
                stream_error_type="unknown_error"
            )
        finally:
            self._current_response = None
    
    async def validate(self) -> bool:
        """验证API Key是否有效 - 已废弃，请使用 init_model_select.py 中的接口实现"""
        raise NotImplementedError("validate() 已废弃，请使用 /api/v1/chat/validate 接口")
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
    
    async def chat_with_tools(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> ChatResponse:
        """发送对话请求（使用 Function Calling）"""
        try:
            messages = self._build_messages(message, history)
            
            request_json = {
                "model": self.model,
                "messages": messages
            }
            
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice
            
            logger.info(
                f"[chat_with_tools] model={self.model}, "
                f"messages数量={len(messages)}, "
                f"tools数量={len(tools) if tools else 0}"
            )
            
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[chat_with_tools] API Error: {response.status_code}, {error_text}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error=f"API Error: {response.status_code}"
                )
            
            data = response.json()
            choices = data.get("choices", [])
            
            if not choices:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="No response from API"
                )
            
            msg = choices[0].get("message", {})
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                return ChatResponse(
                    content=json.dumps(tool_calls, ensure_ascii=False),
                    model=self.model,
                    provider=self.provider
                )
            else:
                content = msg.get("content", "")
                if not content:
                    finish_reason = choices[0].get("finish_reason", "")
                    if finish_reason == "tool_calls":
                        return ChatResponse(
                            content="",
                            model=self.model,
                            provider=self.provider,
                            error="Failed to parse tool_calls"
                        )
                
                return ChatResponse(
                    content=content,
                    model=self.model,
                    provider=self.provider
                )
                
        except Exception as e:
            import traceback
            error_type_name = type(e).__name__
            logger.error(
                f"[chat_with_tools] Exception: {str(e)}, "
                f"type: {error_type_name}, "
                f"stack: {traceback.format_exc()}"
            )
            return ChatResponse(
                content="",
                model=self.model,
                provider=self.provider,
                error=f"{error_type_name}: {str(e)}"
            )
    
    async def chat_with_tools_stream(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（使用 Function Calling，流式返回）"""
        self.reset_cancel()
        
        try:
            messages = self._build_messages(message, history)
            
            request_json = {
                "model": self.model,
                "messages": messages,
                "stream": True
            }
            
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice
            
            logger.info(
                f"[chat_with_tools_stream] model={self.model}, "
                f"tools数量={len(tools) if tools else 0}"
            )
            
            async with self.client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            ) as response:
                self._current_response = response
                
                if response.status_code != 200:
                    yield StreamChunk(
                        content="",
                        model=self.model,
                        is_done=True,
                        stream_error=f"API Error: {response.status_code}"
                    )
                    return
                
                async for line in response.aiter_lines():
                    if self._cancelled:
                        logger.info("[chat_with_tools_stream] Cancelled")
                        yield StreamChunk(
                            content="",
                            model=self.model,
                            is_done=True,
                            stream_error="任务已取消",
                            stream_error_type="cancelled"
                        )
                        return
                    
                    if not line or line.strip() == "":
                        continue
                    
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
                        choices = data.get("choices", [])
                        
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            
                            if content:
                                yield StreamChunk(
                                    content=content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=False
                                )
                    except json.JSONDecodeError:
                        continue
                
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except Exception as e:
            import traceback
            logger.error(f"[chat_with_tools_stream] Error: {e}")
            yield StreamChunk(
                content="",
                model=self.model,
                is_done=True,
                stream_error=str(e)
            )
        finally:
            self._current_response = None
    
    async def chat_with_response_format(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """发送对话请求（使用 Structured Outputs response_format）"""
        try:
            messages = self._build_messages(message, history)
            
            request_json: Dict[str, Any] = {
                "model": self.model,
                "messages": messages
            }
            
            if response_format:
                request_json["response_format"] = response_format
            
            logger.info(
                f"[chat_with_response_format] model={self.model}, "
                f"response_format={'provided' if response_format else 'None'}"
            )
            
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[chat_with_response_format] API Error: {response.status_code}, {error_text}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error=f"API Error: {response.status_code}"
                )
            
            data = response.json()
            choices = data.get("choices", [])
            
            if not choices:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="No response from API"
                )
            
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            
            return ChatResponse(
                content=content,
                model=self.model,
                provider=self.provider
            )
            
        except Exception as e:
            import traceback
            error_type_name = type(e).__name__
            logger.error(
                f"[chat_with_response_format] Exception: {str(e)}, "
                f"type: {error_type_name}, "
                f"stack: {traceback.format_exc()}"
            )
            return ChatResponse(
                content="",
                model=self.model,
                provider=self.provider,
                error=f"{error_type_name}: {str(e)}"
            )
