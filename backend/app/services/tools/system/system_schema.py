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
    """list_processes 工具的输入参数 - 按文档7.5节定义"""
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
        description="用户名过滤（可选）。如 Administrator"
    )
    status: Optional[Literal["running", "sleeping"]] = Field(
        default=None,
        description="状态过滤（可选）。可选值：running（运行中）、sleeping（睡眠）"
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=500,
        description="返回进程数量限制（可选），默认100"
    )
    sort_by: Literal["pid", "name", "cpu", "memory"] = Field(
        default="pid",
        description="排序方式（可选）。可选值：pid、name、cpu、memory，默认pid"
    )
    descending: bool = Field(
        default=False,
        description="降序排序，默认False"
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


class LogMessageInput(BaseModel):
    """log_message 工具的输入参数 - 按文档7.3节定义"""
    message: str = Field(
        ...,
        description="日志消息内容（必填）"
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="日志级别（可选），默认INFO。可选值：DEBUG、INFO、WARNING、ERROR、CRITICAL"
    )
    logger_name: str = Field(
        default="root",
        description="日志记录器名称（可选），默认root"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="日志文件路径（可选），默认null输出到控制台"
    )


class GetLogsInput(BaseModel):
    """get_logs 工具的输入参数 - 按文档7.3节定义"""
    log_file: str = Field(
        ...,
        description="日志文件路径（必填）"
    )
    level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = Field(
        default="WARNING",
        description="日志级别过滤（可选），默认WARNING"
    )
    start_time: Optional[str] = Field(
        default=None,
        description="起始时间（可选），Agent自动解析自然语言时间"
    )
    end_time: Optional[str] = Field(
        default=None,
        description="结束时间（可选），默认当前时间"
    )
    log_format: str = Field(
        default="auto_detect",
        description="时间格式（可选），默认auto_detect"
    )
    max_lines: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="最大返回行数（可选），默认200"
    )
    tail_mode: bool = Field(
        default=False,
        description="尾部读取模式（可选），默认false"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="关键词过滤（可选）"
    )
    output_format: str = Field(
        default="table",
        description="输出格式（可选），默认table，可选json"
    )


class ServiceListInput(BaseModel):
    """service_list 工具的输入参数 - 小沈 2026-05-03 修正
    
    按文档7.6节参数定义：
    - name: 服务名称过滤（可选）
    - state: 状态过滤（可选），running/stopped/all
    - output_format: 输出格式（可选），json/table
    """
    name: Optional[str] = Field(
        default=None,
        description="服务名称过滤（可选）。如 MySQL、nginx。Agent 根据 query 语义自动提取服务名关键词进行模糊匹配"
    )
    state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="服务状态过滤（可选）。可选值：running（运行中）、stopped（已停止）、all（全部）。Agent 根据 query 语义自动映射，如问运行中的服务自动映射为 running。默认为all"
    )
    output_format: Literal["json", "table"] = Field(
        default="json",
        description="输出格式（可选）。可选值：json（结构化数据）、table（人类可读表格）。Agent 根据下游需求自动切换，如需人类阅读则切换为 table。默认为json"
    )


class ServiceStartInput(BaseModel):
    """service_start 工具的输入参数 - 小沈 2026-05-03, 小健 2026-05-06 补timeout"""
    service_name: str = Field(
        ...,
        description="要启动的服务名称（必填）。如 MySQL、nginx。必填由 LLM 提供，可通过 service_list 查询可用服务"
    )
    wait_for_started: bool = Field(
        default=True,
        description="等待服务启动完成（可选）。默认 true。Agent 等待服务真正进入运行状态后再返回，确保启动成功。若设为 false 则立即返回"
    )
    timeout: int = Field(
        default=30, ge=1, le=300,
        description="等待服务启动的超时时间（秒）。默认30秒 - 小健 2026-05-06"
    )


class ServiceStopInput(BaseModel):
    """service_stop 工具的输入参数 - 小沈 2026-05-03 修正
    
    按文档7.6节参数定义：
    - service_name: 服务名称（必填）
    - force: 强制停止（可选），默认 false
    - wait_for_stopped: 等待停止（可选），默认 true
    """
    service_name: str = Field(
        ...,
        description="要停止的服务名称（必填）。如 MySQL、nginx。必填由 LLM 提供，可通过 service_list 查询可用服务"
    )
    force: bool = Field(
        default=False,
        description="是否强制停止服务（可选）。默认 false。false：优雅停止，发送停止信号等待清理；true：强制立即终止。若服务无响应，Agent 自动设 force 为 true"
    )
    wait_for_stopped: bool = Field(
        default=True,
        description="等待服务停止完成（可选）。默认 true。Agent 等待服务真正停止后再返回，确保停止成功。若设为 false 则立即返回"
    )
    timeout: int = Field(
        default=30, ge=1, le=300,
        description="等待服务停止的超时时间（秒）。默认30秒 - 小健 2026-05-06"
    )


class TaskListInput(BaseModel):
    """task_list 工具的输入参数 - 按文档7.7节定义
    
    按文档7.7节参数定义：
    - filter_name: 任务名过滤（可选）
    - filter_status: 状态过滤（可选），ready/running/disabled/all
    - max_results: 最大返回数（可选），默认100
    """
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
    """task_create 工具的输入参数 - 按文档7.7节定义
    
    按文档7.7节参数定义：
    - task_name: 任务名称（必填）
    - command: 命令（必填）
    - schedule: 计划时间（必填）
    - description: 任务描述（可选）
    - user: 运行用户（可选）
    - start_in: 起始目录（可选）
    """
    task_name: str = Field(
        ...,
        description="计划任务的名称（必填）。用于标识和后续管理任务，不能与现有任务重名。必填由 LLM 提供。"
    )
    command: str = Field(
        ...,
        description="要执行的命令或程序路径（必填）。可以是命令行或完整路径的可执行文件。必填由 LLM 提供。"
    )
    schedule: str = Field(
        ...,
        description="计划执行时间（必填）。格式说明：\n- 每日：\"HH:MM\"，例如\"08:00\"表示每天早上8点执行\n- 每周：\"HH:MM /day D\"，例如\"08:00 /day 1\"表示每周一早上8点执行，1-7代表周日到周六\n- 每月：\"HH:MM /monthly DD\"，例如\"08:00 /monthly 1\"表示每月1号早上8点执行\n必填由 LLM 提供。"
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
    start_time: Optional[str] = Field(
        default=None,
        description="起始时间（可选）。如 '08:00'。不提供时使用schedule中的时间 - 小健 2026-05-06"
    )
    start_date: Optional[str] = Field(
        default=None,
        description="起始日期（可选）。如 '2026-05-06'。不提供时使用当前日期 - 小健 2026-05-06"
    )
    interval: Optional[int] = Field(
        default=None,
        description="重复间隔（分钟，可选）。不提供时使用schedule中的间隔 - 小健 2026-05-06"
    )


class TaskDeleteInput(BaseModel):
    """task_delete 工具的输入参数 - 按文档7.7节定义, 小健 2026-05-06 补folder
    
    按文档7.7节参数定义：
    - task_name: 任务名称（必填）
    - force: 强制删除（可选），默认false
    """
    task_name: str = Field(
        ...,
        description="要删除的计划任务名称（必填）。可通过 task_list 工具查询现有的任务名称。必填由 LLM 提供。"
    )
    force: bool = Field(
        default=False,
        description="是否强制删除（即使任务正在运行）。必填为LLM给出，当LLM未明确指定时Agent智能补全为false。\n- false：仅删除已停止的任务（默认）\n- true：强制删除，包括正在运行的任务"
    )
    folder: Optional[str] = Field(
        default=None,
        description="任务所在文件夹（可选）。不提供时从根目录查找 - 小健 2026-05-06"
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