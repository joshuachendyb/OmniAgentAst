# -*- coding: utf-8 -*-
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【工具列表】（共5个）
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程

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
)

from app.services.tools.system.system_tools import (
    get_system_info,
    net_connections,
    event_log,
    list_processes,
    kill_process,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {
    "get_system_info": "获取系统信息，包括平台、CPU、内存、磁盘、网络等详细信息",
    "net_connections": "获取网络连接列表，支持按类型、状态、端口过滤，可获取进程信息",
    "event_log": "获取系统事件日志，支持按级别、来源、时间范围过滤",
    "list_processes": "列出系统进程，支持按名称/PID过滤，可按CPU/内存排序",
    "kill_process": "终止指定进程，支持优雅终止和强制终止",
}

# 模型映射
SYSTEM_TOOL_INPUT_MODELS = {
    "get_system_info": GetSystemInfoInput,
    "net_connections": NetConnectionsInput,
    "event_log": EventLogInput,
    "list_processes": ListProcessesInput,
    "kill_process": KillProcessInput,
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
}


def _register_system_tools():
    """注册所有系统信息工具"""
    tool_methods = {
        "get_system_info": get_system_info,
        "net_connections": net_connections,
        "event_log": event_log,
        "list_processes": list_processes,
        "kill_process": kill_process,
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
