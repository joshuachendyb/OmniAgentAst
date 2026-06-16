# -*- coding: utf-8 -*-
"""SYSTEM 模块 - 系统信息 + 环境变量工具

【2026-05-18 小沈】Environment工具迁入,旧函数service_list/start/stop/task_list/create/delete删除
"""

from app.services.tools.system.system_register import *
from app.services.tools.system.system_tools import (
    get_system_info,
    service_control,
    create_task,
    delete_task,
    list_tasks,
)
from app.services.tools.system.reg_register import *
from app.services.tools.system.reg_tools import (
    registry_read,
    registry_write,
    registry_delete,
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
    "registry_read",
    "registry_write",
    "registry_delete",
    "get_env",
    "set_env",
]
