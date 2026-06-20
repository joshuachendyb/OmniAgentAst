# -*- coding: utf-8 -*-
"""SYSTEM 模块 - 系统信息工具

【2026-05-18 小沈】Environment工具迁入,旧函数service_list/start/stop/task_list/create/delete删除
【2026-06-17 小健】reg_* 迁入 win_registry/ 独立目录
【2026-06-20 小健】删除get_env/set_env/net_connections
"""

from app.tools.system.system_register import *
from app.tools.system.system_tools import (
    get_system_info,
    create_task,
    delete_task,
    list_tasks,
)

__all__ = [
    "get_system_info",
    "create_task",
    "delete_task",
    "list_tasks",
]
