# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

工具列表（13个）：
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程
6. log_message - 记录日志消息
7. get_logs - 获取日志内容
8. service_list - 列出系统服务
9. service_start - 启动系统服务
10. service_stop - 停止系统服务
11. task_list - 列出计划任务
12. task_create - 创建计划任务
13. task_delete - 删除计划任务

Author: 小沈 - 2026-04-29
更新时间: 2026-05-03 小沈 - 修正参数description，准确清晰完整
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class GetSystemInfoInput(BaseModel):
    """get_system_info 工具的输入参数 - 小沈 2026-05-03 修正"""
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all",
        description="要获取的系统信息类型。必填为LLM给出，当LLM未明确指定时Agent智能补全为all。可选值含义：\n- basic：操作系统名称、版本、主机名、架构等基础信息\n- cpu：处理器型号、核心数、频率、使用率等CPU信息\n- memory：总内存、可用内存、使用率等内存信息\n- disk：各磁盘总空间、可用空间、使用率等磁盘信息\n- network：网络接口名称、IP地址、MAC地址等网络信息\n- all：以上全部信息（默认）"
    )


class NetConnectionsInput(BaseModel):
    """net_connections 工具的输入参数 - 小沈 2026-05-03 修正"""
    kind: Literal["inet", "tcp", "udp"] = Field(
        default="inet",
        description="网络连接的类型。必填为LLM给出，当LLM未明确指定时Agent智能补全为inet。可选值含义：\n- inet：TCP和UDP连接（默认）\n- tcp：仅TCP连接\n- 仅UDP连接"
    )
    state: Optional[str] = Field(
        default=None,
        description="连接状态过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为null（返回所有状态）。常见取值：\n- established：已建立的连接（用户问\"谁连着我\"时Agent自动设为此值）\n- listen：监听中的端口（用户问\"开了哪些服务\"时Agent自动设为此值）\n- time_wait：等待中的连接\n- close_wait：关闭等待中的连接"
    )
    resolve_dns: bool = Field(
        default=False,
        description="是否对IP地址进行反向DNS解析，将IP地址解析为域名。必填为LLM给出，当LLM未明确指定时Agent智能补全为false。开启后仅对ESTABLISHED状态的前10个IP进行解析，单IP超时2秒自动跳过，防止阻塞。"
    )
    process_info: bool = Field(
        default=False,
        description="是否获取占用端口的进程信息（进程名和PID）。必填为LLM给出，当LLM未明确指定时Agent智能补全为false。若用户问\"哪个程序占用端口\"，Agent自动设为true。权限不足时自动降级为仅返回IP和端口，并提示需要管理员权限。"
    )
    filter_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="过滤指定端口号，只返回与该端口相关的连接。必填为LLM给出，当LLM未明确指定时Agent智能补全为null。Agent自动从用户query中提取��口号填入，例如用户问\"占用8080端口的进程\"时Agent自动填入8080。"
    )


class EventLogInput(BaseModel):
    """event_log 工具的输入参数 - 小沈 2026-05-03 修正"""
    log_name: str = Field(
        default="System",
        description="要读取的日志名称（Windows事件查看器日志分类）。必填为LLM给出，当LLM未明确指定时Agent智能补全为System。可选值含义：\n- System：系统日志，记录系统组件事件（默认）\n- Application：应用程序日志，记录应用程序事件\n- Security：安全日志，记录登录审计等信息\n用户问\"软件崩溃\"时Agent自动切为Application；问\"登录失败\"时Agent自动切为Security。"
    )
    max_events: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大返回的事件数。必填为LLM给出，当LLM未明确指定时Agent智能补全为50。Agent根据意图动态调整：概览类意图自动设为20条，深度排查类意图自动设为200条。"
    )
    level: Optional[Literal["critical", "error", "warning", "info"]] = Field(
        default="error",
        description="日志级别过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为error。可选值含义：\n- critical：严重错误（最高级别）\n- error：错误（默认）\n- warning：警告\n- info：信息\nAgent负责跨平台映射并自动收窄范围。"
    )
    source: Optional[str] = Field(
        default=None,
        description="事件来源/应用名过滤，只返回指定来源的事件。必填为LLM给出，当LLM未明确指定时Agent智能补全为null。Agent自动从用户query中提取应用名填入，例如用户问\"Windows Update错误\"时Agent自动填入\"Windows Update\"。"
    )
    time_range: str = Field(
        default="1h",
        description="时间范围过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为1h。支持格式：\n- 10m：最近10分钟\n- 1h：最近1小时（默认）\n- 24h：最近24小时\n- 7d：最近7天\nAgent语义映射自然语言到标准格式，例如用户说\"今天\"自动映射为24h。"
    )
    event_id: Optional[List[int]] = Field(
        default=None,
        description="事件ID数组过滤，只返回指定ID的事件。必填为LLM给出，当LLM未明确指定时Agent智能补全为null。支持数组格式例如[4625,4771]。Agent自动解析用户query中的事件ID进行联合过滤。"
    )


class ListProcessesInput(BaseModel):
    """list_processes 工具的输入参数 - 小沈 2026-05-03修正
    
    按文档7.5节参数定义：
    - name: 进程名称过滤（可选）
    - user: 用户名过滤（可选）
    - status: 状态过滤（可选），running/sleeping
    - limit: 返回数量限制（可选），默认 100
    - sort_by: 排序方式（可选），默认 pid
    """
    name: Optional[str] = Field(
        default=None,
        description="进程名称过滤（可选）。如 python.exe、chrome.exe。Agent 根据 query 语义自动提取进程名，若 query 只说查看进程则不设此参数"
    )
    user: Optional[str] = Field(
        default=None,
        description="用户名过滤（可选）。如 Administrator。Agent 根据 query 中是否包含用户信息自动映射"
    )
    status: Optional[Literal["running", "sleeping"]] = Field(
        default=None,
        description="状态过滤（可选）。可选值：running（运行中）、sleeping（睡眠）。Agent 根据 query 语义自动映射，如问卡住的进程自动映射为 running"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="返回进程数量限制（可选），默认 100。Agent 根据 query 语义自动提取数量，如说前10个自动设 limit=10"
    )
    sort_by: Literal["pid", "name", "cpu", "memory"] = Field(
        default="pid",
        description="排序方式（可选）。可选值：pid（默认值）、name（名称）、cpu（CPU 占用）、memory（内存占用）。Agent 根据 query 语义自动映射，如问最占 CPU 自动设 cpu"
    )


class KillProcessInput(BaseModel):
    """kill_process 工具的输入参数 - 小沈 2026-05-03修正
    
    按文档7.5节参数定义：
    - pid: 进程ID（可选）
    - name: 进程名称（可选，可批量终止）
    - force: 是否强制终止（可选），默认 false
    """
    pid: Optional[int] = Field(
        default=None,
        ge=1,
        description="进程 ID（可选）。如 1234。Agent 根据 query 语义自动提取 PID，若 query 只提供进程名则通过 list_processes 查找后再填充"
    )
    name: Optional[str] = Field(
        default=None,
        description="进程名称（可选）。可批量终止同名进程，如 python.exe。Agent 根据 query 语义自动提取进程名"
    )
    force: bool = Field(
        default=False,
        description="是否强制终止进程。默认 false。false：优雅终止（SIGTERM），给进程机会清理资源；true：强制终止（SIGKILL），立即杀死进程。若进程无响应，Agent 自动设 force 为 true 强制杀死"
    )


class LogMessageInput(BaseModel):
    """log_message 工具的输入参数 - 小沈 2026-05-03 修正
    
    按文档7.3节参数定义：
    - message: 日志消息内容（必填）
    - level: 日志级别（可选），默认 INFO
    - logger_name: 记录器名称（可选），默认 root
    - log_file: 日志文件路径（可选），默认控制台
    """
    message: str = Field(
        ...,
        description="日志消息内容（必填）。要记录到日志的消息文本。必填由LLM提供。"
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别。可选值：DEBUG、INFO（默认）、WARNING、ERROR、CRITICAL。Agent 根据消息语义自动推断：崩溃/失败→ERROR，启动/完成→INFO，调试→DEBUG"
    )
    logger_name: str = Field(
        default="root",
        description="日志记录器名称。默认 root。Agent 根据 query 模块名自动映射，如 agent、tool、workflow 等"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="日志文件路径。默认 null（仅输出到控制台）。Agent 根据意图自动路由到项目标准日志路径"
    )


class GetLogsInput(BaseModel):
    """get_logs 工具的输入参数 - 小沈 2026-05-03 修正
    
    按文档7.3节参数定义：
    - log_file: 日志文件路径（必填）
    - level: 日志级别过滤（可选），默认 WARNING
    - start_time: 起始时间过滤（可选）
    - end_time: 结束时间过滤（可选）
    - log_format: 时间格式（可选），默认 auto_detect
    - max_lines: 最大行数（可选），默认 200
    - tail_mode: 尾部读取模式（可选），默认 false
    - pattern: 关键词过滤（可选）
    - output_format: 输出格式（可选），默认 table
    """
    log_file: str = Field(
        ...,
        description="日志文件路径（必填）。如 D:/logs/app.log。必填由LLM提供。"
    )
    level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = Field(
        default="WARNING",
        description="日志级别过滤。默认 WARNING。可选值：DEBUG、INFO、WARNING、ERROR、CRITICAL。Agent 根据 query 语义自动收窄：查错误→ERROR，全量→DEBUG"
    )
    start_time: Optional[str] = Field(
        default=None,
        description="起始时间过滤。Agent 解析自然语言自动转为标准格式。依赖 log_format 解析"
    )
    end_time: Optional[str] = Field(
        default=None,
        description="结束时间过滤。默认 null（截至当前）"
    )
    log_format: Optional[str] = Field(
        default="auto_detect",
        description="日志时间格式。默认 auto_detect。Agent 优先自动探测常见格式；若失败或需精确过滤，自动注入标准格式（如 YYYY-MM-DD HH:mm:ss）"
    )
    max_lines: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="返回最大行数。默认 200。Agent 根据意图动态调整：概览 50 行，深度排查 1000 行"
    )
    tail_mode: bool = Field(
        default=False,
        description="是否仅读取文件末尾 max_lines 行。默认 false。注意：开启后不执行 level/pattern 过滤，若需过滤 Agent 自动关闭此模式改为正向读取"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="关键词/正则过滤。Agent 从 query 自动提取注入。与 tail_mode 互斥"
    )
    output_format: Literal["table", "json"] = Field(
        default="table",
        description="输出格式。可选值：table（默认，人类可读）、json（结构化数据）。由 Agent 根据下游需求自动切换"
    )


class ServiceListInput(BaseModel):
    """service_list 工具的输入参数 - 小沈 2026-05-03 修正"""
    filter_name: Optional[str] = Field(
        default=None,
        description="按服务名模糊匹配过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为null。例如填写\"mysql\"会匹配所有名称包含mysql的服务。"
    )
    filter_state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="按服务状态过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为all。可选值含义：\n- running：仅返回运行中的服务\n- stopped：仅返回已停止的服务\n- all：返回所有服务（默认）"
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="最大返回的服务数。必填为LLM给出，当LLM未明确指定时Agent智能补全为100。用于限制返回结果数量，避免输出过多。"
    )


class ServiceStartInput(BaseModel):
    """service_start 工具的输入参数 - 小沈 2026-05-03 修正"""
    service_name: str = Field(
        ...,
        description="要启动的服务名称（必填）。可通过service_list工具查询可用的服务名称。必填由LLM提供。"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="等待服务启动的超时时间（秒）。必填为LLM给出，当LLM未明确指定时Agent智能补全为30。若服务启动时间超过此值则超时失败。"
    )


class ServiceStopInput(BaseModel):
    """service_stop 工具的输入参数 - 小沈 2026-05-03 修正"""
    service_name: str = Field(
        ...,
        description="要停止的服务名称（必填）。可通过service_list工具查询可用的服务名称。必填由LLM提供。"
    )
    force: bool = Field(
        default=False,
        description="是否强制停止服务。必填为LLM给出，当LLM未明确指定时Agent智能补全为false。\n- false：优雅停止，发送停止信号（默认）\n- true：强制停止，立即终止\n若服务无响应，Agent自动设force为true强制停止。"
    )
    timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="等待服务停止的超时时间（秒）。必填为LLM给出，当LLM未明确指定时Agent智能补全为30。若服务停止时间超过此值则超时失败。"
    )


class TaskListInput(BaseModel):
    """task_list 工具的输入参数 - 小沈 2026-05-03 修正"""
    filter_name: Optional[str] = Field(
        default=None,
        description="按计划任务名模糊匹配过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为null。例如填写\"backup\"会匹配所有名称包含backup的任务。"
    )
    filter_status: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all",
        description="按任务状态过滤。必填为LLM给出，当LLM未明确指定时Agent智能补全为all。可选值含义：\n- ready：已就绪待执行的任务\n- running：正在运行的任务\n- disabled：已禁用的任务\n- all：所有任务（默认）"
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=500,
        description="最大返回的任务数。必填为LLM给出，当LLM未明确指定时Agent智能补全为100。用于限制返回结果数量，避免输出过多。"
    )


class TaskCreateInput(BaseModel):
    """task_create 工具的输入参数 - 小沈 2026-05-03 修正"""
    task_name: str = Field(
        ...,
        description="计划任务的名称（必填）。用于标识和后续管理任务，不能与现有任务重名。必填由LLM提供。"
    )
    command: str = Field(
        ...,
        description="要执行的命令或程序路径（必填）。可以是命令行或完整路径的可执行文件。必填由LLM提供。"
    )
    schedule: str = Field(
        ...,
        description="计划执行时间（必填）。格式说明：\n- 每日：\"HH:MM\"，例如\"08:00\"表示每天早上8点执行\n- 每周：\"HH:MM /day D\"，例如\"08:00 /day 1\"表示每周一早上8点执行，1-7代表周日到周六\n- 每月：\"HH:MM /monthly DD\"，例如\"08:00 /monthly 1\"表示每月1号早上8点执行\n必填由LLM提供。"
    )
    description: Optional[str] = Field(
        default=None,
        description="任务描述，用于说明任务的用途。可选，不提供时Agent智能补全为null。"
    )
    user: Optional[str] = Field(
        default=None,
        description="运行任务的用户账户。必填为LLM给出，当LLM未明确指定时Agent智能补全为null（默认使用当前用户）。需要指定具有相应权限的用户。"
    )
    start_in: Optional[str] = Field(
        default=None,
        description="任务执行的起始目录。可选，不提供时Agent智能补全为null。指定命令执行时的工作目录。"
    )


class TaskDeleteInput(BaseModel):
    """task_delete ��具的输入参数 - 小沈 2026-05-03 修正"""
    task_name: str = Field(
        ...,
        description="要删除的计划任务名称（必填）。可通过task_list工具查询现有的任务名称。必填由LLM提供。"
    )
    force: bool = Field(
        default=False,
        description="是否强制删除（即使任务正在运行）。必填为LLM给出，当LLM未明确指定时Agent智能补全为false。\n- false：仅删除已停止的任务（默认）\n- true：强制删除，包括正在运行的任务"
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