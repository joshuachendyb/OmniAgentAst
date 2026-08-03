# -*- coding: utf-8 -*-
"""FUNDAMENTAL 模块 - 基础工具(搜索+时间)
【2026-06-18 小欧】从 meta/ 迁入,匹配 ToolCategory.FUNDAMENTAL
"""

from app.tools.fundamental.fundamental_register import _register_fundamental_tools

from app.tools.fundamental.tool_search import searchtool
from app.tools.fundamental.time_now import timenow
from app.tools.fundamental.time_add import timeadd
from app.tools.fundamental.time_diff import timediff
from app.tools.fundamental.query_calendar import calendar
from app.tools.fundamental.get_system_info import sysinfo
from app.tools.fundamental.send_notification import notify

__all__ = [
    "_register_fundamental_tools",
    "searchtool",
    "timenow",
    "timeadd",
    "timediff",
    "calendar",
    "sysinfo",
    "notify",
]
