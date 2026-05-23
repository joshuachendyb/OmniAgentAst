"""
LLM适配器 — 探测+策略选择合一

逻辑：发一个带tools参数的请求，模型返回tool_calls → tools，否则 → text
缓存探测结果，不重复探测。
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
        self._capability_cache = None
    
    async def ensure_capability(self) -> str:
        """探测并返回策略: tools 或 text"""
        if self._strategy is not None:
            return self._strategy
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                result = await self._probe_tools(client)
                if result["works"]:
                    self._strategy = "tools"
                    self._capability_cache = type('Cap', (), {'supports_tools': True, 'supports_response_format': False})()
                    logger.info(f"[适配器] model={self.model} → tools (FC支持)")
                else:
                    self._strategy = "text"
                    self._capability_cache = type('Cap', (), {'supports_tools': False, 'supports_response_format': False})()
                    logger.info(f"[适配器] model={self.model} → text (FC不支持: {result.get('reason', 'N/A')})")
        except Exception as e:
            logger.error(f"[适配器] 探测异常: {e}")
            self._strategy = "text"
            self._capability_cache = None
        
        return self._strategy
    
    async def _probe_tools(self, client: httpx.AsyncClient) -> dict:
        """发一个带tools的请求，看返回有没有tool_calls"""
        tools = [{"type": "function", "function": {"name": "test_tool", "description": "A test tool", "parameters": {"type": "object", "properties": {"param": {"type": "string", "description": "test"}}, "required": ["param"]}}}]
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": [{"role": "user", "content": "Call test_tool"}], "tools": tools, "tool_choice": "auto", "stream": False}
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
