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
    "get_system_info": "获取系统完整信息，包括操作系统、CPU、内存、磁盘、网络接口等硬件和系统配置信息。适合查看系统配置、诊断系统问题",
    "net_connections": "获取网络连接列表，支持按类型（TCP/UDP）、状态（ESTABLISHED/LISTEN）、端口过滤，可获取关联进程信息。适合查看网络连接、排查端口占用",
    "event_log": "获取系统事件日志（Windows事件查看器/Linux syslog），支持按级别、来源、时间范围过滤。适合查看系统错误、诊断问题、审计日志",
    "list_processes": "列出系统所有进程，支持按名称/PID过滤，可按CPU/内存占用排序。适合查看进程状态、找资源占用高的进程",
    "kill_process": "终止指定进程，支持优雅终止（SIGTERM）和强制终止（SIGKILL），需谨慎使用。适合结束卡死进程、释放资源",
    "log_message": "记录日志消息到指定日志文件或日志系统，支持DEBUG/INFO/WARNING/ERROR/CRITICAL级别。使用Python内置库logging，零依赖。适合记录调试信息、错误追踪、审计日志",
    "get_logs": "读取指定日志文件的内容，支持按级别、时间范围、关键词过滤，支持尾部读取和分页。适合查看运行日志、排查错误、分析问题",
    "service_list": "列出系统服务（Windows用sc/Linux用systemctl），支持按名称和状态（running/stopped）过滤。适合查看服务状态、管理服务",
    "service_start": "启动指定系统服务（Windows用sc/Linux用systemctl），支持超时设置。适合启动停止的服务",
    "service_stop": "停止指定系统服务（Windows用sc/Linux用systemctl），支持优雅停止和强制停止。适合停止异常服务",
    "task_list": "列出所有计划任务（Windows专用，使用schtasks），支持按名称和状态过滤。适合查看定时任务配置",
    "task_create": "创建计划任务（Windows专用），支持每日/每周/每月/一次性调度，可设置启动程序和参数。适合创建定时备份、定时检查等任务",
    "task_delete": "删除计划任务（Windows专用），使用schtasks delete命令，支持强制删除。适合清理无用定时任务",
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
        {"name": "python"},
        {"name": "python", "status": "running", "sort_by": "memory", "limit": 20},
    ],
    "kill_process": [
        {"pid": 1234},
        {"pid": 1234, "force": True},
        {"name": "python.exe"},
    ],
    "log_message": [
        {"message": "这是一条测试日志"},
        {"level": "WARNING", "message": "警告信息"},
        {"level": "ERROR", "message": "错误信息", "logger_name": "api"},
        {"message": "系统启动", "log_file": "D:/logs/app.log"},
    ],
    "get_logs": [
        {"log_file": "D:/logs/app.log"},
        {"log_file": "D:/logs/app.log", "level": "ERROR", "max_lines": 100},
        {"log_file": "D:/logs/app.log", "tail_mode": True, "max_lines": 50},
        {"log_file": "D:/logs/app.log", "pattern": "timeout", "output_format": "json"},
    ],
    "service_list": [
        {},
        {"state": "running"},
        {"name": "mysql", "state": "running"},
    ],
    "service_start": [
        {"service_name": "mysql"},
        {"service_name": "nginx", "wait_for_started": True},
    ],
    "service_stop": [
        {"service_name": "mysql"},
        {"service_name": "nginx", "force": True},
    ],
    "task_list": [
        {},
        {"state": "running"},
        {"folder": "\\Microsoft", "state": "ready"},
    ],
    "task_create": [
        {"task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"},
        {"task_name": "WeeklyReport", "command": "python C:\\scripts\\report.py", "schedule": "09:00 /day 1", "start_time": "09:00"},
    ],
    "task_delete": [
        {"task_name": "MyBackup"},
        {"task_name": "OldTask", "folder": "\\Microsoft"},
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
