# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤2): 编排逻辑(chat_stream/confirm_operation/step_start)迁入
#   services/chat/stream_orchestrator.py, 本包不再 export 已删除的编排函数(禁止 backward); 保留 router/task_router/sse 路由。
# 2026-08-14 - 小欧 - 改名名实相符: openai.py → chat_routes.py(实为自定义Chat路由薄壳, 无OpenAI协议)
"""
chat — Chat API模块

小健 - 2026-06-07 清理:删除step_react_loop和route(死代码)

Author: 小沈 - 2026-03-26
"""

from app.api.v1.chat.models import ChatMessage, ChatRequest
from app.api.v1.chat.chat_routes import router, task_router
__all__ = [
    "ChatMessage", "ChatRequest",
    "router", "task_router",
]
