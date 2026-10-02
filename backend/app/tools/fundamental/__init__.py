# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-02 - 小欧 - 归组调整: sysinfo 整体迁出本模块至 system/, __all__ 同步移除其导出 — 小欧-2026-10-02
"""FUNDAMENTAL 模块 - 基础工具(搜索+时间+Shell+通知)
【2026-06-18 小欧】从 meta/ 迁入,匹配 ToolCategory.FUNDAMENTAL
【2026-07-28 北京老陈】timeadd/timediff/calendar 迁至 TIMER 分类; shell 从 SHELL 迁入
【2026-10-02 小欧】sysinfo 整体迁出本模块(回归 SYSTEM 分类, 实现 get_system_info.py 与
   schema GetSystemInfoInput 已迁至 app/tools/system/), 故此处不再导出 sysinfo — 小欧-2026-10-02
"""

from app.tools.fundamental.fundamental_register import _register_fundamental_tools

from app.tools.fundamental.tool_search import searchtool
from app.tools.fundamental.time_now import timenow
from app.tools.fundamental.execute_shell_command import shell
from app.tools.fundamental.send_notification import notify

__all__ = [
    "_register_fundamental_tools",
    "searchtool",
    "timenow",
    "shell",
    "notify",
]
