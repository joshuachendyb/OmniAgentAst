# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

【2026-05-17 小沈】按精简方案13.4节重构：16→10工具
- 消除 log_message/get_logs（被write_text_file/read_text_file覆盖）
- service×3 → service_control 统一入口
- task×3 → task_control 统一入口
- 修正S1: ListProcessesInput删除limit(保留max_results)
- 新增 ServiceControlInput、TaskControlInput

工具列表（10个LLM可见）：
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志
4. list_processes - 列出所有进程
5. kill_process - 终止指定进程
6. service_control - 服务统一控制(start/stop/restart/list)
7. task_control - 计划任务统一控制(create/delete/list)
8. reg_read - 读取注册表键值
9. reg_write - 写入注册表键值
10. reg_delete - 删除注册表键值

Author: 小沈 - 2026-04-29
更新时间: 2026-05-03 小沈 - 修正参数description，准确清晰完整
更新时间: 2026-05-17 小沈 - 16→10工具重构
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any


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
    """list_processes 工具的输入参数 - 按文档7.5节定义
    【2026-05-17 小沈】修正S1: 删除limit参数(与max_results重复)
    """
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


# 【2026-05-18 小健】已废弃Schema已删除：
# ServiceListInput/ServiceStartInput/ServiceStopInput → 合并入 ServiceControlInput
# TaskListInput/TaskCreateInput/TaskDeleteInput → 合并入 TaskControlInput


# 【2026-05-17 小沈】新增：ServiceControlInput - 服务统一控制入口
class ServiceControlInput(BaseModel):
    """service_control 工具的输入参数 - 统一服务控制入口
    合并 service_start/service_stop/service_list，通过action分发
    """
    action: Literal["start", "stop", "restart", "list"] = Field(
        ...,
        description="操作类型（必填）。可选值：\n- start：启动服务\n- stop：停止服务\n- restart：重启服务（先停后启）\n- list：列出服务"
    )
    service_name: Optional[str] = Field(
        default=None,
        description="服务名称。start/stop/restart时必填；list时可选（用于名称过滤）。如 MySQL、nginx"
    )
    state: Optional[Literal["running", "stopped", "all"]] = Field(
        default="all",
        description="服务状态过滤（仅list时使用）。可选值：running、stopped、all（默认）"
    )
    force: bool = Field(
        default=False,
        description="是否强制停止（仅stop/restart时使用）。默认false。force=true时Windows用taskkill，Linux用systemctl kill"
    )
    wait_for_started: bool = Field(
        default=False,
        description="等待服务启动完成（仅start/restart时使用）。默认false。true时等待服务真正进入running状态"
    )
    wait_for_stopped: bool = Field(
        default=False,
        description="等待服务停止完成（仅stop/restart时使用）。默认false。true时等待服务真正停止"
    )
    timeout: int = Field(
        default=30, ge=1, le=300,
        description="等待服务操作的超时时间（秒）。默认30秒"
    )


# 【2026-05-17 小沈】新增：TaskControlInput - 计划任务统一控制入口
class TaskControlInput(BaseModel):
    """task_control 工具的输入参数 - 统一计划任务控制入口
    合并 task_create/task_delete/task_list，通过action分发
    """
    action: Literal["create", "delete", "list"] = Field(
        ...,
        description="操作类型（必填）。可选值：\n- create：创建计划任务\n- delete：删除计划任务\n- list：列出计划任务"
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
    start_date: Optional[str] = Field(
        default=None,
        description="起始日期（仅create时可选）。如 '2026-05-17'"
    )
    interval: Optional[int] = Field(
        default=None,
        description="重复间隔分钟数（仅create时可选）"
    )
    state: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all",
        description="状态过滤（仅list时使用）。可选值：ready、running、disabled、all（默认）"
    )
    folder: Optional[str] = Field(
        default=None,
        description="任务所在文件夹（仅delete时可选）。不提供时从根目录查找"
    )


# 【2026-05-18 小沈】新增：Environment 工具 Schema（从environment模块迁入）
class GetEnvInput(BaseModel):
    """get_env 工具的输入参数"""
    name: str = Field(..., description="环境变量名称。如 \"PATH\"、\"HOME\"、\"USER\"、\"JAVA_HOME\" 等")
    default: Optional[str] = Field(default=None, description="默认值（可选）。如果指定的环境变量不存在，则返回此默认值")
    scope: Literal["process", "user", "system"] = Field(default="process", description="作用域。可选值：process（仅当前进程）、user（当前用户持久化）、system（全局持久化，需管理员权限）。Agent根据query语义自动映射。默认为process")
    expand_vars: bool = Field(default=True, description="是否展开值中的嵌套变量（如 %JAVA_HOME%\\bin 或 $HOME/.local）。默认 true（返回绝对路径）。展开失败时保留原始字符串")


class SetEnvInput(BaseModel):
    """set_env 工具的输入参数"""
    name: str = Field(..., description="环境变量名称。如 \"MY_VARIABLE\"、\"CONFIG_PATH\"、\"PATH\" 等")
    value: Optional[str] = Field(default=None, description="环境变量值。action=\"set\"时必填，action=\"delete\"时忽略。任意字符串值")
    scope: Literal["user", "system", "process"] = Field(default="process", description="作用域。可选值：process（仅当前进程）、user（持久化到当前用户）、system（持久化到全局，需管理员权限）。Agent根据语义自动映射。默认为process")
    append_mode: bool = Field(default=False, description="追加模式。若 name 为 PATH 或 CLASSPATH，Agent 自动设true。根据OS自动选择分隔符。默认为False")
    action: Literal["set", "delete"] = Field(default="set", description="操作类型。\"set\"=设置变量（默认），\"delete\"=删除变量（原delete_env）。Agent根据语义自动映射")
    exist_ok: bool = Field(default=True, description="幂等模式。True时若变量已存在且值相同则直接返回成功，False时始终覆盖。默认True")


class ListEnvInput(BaseModel):
    """list_env 工具的输入参数"""
    prefix: Optional[str] = Field(default=None, description="环境变量名前缀过滤（可选），例如 PY、JAVA")
    include_system: bool = Field(default=False, description="是否包含系统级环境变量，默认为False（仅用户级）")


# 【2026-05-18 小沈】新增：Env Check 工具 Schema（从env_check模块迁入）
class ValidateCsvFormatInput(BaseModel):
    """validate_csv_format 工具的输入参数（Tool 87）"""
    file_path: str = Field(..., description="CSV文件路径。如 D:/data/users.csv")


class ValidateChartDataInput(BaseModel):
    """validate_chart_data 工具的输入参数（Tool 88）"""
    data: Dict[str, Any] = Field(..., description="图表数据（JSON格式）。检查是否包含必要的 labels 和 values 字段")


class CheckPdfReadableInput(BaseModel):
    """check_pdf_readable 工具的输入参数（Tool 89）"""
    file_path: str = Field(..., description="PDF文件路径。如 D:/documents/report.pdf")


class CheckDocxReadableInput(BaseModel):
    """check_docx_readable 工具的输入参数（Tool 90）"""
    file_path: str = Field(..., description="Word文件路径。如 D:/documents/report.docx")


class CheckXlsxReadableInput(BaseModel):
    """check_xlsx_readable 工具的输入参数（Tool 91）"""
    file_path: str = Field(..., description="Excel文件路径。如 D:/data/report.xlsx")


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
    "ListEnvInput",
    "ValidateCsvFormatInput",
    "ValidateChartDataInput",
    "CheckPdfReadableInput",
    "CheckDocxReadableInput",
    "CheckXlsxReadableInput",
]