"""
LLM 核心模块 - 提供通用的 LLM API 调用能力

包含：
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






from app.constants import (DEFAULT_CONNECT_TIMEOUT, DEFAULT_LLM_TIMEOUT, DEFAULT_POOL_TIMEOUT,
    DEFAULT_PROBE_TIMEOUT, DEFAULT_WRITE_TIMEOUT, ERROR_TYPE_MAP, HTTPX_EXCEPTION_TO_ERROR_KEY,
    LLM_MAX_CONNECTIONS, LLM_MAX_KEEPALIVE, RATE_LIMIT_STATUS_CODES)


def _resolve_exception(e: Exception) -> tuple:
    """解析异常→(用户消息, 错误类型)，复用constants.py已有常量组合查询 — 小健 2026-05-25

    httpx异常通过HTTPX_EXCEPTION_TO_ERROR_KEY映射到error_key，
    httpcore异常共用同名映射（如httpcore.ReadError与httpx.ReadError→"read_error"），
    再通过ERROR_TYPE_MAP[error_key]获取(分类, 用户消息)。
    """
    error_key = HTTPX_EXCEPTION_TO_ERROR_KEY.get(type(e).__name__)
    if error_key and error_key in ERROR_TYPE_MAP:
        _, user_msg = ERROR_TYPE_MAP[error_key]
        return user_msg, error_key
    return f"AI服务调用失败: {type(e).__name__}", "unknown_error"


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


class ChatResponse:
    """聊天响应类 - 非流式响应"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None,
                 reasoning: Optional[str] = None, tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.error = error
        self.success = error is None
        self.reasoning = reasoning or ""
        self.tool_calls = tool_calls or []


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
    
    def __init__(self, api_key: str, model: str, api_base: str, provider: str = "", timeout: int = DEFAULT_LLM_TIMEOUT,
                 max_tokens: int = 4096, temperature: float = 0.7, seed: Optional[int] = None):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        
        try:
            timeout_value = float(timeout) if timeout else float(DEFAULT_LLM_TIMEOUT)
        except (ValueError, TypeError):
            timeout_value = float(DEFAULT_LLM_TIMEOUT)
        self.timeout = int(timeout_value)
        
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=DEFAULT_CONNECT_TIMEOUT,
                read=self.timeout,
                write=DEFAULT_WRITE_TIMEOUT,
                pool=DEFAULT_POOL_TIMEOUT,
            ),
            limits=httpx.Limits(max_connections=LLM_MAX_CONNECTIONS, max_keepalive_connections=LLM_MAX_KEEPALIVE)
        )
        
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None
        self._supports_reasoning: Optional[bool] = None

    async def __call__(self, message: str, history: Optional[List[Dict]] = None) -> "ChatResponse":
        """使BaseAIService可调用，兼容策略层直接调用 llm_client(msg, history) 的约定"""
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
    
    RATE_LIMIT_STATUS_CODES = RATE_LIMIT_STATUS_CODES

    def _is_rate_limit_status(self, status_code: int) -> bool:
        """判断HTTP状态码是否为限流 — 标准HTTP 429 + 非标准限流码 — 小健 2026-05-24"""
        return status_code in self.RATE_LIMIT_STATUS_CODES
    
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
    
    async def _detect_reasoning_support(self) -> bool:
        """通过API探测模型是否支持reasoning_content — 小健 2026-05-24

        发一个简单请求，检查响应message中是否包含reasoning_content字段。
        首次探测后缓存到 _supports_reasoning，不再重复请求。
        """
        if self._supports_reasoning is not None:
            return self._supports_reasoning
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_PROBE_TIMEOUT) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
                )
                if response.status_code == 200:
                    message = response.json().get("choices", [{}])[0].get("message", {})
                    self._supports_reasoning = "reasoning_content" in message
                else:
                    self._supports_reasoning = False
        except Exception as e:
            logger.warning(f"[reasoning探测] 探测失败，默认不支持: {e}")
            self._supports_reasoning = False
        logger.info(f"[reasoning探测] model={self.model}, supports_reasoning={self._supports_reasoning}")
        return self._supports_reasoning

    @staticmethod
    def _fix_thinking_messages(messages: List[Dict], is_thinking: bool) -> List[Dict]:
        """修复thinking模型消息兼容性 — 小健 2026-05-24

        thinking模型(如deepseek-v3/r1)要求assistant消息必须包含
        reasoning_content或tool_calls字段，否则API返回400。

        修复策略：对缺少reasoning_content且无tool_calls的assistant消息，
        将content移入reasoning_content字段，content置空字符串。
        """
        if not is_thinking:
            return messages
        for msg in messages:
            if msg.get("role") == "assistant" and not msg.get("tool_calls"):
                if "reasoning_content" not in msg:
                    content = msg.get("content") or ""
                    msg["reasoning_content"] = content
                    msg["content"] = ""
        return messages

    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        """根据异常类型创建错误StreamChunk — 小健 2026-05-25"""
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown_error":
            import traceback
            logger.error(f"[{_resolve_exception.__name__}] 未知异常: {e}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    def _create_cancelled_chunk(self) -> StreamChunk:
        """创建取消StreamChunk — 小健 2026-05-25"""
        return StreamChunk(content="", model=self.model, is_done=True, stream_error="任务已取消", stream_error_type="cancelled")

    async def _handle_http_error(self, response, log_tag: str = "stream") -> AsyncGenerator[StreamChunk, None]:
        """处理HTTP非200错误响应 — 小健 2026-05-25"""
        try:
            error_body = await response.aread()
            error_text = error_body.decode("utf-8", errors="ignore")
            logger.error(f"[{log_tag}] HTTP {response.status_code} error: {error_text[:500]}")
            try:
                error_json = json.loads(error_text)
                error_msg = error_json.get("error", {}).get("message", "")
                if error_msg:
                    yield StreamChunk(content="", model=self.model, is_done=True,
                                      stream_error=f"API Error: {response.status_code}, {error_text}",
                                      stream_error_type="api_error")
                    return
            except json.JSONDecodeError:
                pass
            yield StreamChunk(content="", model=self.model, is_done=True,
                              stream_error=f"HTTP {response.status_code}: {error_text[:200]}",
                              stream_error_type="http_error")
        except Exception as e:
            logger.error(f"[{log_tag}] 读取错误响应失败: {e}")
            yield StreamChunk(content="", model=self.model, is_done=True,
                              stream_error=f"HTTP {response.status_code} error",
                              stream_error_type="http_error")

    async def _parse_sse_stream(self, response, log_tag: str = "sse") -> AsyncGenerator[StreamChunk, None]:
        """通用SSE解析生成器 — 消除chat_stream/chat_with_tools_stream之间~90%重复 — 小健 2026-05-25

        职责: 从HTTP响应中解析SSE流，yield StreamChunk
        包含: wait_for心跳、取消检查、data:前缀解析、[DONE]处理、choices[0].delta提取
        """
        line_iterator = response.aiter_lines()
        _reasoning_content_total = 0
        _content_total = 0

        while True:
            try:
                line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
            except asyncio.TimeoutError:
                if self._cancelled:
                    yield self._create_cancelled_chunk()
                    return
                continue
            except StopAsyncIteration:
                break

            if self._cancelled:
                yield self._create_cancelled_chunk()
                return

            if not line or not line.strip():
                continue

            if line.startswith("data: "):
                data_str = line[6:]
            elif line.startswith("data:"):
                data_str = line[5:]
            else:
                continue

            if data_str.strip() == "[DONE]":
                logger.info(f"[{log_tag}] 流结束, content_total={_content_total}, reasoning_total={_reasoning_content_total}")
                yield StreamChunk(content="", model=self.model, is_done=True)
                return

            try:
                data = json.loads(data_str)
                choices = data.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "") or ""
                    reasoning_content = delta.get("reasoning_content", "") or ""

                    if content:
                        _content_total += len(content)
                        yield StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False)

                    if reasoning_content:
                        _reasoning_content_total += len(reasoning_content)
                        if _reasoning_content_total == len(reasoning_content):
                            logger.info(f"[{log_tag}] 首次收到reasoning, model={self.model}")
                        yield StreamChunk(content=reasoning_content, model=self.model, is_done=False, is_reasoning=True)
            except json.JSONDecodeError:
                continue

        yield StreamChunk(content="", model=self.model, is_done=True)

    def _build_messages(self, message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
        """构建消息列表 — message为空时直接返回history，否则拼接"""
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
    
    async def chat_stream(self, message: str, history: Optional[List[Dict]] = None) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（流式返回）— 重构为骨架+通用解析+错误处理 小健 2026-05-25"""
        self.reset_cancel()
        messages = self._build_messages(message, history)
        if await self._detect_reasoning_support():
            messages = self._fix_thinking_messages(messages, True)

        try:
            async with self._stream_with_retry(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json_body=self._build_request_body(messages)
            ) as response:
                self._current_response = response
                if self._cancelled:
                    await response.aclose()
                    yield self._create_cancelled_chunk()
                    return
                if response.status_code != 200:
                    async for chunk in self._handle_http_error(response, log_tag="chat_stream"):
                        yield chunk
                    return
                async for chunk in self._parse_sse_stream(response, log_tag="chat_stream"):
                    yield chunk
        except Exception as e:
            yield self._create_stream_error_chunk(e)
        finally:
            self._current_response = None
    
    async def validate(self) -> bool:
        """验证API Key是否有效 - 已废弃，请使用 init_model_select.py 中的接口实现"""
        raise NotImplementedError("validate() 已废弃，请使用 /api/v1/chat/validate 接口")
    
    async def close(self):
        """关闭HTTP客户端"""
        await self.client.aclose()
    
    async def _cancel_or_wait(self, request_task: asyncio.Task) -> Optional[ChatResponse]:
        """心跳循环：1秒间隔检查取消。取消则返回 error ChatResponse — 小沈 2026-05-25"""
        try:
            while not request_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(request_task), timeout=1.0)
                except asyncio.TimeoutError:
                    if self._cancelled:
                        logger.info("[chat_with_tools] 检测到取消，中断请求")
                        request_task.cancel()
                        try:
                            await request_task
                        except asyncio.CancelledError:
                            pass
                        return ChatResponse(content="", model=self.model, provider=self.provider, error="任务已取消")
        except asyncio.CancelledError:
            return ChatResponse(content="", model=self.model, provider=self.provider, error="任务已取消")
        if self._cancelled:
            return ChatResponse(content="", model=self.model, provider=self.provider, error="任务已取消")
        return None

    def _response_or_error(self, content: str = "", error: str = "",
                          tool_calls: Optional[List] = None,
                          reasoning: str = "") -> ChatResponse:
        """统一构建 ChatResponse，消除 error 路径的 6 次构造重复 — 小沈 2026-05-25"""
        return ChatResponse(content=content, model=self.model, provider=self.provider,
                           error=error, tool_calls=tool_calls, reasoning=reasoning)

    async def chat_with_tools(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> ChatResponse:
        """发送对话请求（使用 Function Calling） — 小沈 2026-05-25 重构"""
        self.reset_cancel()
        try:
            messages = self._build_messages(message, history)
            if await self._detect_reasoning_support():
                messages = self._fix_thinking_messages(messages, True)
            request_json = {"model": self.model, "messages": messages}
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice

            logger.info(f"[chat_with_tools] model={self.model}, messages数量={len(messages)}, tools数量={len(tools) if tools else 0}")

            request_task = asyncio.ensure_future(self._post_with_retry(f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json_body=request_json))

            cancel_response = await self._cancel_or_wait(request_task)
            if cancel_response:
                return cancel_response

            response = await request_task
            if response.status_code != 200:
                return self._response_or_error(error=f"API Error: {response.status_code}, {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return self._response_or_error(error="No response from API")

            msg = choices[0].get("message", {})
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                return self._response_or_error(content=json.dumps(tool_calls, ensure_ascii=False), tool_calls=tool_calls)

            content = msg.get("content", "") or ""
            reasoning = msg.get("reasoning", "") or ""
            if not content:
                finish_reason = choices[0].get("finish_reason", "")
                if finish_reason == "tool_calls":
                    return self._response_or_error(error="Failed to parse tool_calls")
                if reasoning:
                    content = reasoning
                    logger.info(f"[chat_with_tools] content为空，使用reasoning作为fallback")

            if content and "<" in content and ">" in content:
                xml_converted = _convert_xml_tool_call_to_json(content)
                if xml_converted:
                    logger.info(f"[chat_with_tools] 检测到XML工具调用格式，已转为JSON: {xml_converted}")
                    return self._response_or_error(content=xml_converted)
            return self._response_or_error(content=content, reasoning=reasoning)

        except Exception as e:
            logger.error(f"[chat_with_tools] Exception: {e}")
            return self._response_or_error(error=f"{type(e).__name__}: {e}")
    
    async def chat_with_tools_stream(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto"
    ) -> AsyncGenerator[StreamChunk, None]:
        """发送对话请求（使用 Function Calling，流式返回）— 重构为骨架+通用解析 小健 2026-05-25"""
        self.reset_cancel()

        try:
            messages = self._build_messages(message, history)
            if await self._detect_reasoning_support():
                messages = self._fix_thinking_messages(messages, True)

            request_json = {"model": self.model, "messages": messages, "stream": True}
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice

            async with self._stream_with_retry(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json_body=request_json
            ) as response:
                self._current_response = response
                if self._cancelled:
                    await response.aclose()
                    yield self._create_cancelled_chunk()
                    return
                if response.status_code != 200:
                    yield StreamChunk(content="", model=self.model, is_done=True,
                                      stream_error=f"API Error: {response.status_code}")
                    return
                async for chunk in self._parse_sse_stream(response, log_tag="chat_with_tools_stream"):
                    yield chunk
        except Exception as e:
            yield self._create_stream_error_chunk(e)
        finally:
            self._current_response = None


