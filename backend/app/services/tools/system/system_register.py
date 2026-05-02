# -*- coding: utf-8 -*-
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【工具列表】（共13个）
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程
6. log_message - 记录日志消息
7. get_logs - 获取应用日志
8. service_list - 列出所有服务
9. service_start - 启动服务
10. service_stop - 停止服务
11. task_list - 列出所有计划任务（Windows专用）
12. task_create - 创建计划任务（Windows专用）
13. task_delete - 删除计划任务（Windows专用）

创建时间: 2026-04-29
更新时间: 2026-05-02
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.system.system_schema import (
    GetSystemInfoInput,
    NetConnectionsInput,
    EventLogInput,
    ListProcessesInput,
    KillProcessInput,
    LogMessageInput,
    GetLogsInput,
    ServiceListInput,
    ServiceStartInput,
    ServiceStopInput,
    TaskListInput,
    TaskCreateInput,
    TaskDeleteInput,
)

from app.services.tools.system.system_tools import (
    get_system_info,
    net_connections,
    event_log,
    list_processes,
    kill_process,
    log_message,
    get_logs,
    service_list,
    service_start,
    service_stop,
    task_list,
    task_create,
    task_delete,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {
    "get_system_info": "获取系统信息，包括平台、CPU、内存、磁盘、网络等详细信息",
    "net_connections": "获取网络连接列表，支持按类型、状态、端口过滤，可获取进程信息",
    "event_log": "获取系统事件日志，支持按级别、来源、时间范围过滤",
    "list_processes": "列出系统进程，支持按名称/PID过滤，可按CPU/内存排序",
    "kill_process": "终止指定进程，支持优雅终止和强制终止",
    "log_message": "记录日志消息，支持debug/info/warning/error/critical级别",
    "get_logs": "获取应用日志，支持按日期、级别、模块、关键字过滤",
    "service_list": "列出所有系统服务，支持按名称和状态过滤（Windows用sc，Linux用systemctl）",
    "service_start": "启动指定服务，支持超时设置（Windows用sc，Linux用systemctl）",
    "service_stop": "停止指定服务，支持优雅停止和强制停止（Windows用sc，Linux用systemctl）",
    "task_list": "列出所有计划任务（Windows专用），使用schtasks query命令，支持按名称和状态过滤",
    "task_create": "创建计划任务（Windows专用），使用schtasks create命令，支持每日/每周/每月调度",
    "task_delete": "删除计划任务（Windows专用），使用schtasks delete命令，支持强制删除",
}

# 模型映射
SYSTEM_TOOL_INPUT_MODELS = {
    "get_system_info": GetSystemInfoInput,
    "net_connections": NetConnectionsInput,
    "event_log": EventLogInput,
    "list_processes": ListProcessesInput,
    "kill_process": KillProcessInput,
    "log_message": LogMessageInput,
    "get_logs": GetLogsInput,
    "service_list": ServiceListInput,
    "service_start": ServiceStartInput,
    "service_stop": ServiceStopInput,
    "task_list": TaskListInput,
    "task_create": TaskCreateInput,
    "task_delete": TaskDeleteInput,
}

# 使用示例
SYSTEM_TOOL_EXAMPLES = {
    "get_system_info": [
        {"info_type": "all"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
    ],
    "net_connections": [
        {},
        {"kind": "tcp", "state": "established"},
        {"filter_port": 8080, "process_info": True},
    ],
    "event_log": [
        {},
        {"log_name": "Application", "max_events": 20},
        {"level": "error", "time_range": "24h"},
    ],
    "list_processes": [
        {},
        {"filter_name": "python"},
        {"sort_by": "memory", "descending": True, "max_results": 20},
    ],
    "kill_process": [
        {"pid": 1234},
        {"pid": 1234, "force": True},
    ],
    "log_message": [
        {"message": "这是一条测试日志"},
        {"level": "warning", "message": "警告信息"},
        {"level": "error", "message": "错误信息", "module": "api"},
    ],
    "get_logs": [
        {},
        {"level": "ERROR", "max_lines": 50},
        {"keyword": "timeout", "max_lines": 20},
        {"date": "2026-05-01", "level": "INFO"},
    ],
    "service_list": [
        {},
        {"filter_state": "running"},
        {"filter_name": "mysql", "max_results": 20},
    ],
    "service_start": [
        {"service_name": "mysql"},
        {"service_name": "nginx", "timeout": 60},
    ],
    "service_stop": [
        {"service_name": "mysql"},
        {"service_name": "nginx", "force": True},
    ],
    "task_list": [
        {},
        {"filter_status": "ready"},
        {"filter_name": "backup", "max_results": 20},
    ],
    "task_create": [
        {"task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"},
        {"task_name": "WeeklyReport", "command": "python C:\\scripts\\report.py", "schedule": "09:00 /day 1"},
    ],
    "task_delete": [
        {"task_name": "MyBackup"},
        {"task_name": "OldTask", "force": True},
    ],
}


def _register_system_tools():
    """注册所有系统信息工具"""
    tool_methods = {
        "get_system_info": get_system_info,
        "net_connections": net_connections,
        "event_log": event_log,
        "list_processes": list_processes,
        "kill_process": kill_process,
        "log_message": log_message,
        "get_logs": get_logs,
        "service_list": service_list,
        "service_start": service_start,
        "service_stop": service_stop,
        "task_list": task_list,
        "task_create": task_create,
        "task_delete": task_delete,
    }

    for name, method in tool_methods.items():
        desc = SYSTEM_TOOL_DESCRIPTIONS.get(name, "")
        input_model = SYSTEM_TOOL_INPUT_MODELS.get(name)
        examples = SYSTEM_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.SYSTEM,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[system_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_system_tools()
