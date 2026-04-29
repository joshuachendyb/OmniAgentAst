# -*- coding: utf-8 -*-
"""
SYSTEM 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 system 工具的 Pydantic 模型。

工具列表（1个）：
1. get_system_info - 获取系统信息

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class GetSystemInfoInput(BaseModel):
    """get_system_info 工具的输入参数"""
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all", description="要获取的信息类型：basic（基本信息）、cpu（CPU信息）、memory（内存信息）、disk（磁盘信息）、network（网络信息）、all（全部信息），默认为all"
    )


__all__ = [
    "GetSystemInfoInput",
]
