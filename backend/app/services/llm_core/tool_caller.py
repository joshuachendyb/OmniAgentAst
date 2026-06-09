# -*- coding: utf-8 -*-
"""
tool_caller — 调用SDK层实现FC

重构：Service层调用SDK层，消除重复代码 - 小沈 2026-06-09
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Any, Optional

from app.utils.logger import logger
from app.services.llm.core import ChatResponse


class ToolCallerMixin:
    """Function Calling(SRP)"""

    async def chat_with_tools(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        """非流式FC对话 — 调用SDK层chat() - 小沈 2026-06-09"""
        try:
            full_content = ""
            full_reasoning = ""
            has_non_reasoning_content = False
            stream_error = None

            async for chunk in self.chat_with_tools_stream(message, history, tools, tool_choice):
                if chunk.content:
                    if getattr(chunk, "is_reasoning", False):
                        full_reasoning += chunk.content
                    else:
                        full_content += chunk.content
                        has_non_reasoning_content = True
                if chunk.reasoning:
                    full_reasoning += chunk.reasoning
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                if chunk.is_done:
                    break

            if not has_non_reasoning_content and full_reasoning:
                full_content = full_reasoning

            if stream_error:
                return ChatResponse(content="", model=self.model, provider=self.provider, error=stream_error)

            return ChatResponse(content=full_content, model=self.model, provider=self.provider, reasoning=full_reasoning)

        except Exception as e:
            logger.error(f"[chat_with_tools] 异常: {e}")
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
