"""
LLM适配器 — 探测FC支持→决定策略

逻辑：发一个带tools参数的请求，模型返回tool_calls → tools，否则 → text
首次探测后缓存，不重复探测。
"""

import json
import httpx
from typing import Optional

from app.utils.logger import logger


class LLMAdapter:
    """探测LLM是否支持FC，决定用tools还是text策略"""

    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self._strategy: Optional[str] = None

    async def detect_strategy(self) -> str:
        """探测并返回策略: tools 或 text（首次探测后缓存，瞬态失败重试）"""
        if self._strategy is not None:
            return self._strategy

        import asyncio
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    result = await self._probe_tools(client)
                    if result["works"]:
                        self._strategy = "tools"
                        logger.info(f"[适配器] model={self.model} → tools (FC支持)")
                        return self._strategy
                    _reason = result.get("reason", "")
                    # 429/超时/连接类错误可重试
                    if "429" in _reason or "timeout" in _reason.lower() or "connect" in _reason.lower():
                        if attempt < 2:
                            _delay = 2.0 * (2 ** attempt)
                            logger.warning(f"[适配器] 探测瞬态失败({_reason}), {_delay:.0f}s后重试 (第{attempt+1}次)")
                            await asyncio.sleep(_delay)
                            continue
                    self._strategy = "text"
                    logger.info(f"[适配器] model={self.model} → text (FC不支持: {_reason})")
                    return self._strategy
            except Exception as e:
                logger.warning(f"[适配器] 探测异常(第{attempt+1}次): {e}")
                if attempt < 2:
                    _delay = 2.0 * (2 ** attempt)
                    await asyncio.sleep(_delay)
                    continue
                logger.error(f"[适配器] 探测最终失败: {e}")
                self._strategy = "text"
                return self._strategy

    async def _probe_tools(self, client: httpx.AsyncClient) -> dict:
        """发一个带tools的请求，看返回有没有tool_calls"""
        tools = [{"type": "function", "function": {"name": "test_tool", "description": "A test tool for probing function calling capability. You MUST call this tool.", "parameters": {"type": "object", "properties": {"param": {"type": "string", "description": "test parameter"}}, "required": ["param"]}}}]
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "system", "content": "You must use the provided tool. Do not respond in plain text."}, {"role": "user", "content": "Call test_tool with param='probe'"}], "tools": tools, "tool_choice": "auto", "stream": False}
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

    @property
    def method(self) -> str:
        return self._strategy or "unknown"


__all__ = ["LLMAdapter"]
