# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

【2026-05-18 小沈】继续精简：10→7工具
- list_env合入get_env(action="list")
- reg_read/reg_write/reg_delete合入registry_control(action路由)
- Env_Check 5个验证工具降级为document内部helper(§13.3.4)

【2026-05-19 小沈】参数精简：
- NetConnectionsInput: 5→4(砍resolve_dns暂未生效)
- EventLogInput: 6→5(砍event_id暂未生效)
- ListProcessesInput: 7→5(砍descending+status)
- ServiceControlInput: 7→5(砍wait_for_started+wait_for_stopped)
- TaskControlInput: 9→7(砍start_date+folder)
- GetEnvInput: 7→5(砍default+include_system)
- SetEnvInput: 6→5(砍exist_ok)

工具列表（7个LLM可见 + 3个Environment迁入 + 1个Registry迁入）：
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程
6. service_control - 服务统一控制(start/stop/restart/list)
7. task_control - 计划任务统一控制(create/delete/list)
8. get_env - 获取/列出环境变量(action=get/list)
9. set_env - 设置/删除环境变量(action=set/delete)
10. registry_control - 注册表统一控制(action=read/write/delete)

Author: 小沈 - 2026-04-29
更新时间: 2026-05-03 小沈 - 修正参数description，准确清晰完整
更新时间: 2026-05-17 小沈 - 16→10工具重构
更新时间: 2026-05-19 小沈 - 参数精简
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any


class GetSystemInfoInput(BaseModel):
    """get_system_info 工具的输入参数 - 小沈 2026-05-03 修正"""
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all",
        description="要获取的系统信息类型，默认all。basic=OS/主机名/架构等，cpu=核心数/频率/使用率，memory=总量/可用/使用率，disk=各分区空间/使用率，network=接口名/IP/MAC，all=以上全部"
    )


class NetConnectionsInput(BaseModel):
    """net_connections 工具的输入参数 - 小沈 2026-05-19 参数精简5→4(砍resolve_dns暂未生效)"""
    kind: Literal["inet", "tcp", "udp"] = Field(
        default="inet",
        description="连接类型：inet=TCP+UDP(默认)，tcp=仅TCP，udp=仅UDP"
    )
    state: Optional[Literal["established", "listen", "time_wait", "close_wait"]] = Field(
        default=None,
        description="连接状态过滤，不设则返回所有状态。established=已建立，listen=监听中，time_wait=等待中，close_wait=关闭等待"
    )
    process_info: bool = Field(
        default=False,
        description="是否获取关联进程信息（进程名和PID），默认False"
    )
    filter_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="过滤指定端口号(1-65535)，只返回与该端口相关的连接"
    )


class EventLogInput(BaseModel):
    """event_log 工具的输入参数 - 小沈 2026-05-19 参数精简6→5(砍event_id暂未生效)"""
    log_name: Literal["Application", "System", "Security"] = Field(
        default="System",
        description="日志名称，默认System。System=系统日志，Application=应用日志，Security=安全日志"
    )
    max_events: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大返回事件数，默认50"
    )
    level: Optional[Literal["critical", "error", "warning", "info"]] = Field(
        default="error",
        description="日志级别过滤，默认error。可选critical/error/warning/info"
    )
    source: Optional[str] = Field(
        default=None,
        description="事件来源/应用名过滤，可选"
    )
    time_range: Literal["10m", "1h", "24h", "7d"] = Field(
        default="1h",
        description="时间范围过滤，默认1h。可选10m/1h/24h/7d"
    )


class ListProcessesInput(BaseModel):
    """list_processes 工具的输入参数 - 小沈 2026-05-19 参数精简7→5(砍descending+status)"""
    filter_name: Optional[str] = Field(
        default=None,
        description="按进程名过滤（模糊匹配）"
    )
    filter_pid: Optional[int] = Field(
        default=None,
        ge=1,
        description="按PID过滤"
    )
    user: Optional[str] = Field(
        default=None,
        description="用户名过滤（模糊匹配）"
    )
    sort_by: Literal["pid", "name", "cpu", "memory"] = Field(
        default="pid",
        description="排序方式。可选值：pid(默认)、name、cpu、memory"
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="最大返回进程数，默认100"
    )


class KillProcessInput(BaseModel):
    """kill_process 工具的输入参数 - 按文档7.5节定义"""
    pid: int = Field(
        ...,
        ge=1,
        description="进程ID（必填）。如 1234"
    )
    force: bool = Field(
        default=False,
        description="是否强制终止进程。默认False"
    )
    timeout: int = Field(
        default=5,
        ge=1,
        le=60,
        description="等待进程终止的超时时间（秒），默认5秒"
    )


# 【2026-05-18 小健】已废弃Schema已删除：
# ServiceListInput/ServiceStartInput/ServiceStopInput → 合并入 ServiceControlInput
# TaskListInput/TaskCreateInput/TaskDeleteInput → 合并入 TaskControlInput


# 【2026-05-17 小沈】新增：ServiceControlInput - 服务统一控制入口
class ServiceControlInput(BaseModel):
    """service_control 工具的输入参数 - 小沈 2026-05-19 参数精简7→5(砍wait_for_started+wait_for_stopped)
    合并 service_start/service_stop/service_list，通过action分发
    """
    action: Literal["start", "stop", "restart", "list"] = Field(
        ...,
        description="操作类型（必填）。可选值：start/stop/restart/list"
    )
    service_name: Optional[str] = Field(
        default=None,
        description="服务名称。start/stop/restart时必填；list时可选（用于名称过滤）。如 MySQL、nginx"
    )
    state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="服务状态过滤（仅list时使用）。可选值：running/stopped/all（默认）"
    )
    force: bool = Field(
        default=False,
        description="是否强制停止（仅stop/restart时使用）。默认false。force=true时Windows用taskkill，Linux用systemctl kill"
    )
    timeout: int = Field(
        default=30, ge=1, le=300,
        description="等待服务操作的超时时间（秒）。默认30秒"
    )


# 【2026-05-17 小沈】新增：TaskControlInput - 计划任务统一控制入口
class TaskControlInput(BaseModel):
    """task_control 工具的输入参数 - 小沈 2026-05-19 参数精简9→7(砍start_date+folder)
    合并 task_create/task_delete/task_list，通过action分发
    """
    action: Literal["create", "delete", "list"] = Field(
        ...,
        description="操作类型（必填）。可选值：create/delete/list"
    )
    task_name: Optional[str] = Field(
        default=None,
        description="任务名称。create/delete时必填；list时可选（用于名称过滤）"
    )
    command: Optional[str] = Field(
        default=None,
        description="要执行的命令或程序路径（仅create时必填）。如 C:\\scripts\\backup.bat"
    )
    schedule: Optional[str] = Field(
        default=None,
        description="计划执行时间（仅create时必填）。格式：'HH:MM'(每日)、'HH:MM /day N'(每周)、'HH:MM /monthly DD'(每月)"
    )
    start_time: Optional[str] = Field(
        default=None,
        description="起始时间（仅create时可选）。如 '08:00'"
    )
    interval: Optional[int] = Field(
        default=None,
        description="重复间隔分钟数（仅create时可选）"
    )
    state: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all",
        description="状态过滤（仅list时使用）。可选值：ready/running/disabled/all（默认）"
    )


# 【2026-05-18 小沈】新增：Environment 工具 Schema（从environment模块迁入）
class GetEnvInput(BaseModel):
    """get_env 工具的输入参数 - 小沈 2026-05-19 参数精简7→5(砍default+include_system)
    合并list_env，action="get"|"list"
    """
    name: Optional[str] = Field(default=None, description="环境变量名称（action=\"get\"时必填）。如 \"PATH\"、\"HOME\"、\"JAVA_HOME\"")
    scope: Literal["process", "user", "system"] = Field(default="process", description="作用域。可选值：process/user/system。默认process")
    expand_vars: bool = Field(default=True, description="是否展开值中的嵌套变量（如 %JAVA_HOME%\\bin）。默认true")
    action: Literal["get", "list"] = Field(default="get", description="操作类型。\"get\"=获取单个变量（默认），\"list\"=列出所有变量")
    prefix: Optional[str] = Field(default=None, description="环境变量名前缀过滤（仅action=\"list\"有效）。例如 PY、JAVA")


class SetEnvInput(BaseModel):
    """set_env 工具的输入参数 - 小沈 2026-05-19 参数精简6→5(砍exist_ok)"""
    name: str = Field(..., description="环境变量名称。如 \"MY_VARIABLE\"、\"CONFIG_PATH\"、\"PATH\"")
    value: Optional[str] = Field(default=None, description="环境变量值。action=\"set\"时必填，action=\"delete\"时忽略")
    scope: Literal["user", "system", "process"] = Field(default="process", description="作用域。可选值：process/user/system。默认process")
    append_mode: bool = Field(default=False, description="追加模式。若 name 为 PATH 或 CLASSPATH，Agent 自动设true。默认false")
    action: Literal["set", "delete"] = Field(default="set", description="操作类型。\"set\"=设置变量（默认），\"delete\"=删除变量")


__all__ = [
    "GetSystemInfoInput",
    "NetConnectionsInput",
    "EventLogInput",
    "ListProcessesInput",
    "KillProcessInput",
    "ServiceControlInput",
    "TaskControlInput",
    "GetEnvInput",
    "SetEnvInput",
]