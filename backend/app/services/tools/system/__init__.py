# -*- coding: utf-8 -*-
"""SYSTEM 模块 - 系统信息 + 环境变量工具

【2026-05-18 小沈】Environment工具迁入,旧函数service_list/start/stop/task_list/create/delete删除
【2026-06-17 小健】reg_* 迁入 win_registry/ 独立目录
"""

from app.services.tools.system.system_register import *
from app.services.tools.system.system_tools import (
    get_system_info,
    service_control,
    create_task,
    delete_task,
    list_tasks,
)
from app.services.tools.system.env_tools import (
    get_env,
    set_env,
)

__all__ = [
    "get_system_info",
    "service_control",
    "create_task",
    "delete_task",
    "list_tasks",
    "get_env",
    "set_env",
]
