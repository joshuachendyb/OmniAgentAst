# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

工具列表（5个）：
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class GetSystemInfoInput(BaseModel):
    """get_system_info 工具的输入参数"""
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all", description="要获取的信息类型：basic（基本信息）、cpu（CPU信息）、memory（内存信息）、disk（磁盘信息）、network（网络信息）、all（全部信息），默认为all"
    )


class NetConnectionsInput(BaseModel):
    """net_connections 工具的输入参数"""
    kind: Literal["inet", "tcp", "udp"] = Field(
        default="inet", description="连接类型。可选值：inet（TCP+UDP，默认）、tcp、udp"
    )
    state: Optional[str] = Field(
        default=None, description="连接状态。可选值：established（已建立）、listen（监听）、time_wait等"
    )
    resolve_dns: bool = Field(
        default=False, description="是否进行反向DNS解析。默认false。若开启，仅对ESTABLISHED状态的前10个IP解析"
    )
    process_info: bool = Field(
        default=False, description="是否获取占用端口的进程名/PID。默认false"
    )
    filter_port: Optional[int] = Field(
        default=None, description="过滤指定端口号", ge=1, le=65535
    )


class EventLogInput(BaseModel):
    """event_log 工具的输入参数"""
    log_name: str = Field(
        default="System", description="日志名称。常用值：System、Application、Security"
    )
    max_events: int = Field(
        default=50, ge=1, le=1000, description="最大返回事件数。默认50"
    )
    level: Optional[Literal["critical", "error", "warning", "info"]] = Field(
        default="error", description="日志级别。可选值：critical、error（默认）、warning、info"
    )
    source: Optional[str] = Field(
        default=None, description="事件来源/应用名"
    )
    time_range: str = Field(
        default="1h", description="时间范围。支持：10m、1h（默认）、24h、7d"
    )
    event_id: Optional[List[int]] = Field(
        default=None, description="事件ID数组"
    )


class ListProcessesInput(BaseModel):
    """list_processes 工具的输入参数 - 小沈 2026-05-02"""
    filter_name: Optional[str] = Field(
        default=None, description="按进程名过滤（支持模糊匹配）"
    )
    filter_pid: Optional[int] = Field(
        default=None, description="按PID过滤", ge=1
    )
    sort_by: Literal["pid", "name", "cpu", "memory"] = Field(
        default="pid", description="排序字段：pid（默认）、name、cpu、memory"
    )
    descending: bool = Field(
        default=False, description="是否降序排序。默认False（升序）"
    )
    max_results: int = Field(
        default=100, ge=1, le=500, description="最大返回进程数。默认100"
    )


class KillProcessInput(BaseModel):
    """kill_process 工具的输入参数 - 小沈 2026-05-02"""
    pid: int = Field(
        description="要终止的进程PID", ge=1
    )
    force: bool = Field(
        default=False, description="是否强制终止（SIGKILL）。默认False（SIGTERM）"
    )
    timeout: int = Field(
        default=5, ge=1, le=30, description="等待进程终止的超时时间（秒）。默认5秒"
    )


class LogMessageInput(BaseModel):
    """log_message 工具的输入参数 - 小沈 2026-05-02"""
    level: Literal["debug", "info", "warning", "error", "critical"] = Field(
        default="info", description="日志级别：debug、info（默认）、warning、error、critical"
    )
    message: str = Field(
        description="日志消息内容"
    )
    module: str = Field(
        default="system", description="模块名称，用于区分日志来源。默认system"
    )


class GetLogsInput(BaseModel):
    """get_logs 工具的输入参数 - 小沈 2026-05-02"""
    date: Optional[str] = Field(
        default=None, description="日期（格式：YYYY-MM-DD），默认今天"
    )
    level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = Field(
        default=None, description="按日志级别过滤"
    )
    module: Optional[str] = Field(
        default=None, description="按模块名过滤"
    )
    keyword: Optional[str] = Field(
        default=None, description="按关键字过滤"
    )
    max_lines: int = Field(
        default=100, ge=1, le=1000, description="最大返回行数。默认100"
    )


class ServiceListInput(BaseModel):
    """service_list 工具的输入参数 - 小沈 2026-05-02"""
    filter_name: Optional[str] = Field(
        default=None, description="按服务名过滤（支持模糊匹配）"
    )
    filter_state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all", description="按状态过滤：running（运行中）、stopped（已停止）、all（全部，默认）"
    )
    max_results: int = Field(
        default=100, ge=1, le=500, description="最大返回服务数。默认100"
    )


class ServiceStartInput(BaseModel):
    """service_start 工具的输入参数 - 小沈 2026-05-02"""
    service_name: str = Field(
        description="要启动的服务名称"
    )
    timeout: int = Field(
        default=30, ge=5, le=120, description="等待服务启动的超时时间（秒）。默认30秒"
    )


class ServiceStopInput(BaseModel):
    """service_stop 工具的输入参数 - 小沈 2026-05-02"""
    service_name: str = Field(
        description="要停止的服务名称"
    )
    force: bool = Field(
        default=False, description="是否强制停止。默认False（优雅停止）"
    )
    timeout: int = Field(
        default=30, ge=5, le=120, description="等待服务停止的超时时间（秒）。默认30秒"
    )


class TaskListInput(BaseModel):
    """task_list 工具的输入参数 - 小沈 2026-05-02"""
    filter_name: Optional[str] = Field(
        default=None, description="按任务名过滤（支持模糊匹配）"
    )
    filter_status: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all", description="按状态过滤：ready（就绪）、running（运行中）、disabled（已禁用）、all（全部，默认）"
    )
    max_results: int = Field(
        default=100, ge=1, le=500, description="最大返回任务数。默认100"
    )


class TaskCreateInput(BaseModel):
    """task_create 工具的输入参数 - 小沈 2026-05-02"""
    task_name: str = Field(
        description="计划任务名称"
    )
    command: str = Field(
        description="要执行的命令或程序路径"
    )
    schedule: str = Field(
        description="计划时间。格式：'HH:MM'（每日）或 'HH:MM /day'（每周几，1-7）或 'HH:MM /monthly DD'（每月几日）"
    )
    description: Optional[str] = Field(
        default=None, description="任务描述"
    )
    user: Optional[str] = Field(
        default=None, description="运行任务的用户账户。默认当前用户"
    )
    start_in: Optional[str] = Field(
        default=None, description="任务起始目录"
    )


class TaskDeleteInput(BaseModel):
    """task_delete 工具的输入参数 - 小沈 2026-05-02"""
    task_name: str = Field(
        description="要删除的计划任务名称"
    )
    force: bool = Field(
        default=False, description="是否强制删除（即使任务正在运行）。默认False"
    )


__all__ = [
    "GetSystemInfoInput",
    "NetConnectionsInput",
    "EventLogInput",
    "ListProcessesInput",
    "KillProcessInput",
    "LogMessageInput",
    "GetLogsInput",
    "ServiceListInput",
    "ServiceStartInput",
    "ServiceStopInput",
    "TaskListInput",
    "TaskCreateInput",
    "TaskDeleteInput",
]
