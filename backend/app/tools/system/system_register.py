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

from app.tools.system.system_tools import (
    event_log,
    create_task,
    delete_task,
    list_tasks,
)

SYSTEM_TOOL_DESCRIPTIONS = {
    "event_log": """获取系统事件日志。Windows使用wevtutil,Linux使用journalctl。支持日志名称(Application/System/Security)、事件级别(critical/error/warning/info)、时间范围(10m/1h/24h/7d)和来源应用名过滤。默认返回System日志,级别error,时间范围1h。适用场景:需要查看系统错误日志、诊断系统问题、审计系统安全事件时使用。""",
    "create_task": """创建Windows计划任务(.bat/.exe等)。必填参数:task_name(任务名)、command(命令或程序路径,如C:\\scripts\\backup.bat)、schedule(计划时间,格式HH:MM每日/HH:MM /day N每周/HH:MM /monthly DD每月)。可选参数:interval(重复间隔分钟数)。适用场景:需要定时执行脚本、定期备份、周期性维护任务时使用。""",
    "delete_task": """删除Windows计划任务。必填参数:task_name(要删除的计划任务名称)。删除前会先查询确认任务存在。适用场景:需要移除不再需要的计划任务时使用。需谨慎操作。""",
    "list_tasks": """列出Windows计划任务。可选参数:task_name(按名称模糊过滤)、state(状态过滤,ready/running/disabled/all,默认all)。适用场景:需要查看所有计划任务、按名称查找特定任务、按状态筛选任务时使用。""",
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
