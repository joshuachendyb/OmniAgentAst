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
    "list_processes": "列出系统所有进程，支持按filter_name/filter_pid过滤，可按CPU/内存占用排序。适合查看进程状态、找资源占用高的进程",
    "kill_process": "终止指定进程(pid必填)，支持优雅终止（SIGTERM）和强制终止（SIGKILL），需谨慎使用。适合结束卡死进程、释放资源",
    "log_message": "记录日志消息到指定日志文件或日志系统。\n\nScenarios:\n- When user needs to log operation\n- When user wants audit trail\n- When user needs debug\n\nParams:\n- message: log message content (required)\n- level: log level (optional), default INFO\n- logger_name: logger name (optional), default root\n- log_file: log file path (optional), default console\n\n[Important] Uses Python builtin logging. Agent auto infers level\n\nExamples:\n- Log: {\"message\": \"User logged in\", \"level\": \"INFO\"}\n- To file: {\"message\": \"System started\", \"log_file\": \"D:/logs/app.log\"}",
    "get_logs": "读取指定日志文件的内容，支持智能过滤与截断。\n\nScenarios:\n- When user needs to view log content\n- When user wants to analyze history\n- When user needs troubleshooting\n\nParams:\n- log_file: log file path (required)\n- level: log level filter (optional), default WARNING\n- start_time/end_time: time range filter (optional)\n- log_format: time format (optional), default auto_detect\n- max_lines: max lines (optional), default 200\n- tail_mode: tail read mode (optional), default false\n- pattern: keyword filter (optional)\n- output_format: output format (optional), default table\n\n[Important] tail_mode enabled skips level/pattern filter\n\nExamples:\n- Read: {\"log_file\": \"D:/logs/app.log\"}\n- Filter ERROR: {\"log_file\": \"D:/logs/app.log\", \"level\": \"ERROR\", \"max_lines\": 100}",
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
        {"filter_name": "python"},
        {"filter_name": "python", "sort_by": "memory", "max_results": 20},
    ],
    "kill_process": [
        {"pid": 1234},
        {"pid": 1234, "force": True},
    ],
    "log_message": [
        {"message": "这是一条测试日志"},
        {"level": "WARNING", "message": "警告信息"},
        {"message": "错误信息", "level": "ERROR", "logger_name": "api"},
    ],
    "get_logs": [
        {"log_file": "D:/logs/app.log"},
        {"log_file": "D:/logs/app.log", "level": "ERROR", "max_lines": 100},
        {"log_file": "D:/logs/app.log", "pattern": "timeout", "tail_mode": True},
        {"log_file": "D:/logs/app.log", "start_time": "2026-01-01", "end_time": "2026-01-02", "output_format": "json"},
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
