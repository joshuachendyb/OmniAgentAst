# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

工具列表（3个）：
1. get_system_info - 获取系统信息
2. net_connections - 获取网络连接列表
3. event_log - 获取系统事件日志

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


__all__ = [
    "GetSystemInfoInput",
    "NetConnectionsInput",
    "EventLogInput",
]
