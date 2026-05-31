# -*- coding: utf-8 -*-
"""
tool_caller — 从 llm_core.py 拆出

复制来源: llm_core.py 第279-305行 (_cancel_or_wait, _response_or_error),
          第348-381行 (chat_with_tools)
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import List, Dict, Any, Optional

from app.utils.logger import logger
from app.services.llm.core import ChatResponse


class ToolCallerMixin:
    """Function Calling（SRP）"""

    async def _cancel_or_wait(self, request_task: asyncio.Task) -> Optional[ChatResponse]:
        """复制自 llm_core.py 第279-298行 — 心跳循环：1秒间隔检查取消"""
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

    def _response_or_error(
        self,
        content: str = "",
        error: str = "",
        tool_calls: Optional[List] = None,
        reasoning: str = "",
    ) -> ChatResponse:
        """复制自 llm_core.py 第300-305行 — 统一构建 ChatResponse"""
        return ChatResponse(
            content=content,
            model=self.model,
            provider=self.provider,
            error=error,
            tool_calls=tool_calls,
            reasoning=reasoning,
        )

    async def chat_with_tools(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        """复制自 llm_core.py 第348-381行 — 发送对话请求（使用 Function Calling）"""
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
