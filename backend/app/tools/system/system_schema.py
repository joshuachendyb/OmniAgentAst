# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-04-29 - 小沈 - 创建文件
# 2026-06-20 - 小健 - 删除net_connections/get_env/set_env
# 2026-07-20 - 小欧 - 复核schema docstring规范,4个工具默认行为均已在Field描述中体现,无需新增docstring
# 2026-07-25 - 小欧 - description去冗余: 移除12处必填/可选/默认重复描述
# 2026-07-25 - 小欧 - description去冗余: task_name/command移除冗余示例(3处)
# 2026-07-31 - 小欧 - EventLogInput.level移除Optional(与default="error"矛盾),description补充默认值说明
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

工具列表(4个):
1. event_log - 获取系统事件日志
2. create_task - 创建计划任务
3. delete_task - 删除计划任务
4. list_tasks - 列出计划任务
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class EventLogInput(BaseModel):
    log_name: Literal["Application", "System", "Security"] = Field(
        default="System",
        description="日志名称。System=系统日志,Application=应用日志,Security=安全日志"
    )
    max_events: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大返回事件数"
    )
    level: Literal["critical", "error", "warning", "info"] = Field(
        default="error",
        description="日志级别过滤，默认error，可选critical/error/warning/info"
    )
    source: Optional[str] = Field(
        default=None,
        description="事件来源/应用名过滤"
    )
    time_range: Literal["10m", "1h", "24h", "7d"] = Field(
        default="1h",
        description="时间范围过滤。可选10m/1h/24h/7d"
    )


class CreateTaskInput(BaseModel):
    task_name: str = Field(
        ...,
        description="计划任务名称"
    )
    command: str = Field(
        ...,
        description="要执行的命令或程序路径"
    )
    schedule: str = Field(
        ...,
        description="计划执行时间。格式:'HH:MM'(每日)、'HH:MM /day N'(每周)、'HH:MM /monthly DD'(每月)"
    )

    interval: Optional[int] = Field(
        default=None,
        description="重复间隔分钟数"
    )


class DeleteTaskInput(BaseModel):
    task_name: str = Field(
        ...,
        description="要删除的计划任务名称"
    )


class ListTasksInput(BaseModel):
    task_name: Optional[str] = Field(
        default=None,
        description="按任务名称过滤(模糊匹配)"
    )
    state: Optional[Literal["ready", "running", "disabled", "all"]] = Field(
        default="all",
        description="状态过滤。可选值:ready/running/disabled/all"
    )


__all__ = [

    "EventLogInput",
    "CreateTaskInput",
    "DeleteTaskInput",
    "ListTasksInput",
]
