# -*- coding: utf-8 -*-
"""FUNDAMENTAL 模块 - 基础工具(搜索+时间)
【2026-06-18 小欧】从 meta/ 迁入,匹配 ToolCategory.FUNDAMENTAL
"""

from app.tools.fundamental.fundamental_register import _register_fundamental_tools

from app.tools.fundamental.tool_search import tool_search
from app.tools.fundamental.time_now import time_now
from app.tools.fundamental.time_add import time_add
from app.tools.fundamental.time_diff import time_diff
from app.tools.fundamental.query_calendar import query_calendar
from app.tools.fundamental.get_system_info import get_system_info
from app.tools.fundamental.send_notification import send_notification

__all__ = [
    "_register_fundamental_tools",
    "tool_search",
    "time_now",
    "time_add",
    "time_diff",
    "query_calendar",
    "get_system_info",
    "send_notification",
]
