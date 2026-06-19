# -*- coding: utf-8 -*-
"""
SYSTEM Schema - 系统工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

工具列表(7个LLM可见 + 3个Environment迁入 + 1个Registry迁入):
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
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any


class GetSystemInfoInput(BaseModel):
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all",
        description="系统信息类型:basic(基础)/cpu/内存/磁盘/网络/all(全部,默认)"
    )


class NetConnectionsInput(BaseModel):
    kind: Literal["inet", "tcp", "udp"] = Field(
        default="inet",
        description="连接类型:inet=TCP+UDP(默认),tcp=仅TCP,udp=仅UDP"
    )
    state: Optional[Literal["established", "listen", "time_wait", "close_wait"]] = Field(
        default=None,
        description="连接状态过滤,不设则返回所有状态。established=已建立,listen=监听中,time_wait=等待中,close_wait=关闭等待"
    )
    process_info: bool = Field(
        default=False,
        description="是否获取关联进程信息(进程名和PID),默认False"
    )
    filter_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="过滤指定端口号(1-65535),只返回与该端口相关的连接"
    )


class EventLogInput(BaseModel):
    log_name: Literal["Application", "System", "Security"] = Field(
        default="System",
        description="日志名称,默认System。System=系统日志,Application=应用日志,Security=安全日志"
    )
    max_events: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大返回事件数,默认50"
    )
    level: Optional[Literal["critical", "error", "warning", "info"]] = Field(
        default="error",
        description="日志级别过滤,默认error。可选critical/error/warning/info"
    )
    source: Optional[str] = Field(
        default=None,
        description="事件来源/应用名过滤,可选"
    )
    time_range: Literal["10m", "1h", "24h", "7d"] = Field(
        default="1h",
        description="时间范围过滤,默认1h。可选10m/1h/24h/7d"
    )


class ListProcessesInput(BaseModel):
    filter_name: Optional[str] = Field(
        default=None,
        description="按进程名过滤(模糊匹配)"
    )
    filter_pid: Optional[int] = Field(
        default=None,
        ge=1,
        description="按进程PID精确过滤。只返回PID等于此值的进程信息。不填或填None则返回所有进程"
    )
    user: Optional[str] = Field(
        default=None,
        description="用户名过滤(模糊匹配)"
    )
    sort_by: Literal["pid", "name", "cpu", "memory"] = Field(
        default="pid",
        description="排序方式。可选值:pid(默认)、name、cpu、memory"
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="最大返回进程数,默认100"
    )


class KillProcessInput(BaseModel):
    pid: int = Field(
        ...,
        ge=1,
        description="进程ID(必填)。如 1234"
    )
    force: bool = Field(
        default=False,
        description="是否强制终止进程。默认False"
    )
    timeout: int = Field(
        default=5,
        ge=1,
        le=60,
        description="等待进程终止的超时时间(秒),默认5秒"
    )


class ServiceControlInput(BaseModel):
    """系统服务控制工具
    
    【action参数】决定操作类型：
    - start: 启动服务
    - stop: 停止服务
    - restart: 重启服务
    - list: 列出服务
    
    【使用示例】
    - 列出服务 → service_control(action="list")
    - 启动服务 → service_control(action="start", service_name="mysql")
    - 停止服务 → service_control(action="stop", service_name="nginx")
    - 重启服务 → service_control(action="restart", service_name="apache")
    """
    action: Literal["start", "stop", "restart", "list"] = Field(
        ...,
        description="操作类型(必填)。start=启动服务,stop=停止服务,restart=重启服务,list=列出服务"
    )
    service_name: Optional[str] = Field(
        default=None,
        description="服务名称。start/stop/restart时【必填】;list时可选(用于名称过滤)。如 MySQL、nginx"
    )
    state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="服务状态过滤(仅list时使用)。可选值:running/stopped/all(默认)"
    )
    force: bool = Field(
        default=False,
        description="是否强制停止(仅stop/restart时使用)。默认false。force=true时Windows用taskkill,Linux用systemctl kill"
    )
    timeout: int = Field(
        default=30, ge=1, le=300,
        description="等待服务操作的超时时间(秒,仅start/stop/restart时使用)。默认30秒"
    )


class CreateTaskInput(BaseModel):
    task_name: str = Field(
        ...,
        description="计划任务名称(必填)。如 MyBackup"
    )
    command: str = Field(
        ...,
        description="要执行的命令或程序路径(必填)。如 C:\\scripts\\backup.bat"
    )
    schedule: str = Field(
        ...,
        description="计划执行时间(必填)。格式:'HH:MM'(每日)、'HH:MM /day N'(每周)、'HH:MM /monthly DD'(每月)"
    )
    start_time: Optional[str] = Field(
        default=None,
        description="起始时间(可选)。如 '08:00'"
    )
    interval: Optional[int] = Field(
        default=None,
        description="重复间隔分钟数(可选)"
    )


class DeleteTaskInput(BaseModel):
    task_name: str = Field(
        ...,
        description="要删除的计划任务名称(必填)。如 MyBackup"
    )


class ListTasksInput(BaseModel):
    task_name: Optional[str] = Field(
        default=None,
        description="按任务名称过滤(模糊匹配,可选)"
    )
    state: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all",
        description="状态过滤(可选)。可选值:ready/running/disabled/all(默认)"
    )


class GetEnvInput(BaseModel):
    """环境变量获取工具
    
    【action参数】决定操作类型：
    - get: 获取单个环境变量
    - list: 列出所有环境变量
    
    【使用示例】
    - 获取单个 → get_env(name="PATH")
    - 列出所有 → get_env(action="list")
    """
    name: Optional[str] = Field(default=None, description="环境变量名称(action=get时【必填】)。如 PATH、HOME、JAVA_HOME")
    scope: Literal["process", "user", "system"] = Field(default="process", description="作用域。可选值:process/user/system。默认process")
    expand_vars: bool = Field(default=True, description="是否展开值中的嵌套变量(如 %%JAVA_HOME%%\\bin,仅action=get时使用)。默认true")
    action: Literal["get", "list"] = Field(default="get", description="操作类型。get=获取单个变量(默认),list=列出所有变量")
    prefix: Optional[str] = Field(default=None, description="环境变量名前缀过滤(仅action=list时使用)。例如 PY、JAVA")


class SetEnvInput(BaseModel):
    """环境变量设置工具
    
    【action参数】决定操作类型：
    - set: 设置环境变量
    - delete: 删除环境变量
    
    【使用示例】
    - 设置变量 → set_env(name="MY_VAR", value="my_value")
    - 删除变量 → set_env(action="delete", name="MY_VAR")
    """
    name: str = Field(..., description="环境变量名称(必填)。如 MY_VARIABLE、CONFIG_PATH、PATH")
    value: Optional[str] = Field(default=None, description="环境变量值(action=set时【必填】,action=delete时忽略)")
    scope: Literal["user", "system", "process"] = Field(default="process", description="作用域。可选值:process/user/system。默认process")
    append_mode: bool = Field(default=False, description="追加模式(仅action=set时使用)。设为true时若变量已存在则在原值后追加;设为false时覆盖原值。默认false")
    action: Literal["set", "delete"] = Field(default="set", description="操作类型。set=设置变量(默认),delete=删除变量")


__all__ = [
    "GetSystemInfoInput",
    "NetConnectionsInput",
    "EventLogInput",
    "ListProcessesInput",
    "KillProcessInput",
    "ServiceControlInput",
    "CreateTaskInput",
    "DeleteTaskInput",
    "ListTasksInput",
    "GetEnvInput",
    "SetEnvInput",
]