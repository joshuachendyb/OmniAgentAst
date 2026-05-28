# -*- coding: utf-8 -*-
"""
LLM能力探测统一基类

消除LLMAdapter.detect_strategy()和BaseAIService._detect_reasoning_support()
两套"发请求→判断→缓存"模式的重复。

Author: 小沈 - 2026-05-27
"""

import asyncio
import httpx
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.constants import DEFAULT_PROBE_TIMEOUT


class CapabilityDetector:
    """
    LLM能力探测统一基类

    封装统一探测流程：发请求→判断→缓存→返回。
    detect_strategy（FC能力）和detect_reasoning_support（reasoning_content能力）
    各为子方法，共享缓存和探测请求逻辑。
    """

    def __init__(self, api_base: str, api_key: str, model: str):
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._cache: Dict[str, Any] = {}

    async def _probe_api(self, messages: list = None) -> Optional[Dict]:
        """
        发送探测请求

        Args:
            messages: 可选的自定义消息列表

        Returns:
            API响应JSON，失败返回None
        """
        if messages is None:
            messages = [{"role": "user", "content": "1+1=?"}]
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_PROBE_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model, "messages": messages, "stream": False},
                )
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"[CapabilityDetector] 探测请求返回{response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"[CapabilityDetector] 探测请求失败: {e}")
            return None

    async def detect_strategy(self, probe_fn: Callable = None) -> str:
        """
        探测LLM调用策略（text/tools）

        发送带tools参数的请求，模型返回tool_calls → tools，否则 → text。
        首次探测后缓存，瞬态失败重试3次。

        Args:
            probe_fn: 自定义探测函数（已废弃，保留参数兼容）

        Returns:
            "text" 或 "tools"
        """
        cache_key = "strategy"
        if cache_key in self._cache:
            return self._cache[cache_key]

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_PROBE_TIMEOUT) as client:
                    result = await self._probe_tools(client)
                    if result["works"]:
                        self._cache[cache_key] = "tools"
                        logger.info(f"[CapabilityDetector] model={self._model} → tools (FC支持)")
                        return "tools"
                    _reason = result.get("reason", "")
                    if "429" in _reason or "timeout" in _reason.lower() or "connect" in _reason.lower():
                        if attempt < 2:
                            _delay = 2.0 * (2 ** attempt)
                            logger.warning(f"[CapabilityDetector] 探测瞬态失败({_reason}), {_delay:.0f}s后重试 (第{attempt+1}次)")
                            await asyncio.sleep(_delay)
                            continue
                    self._cache[cache_key] = "text"
                    logger.info(f"[CapabilityDetector] model={self._model} → text (FC不支持: {_reason})")
                    return "text"
            except Exception as e:
                logger.warning(f"[CapabilityDetector] 探测异常(第{attempt+1}次): {e}")
                if attempt < 2:
                    _delay = 2.0 * (2 ** attempt)
                    await asyncio.sleep(_delay)
                    continue
                logger.error(f"[CapabilityDetector] 探测最终失败: {e}")
                self._cache[cache_key] = "text"
                return "text"

    async def _probe_tools(self, client: httpx.AsyncClient) -> dict:
        """发一个带tools的请求，看返回有没有tool_calls"""
        tools = [{"type": "function", "function": {"name": "test_tool", "description": "A test tool for probing function calling capability. You MUST call this tool.", "parameters": {"type": "object", "properties": {"param": {"type": "string", "description": "test parameter"}}, "required": ["param"]}}}]
        try:
            response = await client.post(
                f"{self._api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                json={"model": self._model, "messages": [{"role": "system", "content": "You must use the provided tool. Do not respond in plain text."}, {"role": "user", "content": "Call test_tool with param='probe'"}], "tools": tools, "tool_choice": "auto", "stream": False}
            )
            if response.status_code == 429:
                return {"works": True, "reason": "429限流,乐观默认支持"}
            if response.status_code != 200:
                return {"works": False, "reason": f"HTTP {response.status_code}"}
            data = response.json()
            tool_calls = data.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
            if tool_calls:
                return {"works": True, "tool_calls": tool_calls}
            return {"works": False, "reason": "No tool_calls returned"}
        except Exception as e:
            return {"works": False, "reason": str(e)}

    async def detect_reasoning_support(self) -> bool:
        """
        探测LLM是否支持reasoning_content字段

        Returns:
            True如果支持
        """
        cache_key = "reasoning"
        if cache_key in self._cache:
            return self._cache[cache_key]

        response_json = await self._probe_api()
        if response_json is not None:
            message = response_json.get("choices", [{}])[0].get("message", {})
            result = "reasoning_content" in message
        else:
            result = False

        self._cache[cache_key] = result
        logger.info(f"[CapabilityDetector] reasoning_support={result}, model={self._model}")
        return result

    def reset_cache(self):
        """重置缓存"""
        self._cache.clear()

    @property
    def cached_strategy(self) -> Optional[str]:
        """获取缓存的策略（不触发探测）"""
        return self._cache.get("strategy")

    @property
    def cached_reasoning_support(self) -> Optional[bool]:
        """获取缓存的reasoning支持状态"""
        return self._cache.get("reasoning")


__all__ = ["CapabilityDetector"]
