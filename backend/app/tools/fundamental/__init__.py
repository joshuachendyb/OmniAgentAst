# -*- coding: utf-8 -*-
"""FUNDAMENTAL 模块 - 基础工具(搜索+时间+系统信息+Shell)
【2026-06-18 小欧】从 meta/ 迁入,匹配 ToolCategory.FUNDAMENTAL
【2026-07-28 北京老陈】timeadd/timediff/calendar 迁至 TIMER 分类; shell 从 SHELL 迁入
"""

from app.tools.fundamental.fundamental_register import _register_fundamental_tools

from app.tools.fundamental.tool_search import searchtool
from app.tools.fundamental.time_now import timenow
from app.tools.fundamental.execute_shell_command import shell
from app.tools.fundamental.get_system_info import sysinfo
from app.tools.fundamental.send_notification import notify

__all__ = [
    "_register_fundamental_tools",
    "searchtool",
    "timenow",
    "shell",
    "sysinfo",
    "notify",
]
