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
    TaskControlInput,
    GetEnvInput,
    SetEnvInput,
)

from app.services.tools.system.system_tools import (
    get_system_info,
    event_log,
    list_processes,
    kill_process,
    service_control,
    task_control,
)

from app.services.tools.system.env_tools import (
    get_env,
    set_env,
)

# 工具描述
SYSTEM_TOOL_DESCRIPTIONS = {
    "get_system_info": """获取系统完整信息,包括操作系统、CPU、内存、磁盘、网络接口等硬件和系统配置信息。

使用场景:
- 当用户需要查看系统配置信息时使用
- 当用户需要诊断系统问题(如CPU占用、内存不足、磁盘空间)时使用
- 当用户需要了解系统硬件规格(CPU核数、内存容量、磁盘分区)时使用

使用示例:【常用名转换说明】
- 全部信息 → get_system_info(info_type="all")
- CPU信息/get_cpu_info → get_system_info(info_type="cpu")
- 内存信息/get_memory_info → get_system_info(info_type="memory")
- 磁盘空间/get_disk_usage → get_system_info(info_type="disk")
- 网络信息/get_network_info → get_system_info(info_type="network")

返回数据说明
【重要】返回按info_type分类的系统信息,all类型返回全部
 - data: 成功时含basic/cpu/memory/disk/network;按info_type返回对应子集""",
    "event_log": """获取系统事件日志(Windows事件查看器/Linux syslog),支持按级别、来源、时间范围过滤。

使用场景:
- 当用户需要查看系统错误日志时使用
- 当用户需要诊断系统问题时使用
- 当用户需要审计系统事件时使用

【重要】Windows用wevtutil,Linux用journalctl;支持10m/1h/24h/7d时间范围

使用示例:
- 获取最近1小时错误日志:{}
- 获取Application日志20条:{"log_name": "Application", "max_events": 20}
- 获取最近24小时错误:{"level": "error", "time_range": "24h"}

返回数据说明:
- code: 状态码,SUCCESS/ERR_SYSTEM_EVENT_LOG/ERR_SYSTEM_TIMEOUT/ERR_SYSTEM_COMMAND_NOT_FOUND
- data: 成功时含log_name/events/total/level;失败时为null
- message: 状态描述信息""",
    "list_processes": """列出系统所有进程,支持按filter_name/filter_pid过滤,可按CPU/内存占用排序。

使用场景:
- 当用户需要查看系统进程状态时使用
- 当用户需要查找资源占用高的进程时使用
- 当用户需要按名称查找特定进程时使用

【重要】默认按pid排序,可按cpu/memory排序;默认最多返回100条

使用示例:
- 列出所有进程:{}
- 按名称过滤:{"filter_name": "python"}
- 按内存排序:{"filter_name": "python", "sort_by": "memory", "max_results": 20}

返回数据说明:
- code: 状态码,SUCCESS/ERR_SYSTEM_PROCESS_LIST
- data: 成功时含processes/total/total_matched/sort_by;失败时为null
- message: 状态描述信息""",
    "kill_process": """终止指定进程(pid必填),支持优雅终止(SIGTERM)和强制终止(SIGKILL),需谨慎使用。

使用场景:
- 当用户需要结束卡死或无响应的进程时使用
- 当用户需要释放被占用资源时使用
- 当用户需要强制终止无法正常关闭的进程时使用

【重要】默认优雅终止(SIGTERM),超时后自动升级为强制终止(SIGKILL);进程已不存在时幂等返回SUCCESS

使用示例:
- 终止进程:{"pid": 1234}
- 强制终止:{"pid": 1234, "force": true}

返回数据说明:
- code: 状态码,SUCCESS/ERR_INVALID_PARAM/ERR_PERMISSION_DENIED/ERR_PERMISSION_DENIED/ERR_SYSTEM_PROCESS_KILL
- data: 成功时含killed(已终止列表);进程不存在时含idempotent=true;失败时为null
- message: 状态描述信息""",
    "service_control": """支持系统服务的start/stop/restart/list操作功能。
action参数决定操作类型:
- start: 启动服务,service_name(可选timeout)
- stop: 停止服务,service_name(可选force/timeout)
- restart: 重启服务,service_name(可选force/timeout)
- list: 列出服务(可选state过滤)

使用示例:
- 列出服务 → service_control(action="list")
- 启动服务 → service_control(action="start", service_name="mysql")
- 停止服务 → service_control(action="stop", service_name="nginx")
- 重启服务 → service_control(action="restart", service_name="apache")""",
    "task_control": """支持Windows计划任务的create/delete/list操作功能。
action参数决定操作类型:
- create: 创建任务,task_name+command+schedule(可选start_time/interval)
- delete: 删除任务,task_name
- list: 列出任务(可选state过滤)

使用示例:
- 列出任务 → task_control(action="list")
- 创建任务 → task_control(action="create", task_name="MyBackup", command="C:\\scripts\\backup.bat", schedule="02:00")
- 删除任务 → task_control(action="delete", task_name="MyBackup")""",
    "get_env": """支持环境变量的获取/列出操作功能。
action参数决定操作类型:
- get: 获取单个环境变量,name(必填;可选scope/expand_vars)
- list: 列出所有环境变量(可选prefix/scope)

使用示例:
- 获取单个 → get_env(name="PATH")
- 列出所有 → get_env(action="list")""",
    "set_env": """支持环境变量的设置/删除操作功能。
action参数决定操作类型:
- set: 设置环境变量,name+value(可选scope/append_mode)
- delete: 删除环境变量,name(可选scope)

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
    "task_control": TaskControlInput,
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
    "task_control": [
        {"action": "list"},
        {"action": "list", "state": "running"},
        {"action": "create", "task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"},
        {"action": "delete", "task_name": "MyBackup"},
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
    """注册系统工具 — 查询类归FUND_RUNTIME,管理类归NET_PROCESS — 小沈 2026-06-09"""
    fund_runtime_tools = {
        "get_system_info": get_system_info,
        "event_log": event_log,
        "list_processes": list_processes,
        "get_env": get_env,
    }
    net_process_tools = {
        "kill_process": kill_process,
        "service_control": service_control,
        "task_control": task_control,
        "set_env": set_env,
    }

    for name, method in fund_runtime_tools.items():
        desc = SYSTEM_TOOL_DESCRIPTIONS.get(name, "")
        input_model = SYSTEM_TOOL_INPUT_MODELS.get(name)
        examples = SYSTEM_TOOL_EXAMPLES.get(name, [])
        tool_registry.register(
            name=name, description=desc, category=ToolCategory.FUND_RUNTIME,
            implementation=method, version="1.0.0", input_model=input_model, examples=examples,
        )
        logger.info(f"[system_register] 已注册工具(FUND_RUNTIME): {name}")

    for name, method in net_process_tools.items():
        desc = SYSTEM_TOOL_DESCRIPTIONS.get(name, "")
        input_model = SYSTEM_TOOL_INPUT_MODELS.get(name)
        examples = SYSTEM_TOOL_EXAMPLES.get(name, [])
        tool_registry.register(
            name=name, description=desc, category=ToolCategory.NET_PROCESS,
            implementation=method, version="1.0.0", input_model=input_model, examples=examples,
        )
        logger.info(f"[system_register] 已注册工具(NET_PROCESS): {name}")

    # 【修复 2026-05-18 小沈】调用reg_register注册reg_read/reg_write/reg_delete
    from app.services.tools.system.reg_register import _register_registry_tools
    _register_registry_tools()



__all__ = ["_register_system_tools"]
