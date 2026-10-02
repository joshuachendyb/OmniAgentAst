# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-02 - 小欧 - 归组调整: ①sysinfo 整体迁入 SYSTEM(与同依赖 psutil 的 event_log 团聚);
#   ②which 由 SHELL 归入 SYSTEM(注册项/实现/schema 均迁入本模块), SHELL 分类随之消亡 — 小欧-2026-10-02
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【2026-06-18 小健】添加SYSTEM_TOOL_DEPENDENCIES常量管理工具依赖
【2026-06-20 小健】删除list_processes/kill_process/service_control/get_env/set_env/net_connections
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复

【工具列表】(本文件注册6个 + reg_register注册1个)
1. event_log - 获取系统事件日志 (依赖: psutil)
2. task_control - 计划任务统一控制(create/delete/list) (无第三方依赖)
3. which - 查找命令安装路径      (2026-10-02 自 SHELL 迁入)
4. sysinfo - 获取系统信息        (2026-10-02 自 FUNDAMENTAL 迁入)
+ reg_read, reg_write, reg_delete(reg_register.py注册)

【2026-06-18 小健】get_system_info移入FUNDAMENTAL分类

创建时间: 2026-04-29
更新时间: 2026-10-02 小欧
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

SYSTEM_TOOL_DEPENDENCIES = {
    "event_log": ["psutil"],
    "task_control": [],
    "sysinfo": ["psutil"],   # 2026-10-02 小欧 - 随 sysinfo 迁入
    "which": [],             # 2026-10-02 小欧 - 随 which 迁入
}

from app.tools.system.system_schema import (
    EventLogInput,
    CreateTaskInput,
    DeleteTaskInput,
    ListTasksInput,
    WhichInput,          # 2026-10-02 小欧 - 随 which 迁入
    GetSystemInfoInput,  # 2026-10-02 小欧 - 随 sysinfo 迁入
)

from app.tools.system.event_log import event_log
from app.tools.system.create_task import create_task
from app.tools.system.delete_task import delete_task
from app.tools.system.list_tasks import list_tasks
from app.tools.system.find_command import which   # 2026-10-02 小欧 - 自 shell/ 迁入
from app.tools.system.get_system_info import sysinfo  # 2026-10-02 小欧 - 自 fundamental/ 迁入

# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 SYSTEM_TOOL_DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
SYSTEM_TOOL_DESCRIPTIONS = {
    "event_log": """获取系统事件日志,可按级别和时间范围过滤。适用场景:需要查看系统错误、诊断问题、审计安全事件时使用。""",
    "create_task": """创建Windows计划任务,定时执行脚本或程序。适用场景:需要定时备份、周期性维护、自动执行脚本时使用。""",
    "delete_task": """删除Windows计划任务。适用场景:需要移除不再需要的定时任务时使用。需谨慎操作。""",
    "list_tasks": """列出Windows计划任务,支持按名称和状态筛选。适用场景:需要查看所有定时任务、查找特定任务时使用。""",
    # 2026-10-02 小欧 - which 原样迁入(描述一字未改)
    "which": """查找系统命令的安装路径。适用场景:需要确认命令是否已安装、查看其安装路径时使用。""",
    # 2026-10-02 小欧 - sysinfo 原样迁入
    "sysinfo": """获取系统信息,包括操作系统、CPU、内存、磁盘和网络。适用场景:需要诊断系统问题(CPU高、内存不足、磁盘满)、了解硬件规格时使用。""",
}

SYSTEM_TOOL_INPUT_MODELS = {
    "event_log": EventLogInput,
    "create_task": CreateTaskInput,
    "delete_task": DeleteTaskInput,
    "list_tasks": ListTasksInput,
    "which": WhichInput,              # 2026-10-02 小欧
    "sysinfo": GetSystemInfoInput,    # 2026-10-02 小欧
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
    # 2026-10-02 小欧 - which/sysinfo 自 shell/fundamental 原样迁入
    "which": [
        {"command": "python"},
        {"command": "python", "all_paths": True},
        {"command": "git"},
        {"command": "npm"}
    ],
    "sysinfo": [
        {},
        {"info_type": "all"},
        {"info_type": "basic"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
        {"info_type": "disk"},
        {"info_type": "network"},
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
        # 2026-10-02 小欧 - 自 shell/fundamental 迁入; 本模块是 SYSTEM 唯一注册点
        "which": which,
        "sysinfo": sysinfo,
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
