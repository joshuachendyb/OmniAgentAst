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
import asyncio
import httpx
import httpcore
from typing import List, Dict, Optional, AsyncGenerator, Any

from app.utils.logger import logger
from app.utils.retry_engine import RetryEngine, BackoffStrategy, create_rate_limit_retry_engine

from app.services.llm.model_adapters.xml_adapter import convert_xml_tool_call_to_json
from app.services.llm.model_adapters.reasoning import (
    fix_thinking_messages,
    extract_reasoning_from_chunk,
    extract_reasoning_from_message,
)

from app.constants import (DEFAULT_CONNECT_TIMEOUT, DEFAULT_LLM_TIMEOUT, DEFAULT_POOL_TIMEOUT,
    DEFAULT_PROBE_TIMEOUT, DEFAULT_WRITE_TIMEOUT,
    LLM_MAX_CONNECTIONS, LLM_MAX_KEEPALIVE, RATE_LIMIT_STATUS_CODES)

from app.services.llm.core import (
    ChatResponse,
    StreamChunk,
    _StreamRetryContext,
    _resolve_exception,
)
from app.services.llm.stream_parser import (
    parse_sse_stream,
    handle_http_error_stream,
    create_cancelled_chunk,
    create_error_chunk,
)
from app.services.llm.request_builder import (
    build_request_body,
    build_messages,
)


class _RateLimitError(Exception):
    """429限流错误 — 供RetryEngine判断可重试性 — 小沈 2026-05-27"""
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code} rate limit")


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
        构建LLM API请求体 — 委托给request_builder — 小健 2026-05-27
        """
        return build_request_body(
            messages,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            seed=self.seed,
            stream=True
        )
    
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
        """带429指数退避重试的POST请求 — 委托到RetryEngine统一重试引擎 — 小沈 2026-05-27"""
        engine = create_rate_limit_retry_engine(
            max_retries=max_retries,
            backoff_factor=retry_delay,
            is_rate_limit_fn=lambda e: (
                hasattr(e, 'response') and self._is_rate_limit_status(getattr(e, 'status_code', 0))
            ),
        )

        async def _do_post():
            response = await self.client.post(url, headers=headers, json=json_body)
            if self._is_rate_limit_status(response.status_code):
                raise _RateLimitError(response.status_code)
            return response

        try:
            return await engine.execute(_do_post)
        except _RateLimitError as e:
            logger.error(f"[429重试] HTTP {e.status_code}, 持续{max_retries}次, 放弃")
            return e.response if hasattr(e, 'response') else await self.client.post(url, headers=headers, json=json_body)
    
    def _stream_with_retry(self, url: str, headers: dict, json_body: dict, max_retries: int = 3, retry_delay: float = 2.0):
        """带429指数退避重试的流式请求上下文管理器
        
        用法: async with self._stream_with_retry(url, headers, body) as response:
        429时自动重试，非429直接返回response上下文。
        """
        return _StreamRetryContext(self, url, headers, json_body, max_retries, retry_delay)
    
    async def _detect_reasoning_support(self) -> bool:
        """通过CapabilityDetector探测reasoning_content支持 — DRY原则
        
        【重构 2026-05-27 小健】委托给CapabilityDetector统一入口，
        消除与llm_adapter.detect_strategy的双重"发请求→判断→缓存"模式。
        """
        if self._supports_reasoning is not None:
            return self._supports_reasoning
        try:
            from app.services.llm.capability_detector import CapabilityDetector
            detector = CapabilityDetector(self.api_base, self.api_key, self.model)
            self._supports_reasoning = await detector.detect_reasoning_support()
        except Exception as e:
            logger.warning(f"[reasoning探测] 探测失败，默认不支持: {e}")
            self._supports_reasoning = False
        logger.info(f"[reasoning探测] model={self.model}, supports_reasoning={self._supports_reasoning}")
        return self._supports_reasoning

    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        """根据异常类型创建错误StreamChunk — 小健 2026-05-25"""
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown_error":
            import traceback
            logger.error(f"[{_resolve_exception.__name__}] 未知异常: {e}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    def _create_cancelled_chunk(self) -> StreamChunk:
        """创建取消StreamChunk — 小健 2026-05-25"""
        return create_cancelled_chunk(self.model)

    def _build_messages(self, message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
        """构建消息列表 — 委托给request_builder统一入口 — 小健 2026-05-27"""
        return build_messages(message, history)
    
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
            messages = fix_thinking_messages(messages, True)

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
                    async for chunk in handle_http_error_stream(response, self.model, log_tag="chat_stream"):
                        yield chunk
                    return
                async for chunk in parse_sse_stream(response, self.model, lambda: self._cancelled, log_tag="chat_stream"):
                    yield chunk
        except Exception as e:
            yield self._create_stream_error_chunk(e)
        finally:
            self._current_response = None
    
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
                messages = fix_thinking_messages(messages, True)
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
                xml_converted = convert_xml_tool_call_to_json(content)
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
                messages = fix_thinking_messages(messages, True)

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
                    async for chunk in handle_http_error_stream(response, self.model, log_tag="chat_with_tools_stream"):
                        yield chunk
                    return
                async for chunk in parse_sse_stream(response, self.model, lambda: self._cancelled, log_tag="chat_with_tools_stream"):
                    yield chunk
        except Exception as e:
            yield self._create_stream_error_chunk(e)
        finally:
            self._current_response = None


__all__ = [
    "BaseAIService",
    "ChatResponse",
    "StreamChunk",
]
