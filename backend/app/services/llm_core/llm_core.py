"""
LLM 核心模块 — BaseAIService

重构: 删除mixin继承, 统一为request/request_stream/chat + mode参数 - 小沈 2026-06-09
FC-only: tool_calls原生yield,不走JSON roundtrip - 小沈 2026-06-12
"""

import asyncio
import json as _json
import traceback
from typing import List, Dict, Optional, AsyncGenerator, Any

import httpx
from app.utils.logger import logger
from app.utils.json_utils import parse_json
from app.services.llm.core import ChatResponse, StreamChunk, _resolve_exception
from app.services.llm.stream_parser import create_cancelled_chunk
from app.services.llm.client_sdk import create_llm_client
from app.services.llm.model_adapters.reasoning import extract_reasoning_from_chunk
from app.services.task.task_registry import check_cancelled, check_paused
from app.services.agent.agent_utils.message_utils import build_llm_messages
from app.constants import DEFAULT_LLM_TIMEOUT, RATE_LIMIT_STATUS_CODES


def _normalize_tool_params(params: Any) -> Any:
    """递归归一化tool params — 修复LLM双倍编码: 字符串形式的JSON array/object还
    原为真实类型. 在 _json.loads(arguments)之后调用,对后续所有工具无感生效 - 小沈 2026-06-14"""
    if isinstance(params, dict):
        return {k: _normalize_tool_params(v) for k, v in params.items()}
    if isinstance(params, list):
        return [_normalize_tool_params(item) for item in params]
    if isinstance(params, str) and params.strip():
        s = params.strip()
        if s.startswith('[') or s.startswith('{'):
            try:
                parsed = _json.loads(s)
                return _normalize_tool_params(parsed)
            except _json.JSONDecodeError:
                pass
    return params


class BaseAIService:
    """通用AI服务 — request/request_stream/chat — FC-only重构 2026-06-11 小沈"""

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str,
        provider: str = "",
        timeout: int = DEFAULT_LLM_TIMEOUT,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        seed: Optional[int] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        self._llm_sdk = None
        try:
            timeout_value = float(timeout) if timeout else float(DEFAULT_LLM_TIMEOUT)
        except (ValueError, TypeError):
            timeout_value = float(DEFAULT_LLM_TIMEOUT)
        self.timeout = int(timeout_value)
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None
        self.task_id: Optional[str] = None

    def _ensure_client(self):
        if self._llm_sdk is None:
            self._llm_sdk = create_llm_client(
                provider=self.provider or "openai",
                model=self.model,
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
            )

    async def cancel(self):
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                if hasattr(self._current_response, 'aclose'):
                    await self._current_response.aclose()
                else:
                    self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")

    def reset_cancel(self):
        self._cancelled = False
        self._current_response = None

    def set_task_id(self, task_id: str):
        """设置任务ID，用于HTTP阻塞期间的取消检查 — 小沈 2026-06-09"""
        self.task_id = task_id

    async def _check_task_cancelled_or_paused(self) -> bool:
        """检查任务是否被取消或暂停 — 小沈 2026-06-09"""
        if not self.task_id:
            return self._cancelled
        is_cancelled = await check_cancelled(self.task_id)
        is_paused = await check_paused(self.task_id)
        return is_cancelled or is_paused or self._cancelled

    RATE_LIMIT_STATUS_CODES = RATE_LIMIT_STATUS_CODES

    def _is_rate_limit_status(self, status_code: int) -> bool:
        return status_code in self.RATE_LIMIT_STATUS_CODES

    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown_error":
            logger.error(f"[{_resolve_exception.__name__}] 未知异常: {e}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    def _create_cancelled_chunk(self) -> StreamChunk:
        return create_cancelled_chunk(self.model)

    async def request(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        """非流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11"""
        self._ensure_client()
        try:
            response = await self._llm_sdk.request(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                seed=self.seed,
            )
            choices = response.get("choices", [])
            if not choices:
                return ChatResponse(content="", model=self.model, provider=self.provider, error="无响应")

            msg = choices[0].get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", [])

            reasoning = extract_reasoning_from_chunk(msg) or ""

            return ChatResponse(
                content=content,
                model=self.model,
                provider=self.provider,
                tool_calls=tool_calls,
                reasoning=reasoning,
            )
        except Exception as e:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))

    async def request_stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式请求 — FC-only: tool_calls原生yield,不走JSON roundtrip — 小沈 2026-06-12"""
        self.reset_cancel()
        self._ensure_client()

        retry_count = 0
        max_retries = 3

        while retry_count <= max_retries:
            try:
                tool_call_accumulator = {}
                raw_data_buf: list = []
                async for data_str in self._llm_sdk.request_stream(
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    seed=self.seed,
                ):
                    if await self._check_task_cancelled_or_paused():
                        yield self._create_cancelled_chunk()
                        return

                    raw_data_buf.append(data_str)

                    # 跨chunk聚合tool_calls — FC-only: 含id — 小沈 2026-06-11
                    tc_data = self._extract_tool_calls(data_str)
                    for idx, entry in tc_data.items():
                        tool_call_accumulator.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                        if entry.get("id"):
                            tool_call_accumulator[idx]["id"] = entry["id"]
                        if entry.get("name"):
                            tool_call_accumulator[idx]["name"] = entry["name"]
                        if entry.get("arguments"):
                            tool_call_accumulator[idx]["arguments"] += entry["arguments"]

                    chunk = self._parse_sse_data(data_str)
                    if chunk:
                        yield chunk

                # 流结束后，如有聚合的tool_calls，原生结构一次性yield — 小沈 2026-06-12
                complete_raw = "\n".join(raw_data_buf)
                if tool_call_accumulator:
                    tool_calls_list = []
                    for idx in sorted(tool_call_accumulator):
                        tc = tool_call_accumulator[idx]
                        if tc["name"]:
                            try:
                                params = _normalize_tool_params(_json.loads(tc["arguments"])) if tc["arguments"] else {}
                            except _json.JSONDecodeError:
                                params = {}
                            tool_calls_list.append({
                                "tool_name": tc["name"],
                                "tool_params": params,
                                "tool_call_id": tc.get("id"),
                                "tool_calls": [{
                                    "id": tc.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc.get("arguments", "")
                                    }
                                }]
                            })
                    yield StreamChunk(content="", model=self.model, is_done=False,
                                      tool_calls=tool_calls_list, raw_data=complete_raw)

                yield StreamChunk(content="", model=self.model, is_done=True, raw_data=complete_raw)
                return

            except Exception as e:
                if self._should_retry(e) and retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    logger.warning(f"[request_stream] 重试 {retry_count}/{max_retries}, 等待{wait_time}秒, 错误: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    yield self._create_stream_error_chunk(e)
                    return

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式对话便捷方法 — FC-only: 无mode参数 — 小沈 2026-06-11"""
        messages = build_llm_messages(message, history)
        async for chunk in self.request_stream(messages=messages):
            yield chunk

    def _extract_tool_calls(self, data_str: str) -> Dict[int, Dict]:
        """从SSE delta中提取tool_calls增量 — FC-only: 含id捕获 — 小沈 2026-06-11"""
        try:
            data = parse_json(data_str)
            if not data:
                return {}
            choices = data.get("choices", [])
            if not choices:
                return {}
            delta = choices[0].get("delta", {})
            raw_tool_calls = delta.get("tool_calls", [])
            if not raw_tool_calls:
                return {}
            result = {}
            for tc in raw_tool_calls:
                idx = tc.get("index", 0)
                entry = {}
                if tc.get("id"):
                    entry["id"] = tc["id"]
                func = tc.get("function", {})
                if func.get("name"):
                    entry["name"] = func["name"]
                if func.get("arguments"):
                    entry["arguments"] = func["arguments"]
                if entry:
                    result[idx] = entry
            return result
        except Exception:
            return {}

    def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
        """解析SSE data字符串为StreamChunk - 小沈 2026-06-09"""
        try:
            data = parse_json(data_str)
            if data is None:
                return None

            choices = data.get("choices", [])
            if not choices:
                return None

            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            reasoning_content = extract_reasoning_from_chunk(delta) or ""

            if content:
                return StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False, raw_data=data_str)
            if reasoning_content:
                return StreamChunk(content=reasoning_content, model=self.model, is_done=False, is_reasoning=True, raw_data=data_str)

            # tool_calls delta — _extract_tool_calls 已处理,跳过冗余空 chunk — 小沈 2026-06-14
            tool_calls_delta = delta.get("tool_calls", [])
            if tool_calls_delta:
                return None

            return None

        except Exception as e:
            logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
            return None

    def _should_retry(self, e: Exception) -> bool:
        """判断是否应该重试 - 小沈 2026-06-09"""
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code in [429, 500, 502, 503, 504]
        if isinstance(e, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
            return True
        return False

    async def close(self):
        if self._llm_sdk:
            await self._llm_sdk.close()


__all__ = ["BaseAIService", "ChatResponse", "StreamChunk"]
