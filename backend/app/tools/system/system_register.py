# -*- coding: utf-8 -*-
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【2026-06-18 小健】添加SYSTEM_TOOL_DEPENDENCIES常量管理工具依赖
【2026-06-20 小健】删除list_processes/kill_process/service_control/get_env/set_env/net_connections

【工具列表】(本文件注册4个 + reg_register注册1个)
1. event_log - 获取系统事件日志 (依赖: psutil)
2. task_control - 计划任务统一控制(create/delete/list) (无第三方依赖)
+ reg_read, reg_write, reg_delete(reg_register.py注册)

【2026-06-18 小健】get_system_info移入FUNDAMENTAL分类

创建时间: 2026-04-29
更新时间: 2026-06-20 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

SYSTEM_TOOL_DEPENDENCIES = {
    "event_log": ["psutil"],
    "task_control": [],
}

from app.tools.system.system_schema import (
    EventLogInput,
    CreateTaskInput,
    DeleteTaskInput,
    ListTasksInput,
)

from app.tools.system.event_log import event_log
from app.tools.system.create_task import create_task
from app.tools.system.delete_task import delete_task
from app.tools.system.list_tasks import list_tasks

SYSTEM_TOOL_DESCRIPTIONS = {
    "event_log": """获取系统事件日志,可按级别和时间范围过滤。适用场景:需要查看系统错误、诊断问题、审计安全事件时使用。""",
    "create_task": """创建Windows计划任务,定时执行脚本或程序。适用场景:需要定时备份、周期性维护、自动执行脚本时使用。""",
    "delete_task": """删除Windows计划任务。适用场景:需要移除不再需要的定时任务时使用。需谨慎操作。""",
    "list_tasks": """列出Windows计划任务,支持按名称和状态筛选。适用场景:需要查看所有定时任务、查找特定任务时使用。""",
}

SYSTEM_TOOL_INPUT_MODELS = {
    "event_log": EventLogInput,
    "create_task": CreateTaskInput,
    "delete_task": DeleteTaskInput,
    "list_tasks": ListTasksInput,
}

SYSTEM_TOOL_EXAMPLES = {
    "event_log": [
        {},
        {"log_name": "Application", "max_events": 20},
        {"level": "error", "time_range": "24h"},
    ],
    "create_task": [
        {"task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"},
        {"task_name": "WeeklyReport", "command": "C:\\scripts\\report.bat", "schedule": "08:00 /day 1"},
        {"task_name": "HourlyCheck", "command": "C:\\scripts\\check.bat", "schedule": "09:00", "interval": 60},
    ],
    "delete_task": [
        {"task_name": "MyBackup"},
    ],
    "list_tasks": [
        {},
        {"state": "running"},
        {"task_name": "Backup"},
    ],
}


def _register_system_tools():
    """注册系统工具 — 全部归入SYSTEM — 小欧 2026-06-12"""
    CONFIRM_TOOLS = {"create_task", "delete_task"}

    system_tools = {
        "event_log": event_log,
        "create_task": create_task,
        "delete_task": delete_task,
        "list_tasks": list_tasks,
    }

    for name, method in system_tools.items():
        desc = SYSTEM_TOOL_DESCRIPTIONS.get(name, "")
        input_model = SYSTEM_TOOL_INPUT_MODELS.get(name)
        examples = SYSTEM_TOOL_EXAMPLES.get(name, [])
        tool_registry.register(
            name=name, description=desc, category=ToolCategory.SYSTEM,
            implementation=method, version="1.0.0", input_model=input_model, examples=examples,
            needs_confirmation=(name in CONFIRM_TOOLS),
            dependencies=SYSTEM_TOOL_DEPENDENCIES.get(name, []),
        )
        logger.debug(f"[system_register] 已注册工具(SYSTEM): {name}")


__all__ = ["_register_system_tools"]
