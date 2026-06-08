# -*- coding: utf-8 -*-
"""
chat — 从 llm_core.py 拆出的 chat 方法

P2-21: 复用 tool_caller.py 的 chat_with_tools，消除重复聚合逻辑
Author: 小沈 - 2026-05-31
P2-21 修复 - 小欧 2026-06-08
"""

from typing import List, Dict, Optional

from app.services.llm.core import ChatResponse


async def aggregate_chat_response(self, message: str, history: Optional[List[Dict]] = None) -> ChatResponse:
    """聚合流式chunk为完整ChatResponse — 复用 chat_with_tools,不传tools"""
    return await self.chat_with_tools(message, history, tools=None, tool_choice=None)
