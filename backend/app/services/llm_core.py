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
import re
import asyncio
import httpx
import httpcore
from typing import List, Dict, Optional, AsyncGenerator, Any

from app.utils.logger import logger


def _convert_xml_tool_call_to_json(content: str) -> Optional[str]:
    """
    通用XML工具调用转JSON
    
    某些模型（如LongCat）返回XML格式工具调用而不是标准OpenAI tool_calls。
    格式: <XXX_tool_call>TOOL_NAME\\n<XXX_arg_key>k</XXX_arg_key>\\n<XXX_arg_value>v</XXX_arg_value>\\n</XXX_tool_call>
    
    此函数通用检测任意前缀的XML工具调用标签并转为标准JSON格式。
    
    Returns:
        转换后的JSON字符串，如果无匹配返回None
    """
    if not content or '<' not in content or '_tool_call>' not in content:
        return None
    
    # 匹配 <任意前缀_tool_call>TOOL_NAME
    m = re.search(r'<(\w+)_tool_call>\s*(\w+)', content)
    if not m:
        return None
    
    prefix = m.group(1)   # 如: longcat
    tool_name = m.group(2)  # 如: search_web
    
    # 匹配 <prefix_arg_key>KEY</prefix_arg_key> 和 <prefix_arg_value>VALUE</prefix_arg_value> 对
    arg_keys = re.findall(rf'<{prefix}_arg_key>([^<]+)</{prefix}_arg_key>', content)
    arg_values = re.findall(rf'<{prefix}_arg_value>([^<]*)</{prefix}_arg_value>', content)
    
    if not arg_keys:
        return None
    
    # 构建标准JSON格式
    tool_params = {}
    for i, key in enumerate(arg_keys):
        val = arg_values[i] if i < len(arg_values) else ''
        tool_params[key.strip()] = val.strip()
    
    result = json.dumps({
        "tool_name": tool_name,
        "tool_params": tool_params
    }, ensure_ascii=False)
    
    return result


class Message:
    """消息类 - 用于构建 LLM 调用时的消息列表"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ChatResponse:
    """聊天响应类 - 非流式响应"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None,
                 reasoning: Optional[str] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.error = error
        self.success = error is None
        self.reasoning = reasoning or ""


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


class _StreamRetryContext:
    """流式请求429重试上下文管理器 — 在传输层统一处理限流"""

    def __init__(self, service, url, headers, json_body, max_retries=3, retry_delay=2.0):
        self.service = service
        self.url = url
        self.headers = headers
        self.json_body = json_body
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._response_ctx = None

    async def __aenter__(self):
        import asyncio
        for attempt in range(self.max_retries):
            self._response_ctx = self.service.client.stream(
                "POST", self.url, headers=self.headers, json=self.json_body
            )
            response = await self._response_ctx.__aenter__()
            if self.service._is_rate_limit_status(response.status_code):
                await self._response_ctx.__aexit__(None, None, None)
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"[429重试] 流式HTTP {response.status_code}, 第{attempt+1}/{self.max_retries}次, {delay:.0f}s后重试")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"[429重试] 流式HTTP {response.status_code}, 持续{self.max_retries}次, 放弃")
                    return response
            return response
        return response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._response_ctx:
            return await self._response_ctx.__aexit__(exc_type, exc_val, exc_tb)


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
    
    def __init__(self, api_key: str, model: str, api_base: str, provider: str = "", timeout: int = 60,
                 max_tokens: int = 4096, temperature: float = 0.7, seed: Optional[int] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        
        try:
            timeout_value = float(timeout) if timeout else 60.0
        except (ValueError, TypeError):
            timeout_value = 60.0
        self.timeout = int(timeout_value)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30.0,  # 【2026-05-14 小健/小沈】httpx 0.26.0→0.28.1后TLS偶发超时，10→30
                read=None,
                write=10.0,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None

    async def __call__(self, message: str, history: Optional[List[Message]] = None) -> "ChatResponse":
        """使BaseAIService可调用，兼容策略层直接调用 llm_client(msg, history) 的约定 - 小沈 2026-05-21"""
        return await self.chat(message, history)

    def _build_request_body(self, messages: List[Dict]) -> Dict:
        """
        构建LLM API请求体

        【改进8 2026-05-01 小沈 小健】添加max_tokens/temperature/seed参数

        Returns:
            包含model/messages/stream/参数的请求体字典
        """
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        # seed可选，None时不传（避免不支持seed的API报错）
        if self.seed is not None:
            body["seed"] = self.seed
        return body
    
    def cancel(self):
        """强制取消当前请求"""
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                # 【修复 2026-04-30 小沈】异步流用aclose()，不能用同步close()
                if hasattr(self._current_response, 'aclose'):
                    import asyncio
                    try:
                        asyncio.get_event_loop().run_until_complete(self._current_response.aclose())
                    except RuntimeError:
                        pass
                else:
                    self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")
    
    def reset_cancel(self):
        """重置取消状态（用于新请求）"""
        self._cancelled = False
        self._current_response = None
    
    def _is_rate_limit_status(self, status_code: int) -> bool:
        """判断HTTP状态码是否为限流"""
        return status_code == 429 or status_code == 1305
    
    async def _post_with_retry(self, url: str, headers: dict, json_body: dict, max_retries: int = 3, retry_delay: float = 2.0):
        """带429指数退避重试的POST请求 — 在传输层统一处理限流"""
        import asyncio
        for attempt in range(max_retries):
            response = await self.client.post(url, headers=headers, json=json_body)
            if self._is_rate_limit_status(response.status_code):
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"[429重试] HTTP {response.status_code}, 第{attempt+1}/{max_retries}次, {delay:.0f}s后重试")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"[429重试] HTTP {response.status_code}, 持续{max_retries}次, 放弃")
            return response
        return response
    
    def _stream_with_retry(self, url: str, headers: dict, json_body: dict, max_retries: int = 3, retry_delay: float = 2.0):
        """带429指数退避重试的流式请求上下文管理器
        
        用法: async with self._stream_with_retry(url, headers, body) as response:
        429时自动重试，非429直接返回response上下文。
        """
        return _StreamRetryContext(self, url, headers, json_body, max_retries, retry_delay)
    
    def _build_messages(self, message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
        """构建消息列表
        
        支持两种模式：
        1. 传统模式：message=用户消息, history=历史 → 拼接 history + [user message]
        2. 直接模式：message="", history=完整messages → 直接返回 history（跳过拼接）
        """
        if not message and history:
            return list(history)
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        return messages
    
    async def chat(self, message: str, history: Optional[List[Dict]] = None) -> ChatResponse:
        """发送对话请求（一次性返回）
        
        【修复 2026-05-05 小沈】添加reasoning_content聚合日志，
        便于诊断thinking模型空响应问题
        """
        try:
            full_content = ""
            full_reasoning = ""
            has_non_reasoning_content = False
            stream_error = None
            async for chunk in self.chat_stream(message, history):
                if chunk.content:
                    if getattr(chunk, "is_reasoning", False):
                        # reasoning_content: 收集到reasoning字段，不合并到content
                        full_reasoning += chunk.content
                    else:
                        # 普通content: 正常收集
                        full_content += chunk.content
                        has_non_reasoning_content = True
                # 【修复 2026-05-05 小沈】记录explicit reasoning字段
                if chunk.reasoning:
                    full_reasoning += chunk.reasoning
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                if chunk.is_done:
                    break
            # 【2026-05-13 小沈】fallback：如果没有非推理内容，用推理内容代替（thinking模型）
            if not has_non_reasoning_content and full_reasoning:
                full_content = full_reasoning
                logger.info(f"[chat] 无普通content，使用reasoning_content作为fallback")
            # 【修复 2026-05-05 小沈】日志：记录聚合结果，便于诊断空响应
            logger.info(
                f"[chat] 聚合结果, model={self.model}, "
                f"full_content长度={len(full_content)}, "
                f"full_reasoning长度={len(full_reasoning)}, "
                f"has_error={stream_error is not None}"
            )
            if stream_error:
                return ChatResponse(content="", model=self.model, provider=self.provider, error=stream_error)
            return ChatResponse(content=full_content, model=self.model, provider=self.provider,
                                reasoning=full_reasoning)
        except Exception as e:
            logger.error(f"[chat] 异常: {e}")
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
    
    async def chat_stream(self, message: str, history: Optional[List[Message]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）"""
        self.reset_cancel()
        messages = self._build_messages(message, history)
        
        logger.info(f"[LLM Request] model={self.model}, messages数量={len(messages)}, 首条消息={messages[0] if messages else '无'}")
        
        try:
            async with self._stream_with_retry(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json_body=self._build_request_body(messages)
            ) as response:
                self._current_response = response
                
                # 【修复】发送请求后立即检查取消标志，避免14秒延迟
                if self._cancelled:
                    logger.info("[chat_stream] 请求发送后立即检测到取消，中断流式响应")
                    # 【修复 2026-04-30 小沈】异步流用aclose()，不能用同步close()
                    await response.aclose()
                    yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                    return
                
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
                                    stream_error=f"API Error: {response.status_code}, {error_text}",  # 【修复 2026-04-10】传递完整错误信息
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
                
                # 【问题2修复】使用wait_for定期检查，每1秒超时检查一次_cancelled标志
                # 而不是等下一个token（可能30秒）
                # 【小沈修复 2026-04-21】修复StreamConsumed错误：使用单个迭代器，避免重复创建
                line_iterator = response.aiter_lines()
                
                # 【修复 2026-05-05 小沈】统计reasoning_content和content的接收情况
                _reasoning_content_total = 0
                _content_total = 0
                
                while True:
                    try:
                        line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # 超时了，检查取消标志
                        if self._cancelled:
                            logger.info("[chat_stream] 检测到取消标志（1秒超时检查），中断流式响应")
                            yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                            return
                        # 没取消，继续等待
                        continue
                    except StopAsyncIteration:
                        break
                    
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
                        # 【修复 2026-05-05 小沈】日志：记录流结束时的统计信息
                        logger.info(
                            f"[chat_stream] 流结束[DONE], model={self.model}, "
                            f"content_total={_content_total}, "
                            f"reasoning_content_total={_reasoning_content_total}"
                        )
                        yield StreamChunk(content="", model=self.model, is_done=True)
                        return
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            # 【修复 2026-05-05 小沈】处理thinking模型的reasoning_content
                            # thinking模型(如big-pickle, LongCat-Flash-Thinking)在思考阶段
                            # 将输出放在reasoning_content中，content为空。若不处理，
                            # chat()聚合后full_content为空，导致"AI服务返回空响应"
                            reasoning_content = delta.get("reasoning_content", "") or ""
                            
                            if content:
                                _content_total += len(content)
                                yield StreamChunk(
                                    content=content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=False
                                )
                            
                            # 【修复 2026-05-05 小沈】reasoning_content也作为content输出
                            # 对于Agent路径(TextStrategy)，reasoning_content中的内容
                            # 才是模型实际的"思考+输出"，必须收集到full_content中
                            if reasoning_content:
                                _reasoning_content_total += len(reasoning_content)
                                # 日志：首次收到reasoning_content时记录原始delta信息
                                if _reasoning_content_total == len(reasoning_content):
                                    logger.info(
                                        f"[chat_stream] 首次收到reasoning_content, "
                                        f"model={self.model}, "
                                        f"delta_keys={list(delta.keys())}, "
                                        f"content={content!r}, "
                                        f"reasoning_content前100={reasoning_content[:100]!r}"
                                    )
                                yield StreamChunk(
                                    content=reasoning_content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=True
                                )
                    except json.JSONDecodeError:
                        continue
                
                # 【修复 2026-05-05 小沈】日志：记录流正常结束时的统计信息
                logger.info(
                    f"[chat_stream] 流正常结束(迭代器耗尽), model={self.model}, "
                    f"content_total={_content_total}, "
                    f"reasoning_content_total={_reasoning_content_total}"
                )
                yield StreamChunk(content="", model=self.model, is_done=True)
                
        except httpx.TimeoutException:
            # 【小沈修复 2026-04-01】细化错误分类：超时
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
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> ChatResponse:
        """发送对话请求（使用 Function Calling）
        
        【小沈优化 2026-04-21】使用后台任务+心跳检查，1秒内响应取消
        """
        self.reset_cancel()
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
            
            # 【小沈优化 2026-04-21】使用后台任务+心跳检查，支持1秒内响应取消
            request_task = asyncio.ensure_future(
                self._post_with_retry(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json_body=request_json
                )
            )
            
            try:
                while not request_task.done():
                    # 等待1秒或直到任务完成
                    try:
                        await asyncio.wait_for(asyncio.shield(request_task), timeout=1.0)
                    except asyncio.TimeoutError:
                        # 检查是否被取消
                        if self._cancelled:
                            logger.info("[chat_with_tools] 检测到取消，中断请求")
                            request_task.cancel()
                            try:
                                await request_task
                            except asyncio.CancelledError:
                                pass
                            return ChatResponse(
                                content="",
                                model=self.model,
                                provider=self.provider,
                                error="任务已取消"
                            )
                        continue
                
                response = await request_task
                
            except asyncio.CancelledError:
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error="任务已取消"
                )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[chat_with_tools] API Error: {response.status_code}, {error_text}")
                return ChatResponse(
                    content="",
                    model=self.model,
                    provider=self.provider,
                    error=f"API Error: {response.status_code}, {error_text}"
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
                
                # 【通用XML工具调用检测 2026-05-13 小沈】某些模型（如LongCat）返回XML格式工具调用
                # 格式: <XXX_tool_call>TOOL_NAME\n<XXX_arg_key>k</XXX_arg_key>\n<XXX_arg_value>v</XXX_arg_value>\n</XXX_tool_call>
                xml_converted = _convert_xml_tool_call_to_json(content)
                if xml_converted:
                    logger.info(f"[chat_with_tools] 检测到XML工具调用格式，已转为JSON: {xml_converted}")
                    return ChatResponse(
                        content=xml_converted,
                        model=self.model,
                        provider=self.provider
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
        history: Optional[List[Dict]] = None,
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
            
            async with self._stream_with_retry(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json_body=request_json
            ) as response:
                self._current_response = response
                
                # 【修复】发送请求后立即检查取消标志，避免延迟
                if self._cancelled:
                    logger.info("[chat_with_tools_stream] 请求发送后立即检测到取消")
                    # 【修复 2026-04-30 小沈】异步流用aclose()
                    await response.aclose()
                    yield StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")
                    return
                
                if response.status_code != 200:
                    yield StreamChunk(
                        content="",
                        model=self.model,
                        is_done=True,
                        stream_error=f"API Error: {response.status_code}"
                    )
                    return
                
                # 【问题2修复】同样使用wait_for定期检查，每1秒超时
                # 【小沈修复 2026-04-21】修复StreamConsumed错误：使用单个迭代器，避免重复创建
                line_iterator = response.aiter_lines()
                
                # 【修复 2026-05-05 小沈】统计reasoning_content和content的接收情况
                _reasoning_content_total = 0
                _content_total = 0
                
                while True:
                    try:
                        line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if self._cancelled:
                            logger.info("[chat_with_tools_stream] Cancelled (1s timeout check)")
                            yield StreamChunk(
                                content="",
                                model=self.model,
                                is_done=True,
                                stream_error="任务已取消",
                                stream_error_type="cancelled"
                            )
                            return
                        continue
                    except StopAsyncIteration:
                        break
                    
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
                        # 【修复 2026-05-05 小沈】日志：记录流结束时的统计信息
                        logger.info(
                            f"[chat_with_tools_stream] 流结束[DONE], model={self.model}, "
                            f"content_total={_content_total}, "
                            f"reasoning_content_total={_reasoning_content_total}"
                        )
                        yield StreamChunk(content="", model=self.model, is_done=True)
                        return
                    
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "") or ""
                            # 【修复 2026-05-05 小沈】处理thinking模型的reasoning_content
                            reasoning_content = delta.get("reasoning_content", "") or ""
                            
                            if content:
                                _content_total += len(content)
                                yield StreamChunk(
                                    content=content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=False
                                )
                            
                            # 【修复 2026-05-05 小沈】reasoning_content也作为content输出
                            if reasoning_content:
                                _reasoning_content_total += len(reasoning_content)
                                if _reasoning_content_total == len(reasoning_content):
                                    logger.info(
                                        f"[chat_with_tools_stream] 首次收到reasoning_content, "
                                        f"model={self.model}, "
                                        f"delta_keys={list(delta.keys())}"
                                    )
                                yield StreamChunk(
                                    content=reasoning_content,
                                    model=self.model,
                                    is_done=False,
                                    is_reasoning=True
                                )
                    except json.JSONDecodeError:
                        continue
                
                # 【修复 2026-05-05 小沈】日志：记录流正常结束时的统计信息
                logger.info(
                    f"[chat_with_tools_stream] 流正常结束(迭代器耗尽), model={self.model}, "
                    f"content_total={_content_total}, "
                    f"reasoning_content_total={_reasoning_content_total}"
                )
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
        history: Optional[List[Dict]] = None,
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
            
            response = await self._post_with_retry(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json_body=request_json
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
