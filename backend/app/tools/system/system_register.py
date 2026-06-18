# -*- coding: utf-8 -*-
"""
SYSTEM Register - 系统信息工具注册点

【架构规范】2026-04-29 小沈

【2026-05-18 小沈】继续精简:list_env合入get_env,reg×3合入registry_control
- 保留 get_system_info, event_log, list_processes, kill_process
- 保留 service_control, task_control
- 保留 get_env(action=get/list), set_env(action=set/delete)
- registry_control(action=read/write/delete)在reg_register.py注册
- net_connections迁入network分类(2026-06-09 小沈)
【2026-06-18 小健】添加SYSTEM_TOOL_DEPENDENCIES常量管理工具依赖

【工具列表】(LLM可见8个,本文件注册5个 + reg_register注册1个 + env迁入2个)
1. event_log - 获取系统事件日志 (依赖: psutil)
2. list_processes - 列出所有进程 (依赖: psutil)
3. kill_process - 终止指定进程 (依赖: psutil)
4. service_control - 服务统一控制(start/stop/restart/list) (依赖: psutil)
5. task_control - 计划任务统一控制(create/delete/list) (无第三方依赖)
+ get_env - 获取环境变量 (无第三方依赖)
+ set_env - 设置环境变量 (无第三方依赖)
+ reg_read, reg_write, reg_delete(reg_register.py注册)

【2026-06-18 小健】get_system_info移入FUNDAMENTAL分类

创建时间: 2026-04-29
更新时间: 2026-06-18 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 系统工具依赖配置 — 小健 2026-06-18
# 每个工具对应的第三方依赖包列表
SYSTEM_TOOL_DEPENDENCIES = {

    "event_log": ["psutil"],
    "list_processes": ["psutil"],
    "kill_process": ["psutil"],
    "service_control": ["psutil"],
    "task_control": [],  # 使用内置库
    "get_env": [],  # 使用内置os库
    "set_env": [],  # 使用内置os库
}

from app.tools.system.system_schema import (
    EventLogInput,
    ListProcessesInput,
    KillProcessInput,
    ServiceControlInput,
    CreateTaskInput,
    DeleteTaskInput,
    ListTasksInput,
    GetEnvInput,
    SetEnvInput,
)

from app.tools.system.system_tools import (
    event_log,
    list_processes,
    kill_process,
    service_control,
    create_task,
    delete_task,
    list_tasks,
)

from app.tools.system.env_tools import (
    get_env,
    set_env,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {

    "event_log": """获取系统事件日志。Windows使用wevtutil,Linux使用journalctl。支持日志名称(Application/System/Security)、事件级别(critical/error/warning/info)、时间范围(10m/1h/24h/7d)和来源应用名过滤。默认返回System日志,级别error,时间范围1h。适用场景:需要查看系统错误日志、诊断系统问题、审计系统安全事件时使用。""",
    "list_processes": """列出系统所有进程。支持按进程名(模糊匹配)、PID(精确匹配)和用户名过滤。可按CPU占用/内存占用/名称/PID排序。默认最多返回100条,按PID排序。适用场景:需要查看系统进程状态、查找资源占用高的进程、按名称定位特定进程时使用。""",
    "kill_process": """终止指定PID的进程。默认优雅终止(SIGTERM),超时后自动升级为强制终止(SIGKILL)。force=True跳过等待直接强制终止。进程已不存在时幂等返回成功(不报错)。适用场景:需要结束卡死或无响应的进程、释放被占用资源、强制终止无法正常关闭的进程时使用。需谨慎操作。""",
    "service_control": """系统服务控制工具。支持服务的启动、停止、重启和列表查询。适用场景:需要管理系统服务、查看服务状态时使用。""",
    "create_task": """创建Windows计划任务(.bat/.exe等)。必填参数:task_name(任务名)、command(命令或程序路径,如C:\\scripts\\backup.bat)、schedule(计划时间,格式HH:MM每日/HH:MM /day N每周/HH:MM /monthly DD每月)。可选参数:start_time(起始时间)、interval(重复间隔分钟数)。适用场景:需要定时执行脚本、定期备份、周期性维护任务时使用。""",
    "delete_task": """删除Windows计划任务。必填参数:task_name(要删除的计划任务名称)。删除前会先查询确认任务存在。适用场景:需要移除不再需要的计划任务时使用。需谨慎操作。""",
    "list_tasks": """列出Windows计划任务。可选参数:task_name(按名称模糊过滤)、state(状态过滤,ready/running/disabled/all,默认all)。适用场景:需要查看所有计划任务、按名称查找特定任务、按状态筛选任务时使用。""",
    "get_env": """环境变量获取工具。支持获取单个环境变量或列出所有环境变量。适用场景:需要查看环境变量值、检查配置时使用。""",
    "set_env": """环境变量设置工具。支持设置或删除环境变量。适用场景:需要配置环境变量、修改变量值时使用。""",
}

# 模型映射
SYSTEM_TOOL_INPUT_MODELS = {

    "event_log": EventLogInput,
    "list_processes": ListProcessesInput,
    "kill_process": KillProcessInput,
    "service_control": ServiceControlInput,
    "create_task": CreateTaskInput,
    "delete_task": DeleteTaskInput,
    "list_tasks": ListTasksInput,
    "get_env": GetEnvInput,
    "set_env": SetEnvInput,
}

# 使用示例
SYSTEM_TOOL_EXAMPLES = {

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
    "service_control": [
        {"action": "list"},
        {"action": "list", "state": "running"},
        {"action": "start", "service_name": "mysql"},
        {"action": "stop", "service_name": "nginx", "force": True},
        {"action": "restart", "service_name": "mysql"},
    ],
    "create_task": [
        {"task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"},
        {"task_name": "WeeklyReport", "command": "C:\\scripts\\report.bat", "schedule": "08:00 /day 1", "start_time": "08:00"},
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
    # 【2026-05-19 小沈】Environment工具示例(已精简:砍default/include_system/exist_ok)
    "get_env": [
        {"name": "PATH"},
        {"action": "list"},
        {"action": "list", "prefix": "PY"},
    ],
    "set_env": [
        {"name": "MY_VAR", "value": "hello"},
        {"name": "PATH", "value": "C:\\tools", "append_mode": True},
    ],
}


def _register_system_tools():
    """注册系统工具 — 全部归入SYSTEM — 小欧 2026-06-12"""
    # 【2026-06-16 小沈】二元安全配置（替代5级枚举）
    CONFIRM_TOOLS = {"kill_process", "service_control", "create_task", "delete_task", "set_env"}

    system_tools = {

        "event_log": event_log,
        "list_processes": list_processes,
        "get_env": get_env,
        "kill_process": kill_process,
        "service_control": service_control,
        "create_task": create_task,
        "delete_task": delete_task,
        "list_tasks": list_tasks,
        "set_env": set_env,
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
