# -*- coding: utf-8 -*-
"""
Data Format 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按新增工具规范流程

职责：
定义 data_format 意图的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union


class ReadJsonInput(BaseModel):
    """read_json 工具的输入参数"""
    file_path: str = Field(
        ...,
        description="JSON文件的绝对路径。必填参数"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码格式。默认为utf-8"
    )


class WriteJsonInput(BaseModel):
    """write_json 工具的输入参数"""
    file_path: str = Field(
        ...,
        description="JSON文件的绝对路径。必填参数"
    )
    data: Union[Dict[str, Any], List[Any]] = Field(
        ...,
        description="要写入的数据（字典或列表）。必填参数"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码格式。默认为utf-8"
    )
    indent: Optional[int] = Field(
        default=2,
        description="缩进空格数，用于格式化输出。默认为2"
    )
    ensure_ascii: Optional[bool] = Field(
        default=False,
        description="是否转义非ASCII字符。默认为False（保留中文等字符）"
    )


class ReadCsvBasicInput(BaseModel):
    """read_csv_basic 工具的输入参数"""
    file_path: str = Field(
        ...,
        description="CSV文件的绝对路径。必填参数"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码格式。默认为utf-8"
    )
    delimiter: Optional[str] = Field(
        default=",",
        description="字段分隔符。默认为逗号(,)"
    )
    has_header: Optional[bool] = Field(
        default=True,
        description="是否包含表头。默认为True"
    )
