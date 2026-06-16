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

【工具列表】(LLM可见9个,本文件注册6个 + reg_register注册1个 + env迁入2个)
1. get_system_info - 获取系统信息
2. event_log - 获取系统事件日志
3. list_processes - 列出所有进程
4. kill_process - 终止指定进程
5. service_control - 服务统一控制(start/stop/restart/list)
6. task_control - 计划任务统一控制(create/delete/list)
+ reg_read, reg_write, reg_delete(reg_register.py注册)

创建时间: 2026-04-29
更新时间: 2026-05-17 小沈 - 16→10工具重构
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.system.system_schema import (
    GetSystemInfoInput,
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

from app.services.tools.system.system_tools import (
    get_system_info,
    event_log,
    list_processes,
    kill_process,
    service_control,
    create_task,
    delete_task,
    list_tasks,
)

from app.services.tools.system.env_tools import (
    get_env,
    set_env,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {
    "get_system_info": """获取系统完整信息,支持按类型获取:info_type="basic"(OS/主机名/架构)、"cpu"(核心数/频率/使用率)、"memory"(总量/可用/使用率)、"disk"(各分区空间/使用率)、"network"(IO计数器)、"all"(以上全部,默认)。适用场景:需要诊断系统问题(CPU占用高、内存不足、磁盘空间满)、了解系统硬件规格时使用。""",
    "event_log": """获取系统事件日志。Windows使用wevtutil,Linux使用journalctl。支持日志名称(Application/System/Security)、事件级别(critical/error/warning/info)、时间范围(10m/1h/24h/7d)和来源应用名过滤。默认返回System日志,级别error,时间范围1h。适用场景:需要查看系统错误日志、诊断系统问题、审计系统安全事件时使用。""",
    "list_processes": """列出系统所有进程。支持按进程名(模糊匹配)、PID(精确匹配)和用户名过滤。可按CPU占用/内存占用/名称/PID排序。默认最多返回100条,按PID排序。适用场景:需要查看系统进程状态、查找资源占用高的进程、按名称定位特定进程时使用。""",
    "kill_process": """终止指定PID的进程。默认优雅终止(SIGTERM),超时后自动升级为强制终止(SIGKILL)。force=True跳过等待直接强制终止。进程已不存在时幂等返回成功(不报错)。适用场景:需要结束卡死或无响应的进程、释放被占用资源、强制终止无法正常关闭的进程时使用。需谨慎操作。""",
    "service_control": """支持系统服务的start/stop/restart/list操作功能。
action参数决定操作类型:
- start: 启动服务,service_name【必填】(可选timeout)
- stop: 停止服务,service_name【必填】(可选force/timeout)
- restart: 重启服务,service_name【必填】(可选force/timeout)
- list: 列出服务(可选state/service_name过滤)

使用示例:
- 列出服务 → service_control(action="list")
- 启动服务 → service_control(action="start", service_name="mysql")
- 停止服务 → service_control(action="stop", service_name="nginx")
- 重启服务 → service_control(action="restart", service_name="apache")""",
    "create_task": """创建Windows计划任务(.bat/.exe等)。必填参数:task_name(任务名)、command(命令或程序路径,如C:\\scripts\\backup.bat)、schedule(计划时间,格式HH:MM每日/HH:MM /day N每周/HH:MM /monthly DD每月)。可选参数:start_time(起始时间)、interval(重复间隔分钟数)。适用场景:需要定时执行脚本、定期备份、周期性维护任务时使用。""",
    "delete_task": """删除Windows计划任务。必填参数:task_name(要删除的计划任务名称)。删除前会先查询确认任务存在。适用场景:需要移除不再需要的计划任务时使用。需谨慎操作。""",
    "list_tasks": """列出Windows计划任务。可选参数:task_name(按名称模糊过滤)、state(状态过滤,ready/running/disabled/all,默认all)。适用场景:需要查看所有计划任务、按名称查找特定任务、按状态筛选任务时使用。""",
    "get_env": """支持环境变量的获取/列出操作功能。
action参数决定操作类型:
- get: 获取单个环境变量,name【必填】(可选scope/expand_vars)
- list: 列出所有环境变量(可选prefix/scope)

使用示例:
- 获取单个 → get_env(name="PATH")
- 列出所有 → get_env(action="list")""",
    "set_env": """支持环境变量的设置/删除操作功能。
action参数决定操作类型:
- set: 设置环境变量,name【必填】+value【必填】(可选scope/append_mode)
- delete: 删除环境变量,name【必填】(可选scope)

使用示例:
- 设置变量 → set_env(name="MY_VAR", value="my_value")
- 删除变量 → set_env(action="delete", name="MY_VAR")""",
}

# 模型映射
SYSTEM_TOOL_INPUT_MODELS = {
    "get_system_info": GetSystemInfoInput,
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
    "get_system_info": [
        {"info_type": "all"},
        {"info_type": "cpu"},
        {"info_type": "memory"},
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
        "get_system_info": get_system_info,
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
        )
        logger.info(f"[system_register] 已注册工具(SYSTEM): {name}")

    # 【修复 2026-05-18 小沈】调用reg_register注册reg_read/reg_write/reg_delete
    from app.services.tools.system.reg_register import _register_registry_tools
    _register_registry_tools()



__all__ = ["_register_system_tools"]
