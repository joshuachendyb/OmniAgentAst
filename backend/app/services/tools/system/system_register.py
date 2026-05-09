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
更新时间: 2026-05-09
"""

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
    "get_system_info": """获取系统完整信息，包括操作系统、CPU、内存、磁盘、网络接口等硬件和系统配置信息。

使用场景：
- 当用户需要查看系统配置信息时使用
- 当用户需要诊断系统问题（如CPU占用、内存不足、磁盘空间）时使用
- 当用户需要了解系统硬件规格（CPU核数、内存容量、磁盘分区）时使用

【重要】返回按info_type分类的系统信息，all类型返回全部

使用示例：
- 获取全部信息：{"info_type": "all"}
- 仅获取CPU：{"info_type": "cpu"}
- 仅获取内存：{"info_type": "memory"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SYSTEM_INFO
- data: 成功时含basic(platform/architecture/hostname/python_version等)、cpu(physical_cores/logical_cores/current_frequency_mhz/cpu_usage_percent等)、memory(total_gb/available_gb/used_gb/percent)、disk(设备列表含device/mountpoint/filesystem/total_gb/used_gb/free_gb/percent)、network(bytes_sent_mb/bytes_recv_mb/packets_sent/packets_recv)；按info_type返回对应子集；失败时为null
- message: 状态描述信息""",
    "net_connections": """获取网络连接列表，支持按类型（TCP/UDP）、状态（ESTABLISHED/LISTEN）、端口过滤，可获取关联进程信息。

使用场景：
- 当用户需要查看当前网络连接时使用
- 当用户需要排查端口占用问题时使用
- 当用户需要查看某个端口的连接状态时使用

【重要】最多返回200条连接记录；process_info=True可获取关联进程名和路径

使用示例：
- 查看所有连接：{}
- 查看TCP已建立连接：{"kind": "tcp", "state": "established"}
- 查看端口8080的连接：{"filter_port": 8080, "process_info": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SYSTEM_ACCESS_DENIED/ERR_SYSTEM_NET_CONN
- data: 成功时含connections(连接列表，每项含fd/family/type/local_address/remote_address/status/pid，process_info=true时额外含process_name/process_exe)、total(连接总数)、kind(连接类型)、filter_port(过滤端口)；失败时为null
- message: 状态描述信息""",
    "event_log": """获取系统事件日志（Windows事件查看器/Linux syslog），支持按级别、来源、时间范围过滤。

使用场景：
- 当用户需要查看系统错误日志时使用
- 当用户需要诊断系统问题时使用
- 当用户需要审计系统事件时使用

【重要】Windows用wevtutil，Linux用journalctl；支持10m/1h/24h/7d时间范围

使用示例：
- 获取最近1小时错误日志：{}
- 获取Application日志20条：{"log_name": "Application", "max_events": 20}
- 获取最近24小时错误：{"level": "error", "time_range": "24h"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SYSTEM_EVENT_LOG/ERR_SYSTEM_TIMEOUT/ERR_SYSTEM_COMMAND_NOT_FOUND
- data: 成功时含log_name(日志名称)、events(事件列表，Windows每项含Level/Source Name等字段，Linux每项含timestamp/hostname/syslog_identifier/message/priority)、total(事件数)、level(级别过滤)；失败时为null
- message: 状态描述信息""",
    "list_processes": """列出系统所有进程，支持按filter_name/filter_pid过滤，可按CPU/内存占用排序。

使用场景：
- 当用户需要查看系统进程状态时使用
- 当用户需要查找资源占用高的进程时使用
- 当用户需要按名称查找特定进程时使用

【重要】默认按pid排序，可按cpu/memory排序；默认最多返回100条

使用示例：
- 列出所有进程：{}
- 按名称过滤：{"filter_name": "python"}
- 按内存排序：{"filter_name": "python", "sort_by": "memory", "max_results": 20}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SYSTEM_PROCESS_LIST
- data: 成功时含processes(进程列表，每项含pid/name/status/user/cpu_percent/memory_percent/exe/cmdline)、total(返回数量)、total_matched(匹配总数)、sort_by(排序字段)；失败时为null
- message: 状态描述信息""",
    "kill_process": """终止指定进程(pid必填)，支持优雅终止（SIGTERM）和强制终止（SIGKILL），需谨慎使用。

使用场景：
- 当用户需要结束卡死或无响应的进程时使用
- 当用户需要释放被占用资源时使用
- 当用户需要强制终止无法正常关闭的进程时使用

【重要】默认优雅终止(SIGTERM)，超时后自动升级为强制终止(SIGKILL)；需要管理员权限终止某些进程

使用示例：
- 终止进程：{"pid": 1234}
- 强制终止：{"pid": 1234, "force": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_INVALID_PARAM/ERR_PROCESS_NOT_FOUND/ERR_PERMISSION_DENIED/ERR_SYSTEM_ACCESS_DENIED/ERR_SYSTEM_PROCESS_KILL
- data: 成功时含killed(已终止列表，每项含process(pid/name/status/exe)、terminate_type(终止方式)、final_status(最终状态))；失败时为null
- message: 状态描述信息""",
    "log_message": """记录日志消息到指定日志文件或日志系统。

使用场景：
- 当用户需要记录操作日志时使用
- 当用户需要记录审计信息时使用
- 当用户需要记录调试信息时使用

【重要】使用Python内置logging模块；不指定log_file时输出到控制台

使用示例：
- 记录INFO日志：{"message": "用户登录成功"}
- 记录WARNING日志：{"level": "WARNING", "message": "磁盘空间不足"}
- 记录到文件：{"message": "系统启动", "log_file": "D:/logs/app.log"}

返回数据说明：
- code: 状态码，SUCCESS/ERROR
- data: 成功时含level(日志级别)、message(消息内容)、logger_name(记录器名称)、log_file(日志文件路径，null表示控制台)、timestamp(记录时间)；失败时为null
- message: 状态描述信息""",
    "get_logs": """读取指定日志文件的内容，支持智能过滤与截断。

使用场景：
- 当用户需要查看日志文件内容时使用
- 当用户需要分析历史日志时使用
- 当用户需要排查问题查看错误日志时使用

【重要】tail_mode启用时从文件末尾读取，此时跳过level/pattern过滤

使用示例：
- 读取日志文件：{"log_file": "D:/logs/app.log"}
- 过滤ERROR级别：{"log_file": "D:/logs/app.log", "level": "ERROR", "max_lines": 100}
- 尾部读取并过滤关键词：{"log_file": "D:/logs/app.log", "pattern": "timeout", "tail_mode": true}
- 按时间范围过滤：{"log_file": "D:/logs/app.log", "start_time": "2026-01-01", "end_time": "2026-01-02", "output_format": "json"}

返回数据说明：
- code: 状态码，SUCCESS/ERROR
- data: 成功时含logs(日志行列表)、total(日志行数)、file(日志文件路径)、tail_mode(是否尾部模式)；文件不存在时为null
- message: 状态描述信息""",
    "service_list": """列出系统服务（Windows用sc/Linux用systemctl），支持按名称和状态（running/stopped）过滤。

使用场景：
- 当用户需要查看系统服务状态时使用
- 当用户需要查找特定服务时使用
- 当用户需要检查某个服务是否运行时使用

【重要】Windows用sc query，Linux用systemctl list-units；默认最多返回100条

使用示例：
- 列出所有服务：{}
- 查看运行中的服务：{"state": "running"}
- 按名称过滤：{"name": "mysql", "state": "running"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SERVICE_LIST/ERR_SERVICE_TIMEOUT/ERR_SERVICE_COMMAND_NOT_FOUND
- data: 成功时含services(服务列表，每项含name/display_name/state/state_desc)、total(返回数量)、total_matched(匹配总数)、platform(平台)；失败时为null
- message: 状态描述信息""",
    "service_start": """启动指定系统服务（Windows用sc/Linux用systemctl），支持超时设置。

使用场景：
- 当用户需要启动已停止的服务时使用
- 当用户需要重启服务时使用（先停后启）
- 当用户需要确保服务处于运行状态时使用

【重要】Windows用sc start，Linux用systemctl start；启动后会自动检查服务状态

使用示例：
- 启动服务：{"service_name": "mysql"}
- 启动并等待：{"service_name": "nginx", "wait_for_started": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SERVICE_NOT_FOUND/ERR_SERVICE_START/ERR_SERVICE_TIMEOUT
- data: 成功时含service_name(服务名称)、state(当前状态running/stopped/unknown)、action(执行动作start/none)；失败时为null
- message: 状态描述信息""",
    "service_stop": """停止指定系统服务（Windows用sc/Linux用systemctl），支持优雅停止和强制停止。

使用场景：
- 当用户需要停止运行中的服务时使用
- 当用户需要停止异常服务时使用
- 当用户需要强制停止无法正常停止的服务时使用

【重要】Windows用sc stop，Linux用systemctl stop；force=true时Windows用taskkill强制停止，Linux用systemctl kill

使用示例：
- 停止服务：{"service_name": "mysql"}
- 强制停止：{"service_name": "nginx", "force": true}
- 强制停止并等待：{"service_name": "mysql", "force": true, "wait_for_stopped": true}

返回数据说明：
- code: 状态码，SUCCESS/ERR_SERVICE_NOT_FOUND/ERR_SERVICE_STOP/ERR_SERVICE_TIMEOUT
- data: 成功时含service_name(服务名称)、state(当前状态running/stopped/unknown)、action(执行动作stop/none)、stop_type(停止类型优雅停止/强制停止)；失败时为null
- message: 状态描述信息""",
    "task_list": """列出所有计划任务（Windows专用，使用schtasks），支持按名称和状态过滤。

使用场景：
- 当用户需要查看定时任务配置时使用
- 当用户需要检查计划任务运行状态时使用
- 当用户需要确认某个计划任务是否存在时使用

【重要】仅支持Windows系统；使用schtasks /query命令

使用示例：
- 列出所有计划任务：{}
- 查看运行中的任务：{"state": "running"}
- 按文件夹过滤：{"folder": "\\Microsoft", "state": "ready"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_PLATFORM_NOT_SUPPORTED/ERR_TASK_LIST/ERR_TASK_EMPTY/ERR_TASK_TIMEOUT/ERR_TASK_COMMAND_NOT_FOUND
- data: 成功时含tasks(任务列表，每项含name/next_run/status/status_desc/command)、total(返回数量)、total_matched(匹配总数)、platform(平台Windows)、output_format(输出格式)；失败时为null
- message: 状态描述信息""",
    "task_create": """创建计划任务（Windows专用），支持每日/每周/每月调度，可设置启动程序和参数。

使用场景：
- 当用户需要创建定时备份任务时使用
- 当用户需要创建定时检查任务时使用
- 当用户需要创建周期性执行脚本的任务时使用

【重要】仅支持Windows系统；schedule格式：'HH:MM'(每日)、'HH:MM /day N'(每周)、'HH:MM /monthly DD'(每月)

使用示例：
- 创建每日凌晨2点备份：{"task_name": "MyBackup", "command": "C:\\scripts\\backup.bat", "schedule": "02:00"}
- 创建每周一9点报告：{"task_name": "WeeklyReport", "command": "python C:\\scripts\\report.py", "schedule": "09:00 /day 1", "start_time": "09:00"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_PLATFORM_NOT_SUPPORTED/ERR_TASK_CREATE/ERR_TASK_TIMEOUT/ERR_TASK_COMMAND_NOT_FOUND
- data: 成功时含task_name(任务名称)、command(执行命令)、schedule(调度计划)、description(描述)、user(运行用户)；失败时为null
- message: 状态描述信息""",
    "task_delete": """删除计划任务（Windows专用），使用schtasks delete命令，支持强制删除。

使用场景：
- 当用户需要清理无用的定时任务时使用
- 当用户需要删除错误的计划任务时使用
- 当用户需要重新配置计划任务时使用（先删后建）

【重要】仅支持Windows系统；删除前会先查询确认任务存在；/f参数自动强制删除

使用示例：
- 删除计划任务：{"task_name": "MyBackup"}
- 删除指定文件夹下的任务：{"task_name": "OldTask", "folder": "\\Microsoft"}

返回数据说明：
- code: 状态码，SUCCESS/ERR_PLATFORM_NOT_SUPPORTED/ERR_TASK_NOT_FOUND/ERR_TASK_DELETE/ERR_TASK_TIMEOUT/ERR_TASK_COMMAND_NOT_FOUND
- data: 成功时含task_name(任务全名)、folder(所在文件夹)、delete_type(删除类型普通删除/强制删除)；失败时为null
- message: 状态描述信息""",
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
        {"service_name": "mysql", "force": True, "wait_for_stopped": True},
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


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    _register_system_tools()
    _initialized = True
