# -*- coding: utf-8 -*-
"""
LLM 调用策略模块 — 简化版

小健 - 2026-06-07 删除ToolsStrategy(Function Calling模式),当前只用TextStrategy

只保留:
1. TextStrategy:文本模式,直接返回响应文本

Author: 小沈 - 2026-03-21
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from app.utils.logger import logger
from app.utils.error_classifier import UnifiedErrorClassifier


class LLMStrategy(ABC):
    """LLM 调用策略基类"""
    
    @abstractmethod
    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        pass
    
    def _make_parse_error(self, error: str, content: str = "") -> str:
        return json.dumps({
            "type": "parse_error",
            "error": error,
            "content": content,
            "tool_name": None,
            "tool_params": None,
            "reasoning": None
        }, ensure_ascii=False)


class TextStrategy(LLMStrategy):
    """文本模式 — 直接返回响应文本"""

    def _extract_llm_content(self, response: Any) -> tuple:
        error_info = None
        if getattr(response, "error", None):
            error_info = response.error
            logger.warning(f"[LLM Response] LLM returned error: {error_info}")
        content = response.content if hasattr(response, "content") and response.content else None
        if content is None and isinstance(response, dict):
            content = response.get("content") or str(response)
        elif content is None:
            content = str(response)
        response_reasoning = getattr(response, "reasoning", "") or ""
        return content, error_info, response_reasoning

    async def call(
        self,
        llm_client: Callable,
        messages: List[Dict[str, str]],
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """调用 LLM(文本模式) — 直接返回原始文本,由base_react.py统一解析"""
        logger.info(f"[TextStrategy] call() 被调用, model={getattr(llm_client, 'model', '?')}")
        response = await llm_client(message="", history=messages)
        content, error_info, response_reasoning = self._extract_llm_content(response)
        
        if not content:
            logger.warning("[LLM Response] Warning: LLM returned empty content!")
            if error_info:
                error_hint = self._format_error_hint(error_info)
                logger.warning(f"[LLM Response] Error hint: {error_hint}")
                return self._make_parse_error(error_hint)
            _, user_message = UnifiedErrorClassifier.classify_error_message('empty_response')
            return self._make_parse_error(user_message)
        
        return content
    
    def _format_error_hint(self, error: str) -> str:
        category = UnifiedErrorClassifier.classify_error(str(error))
        _, user_message = UnifiedErrorClassifier.classify_error_message(category.value, original_message=str(error))
        logger.info(f"[LLM Error] 原始错误: {error}, 分类: {category.value}, 提示: {user_message}")
        return f"⚠️ {user_message}"
