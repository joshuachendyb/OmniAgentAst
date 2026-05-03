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
    """read_json 工具的输入参数 - 小沈 2026-05-03修正
    
    按文档7.4节参数定义：
    - file_path: JSON文件路径（必填）
    - encoding: 文件编码（可选），默认 auto_detect
    - max_depth: 最大解析深度（可选），默认 10
    """
    file_path: str = Field(
        ...,
        description="JSON文件的绝对路径（必填）。如 D:/config/settings.json"
    )
    encoding: Optional[str] = Field(
        default="auto_detect",
        description="文件编码。默认 auto_detect。Agent 优先探测 UTF-8 BOM/无 BOM，失败后尝试 GBK"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最大解析深度。默认 10。防深层嵌套撑爆上下文。超出部分在 metadata 中标记 truncated，data 字段保持 100% 合法"
    )


class WriteJsonInput(BaseModel):
    """write_json 工具的输入参数 - 小沈 2026-05-03修正
    
    按文档7.4节参数定义：
    - file_path: JSON文件路径（必填）
    - data: 要写入的数据（必填）
    - encoding: 文件编码（可选），默认 utf-8
    - indent: 缩进空格数（可选），默认 2
    - ensure_ascii: 是否转义非ASCII（可选），默认 false
    - backup_before_write: 写入前备份（可选），默认 true
    - create_parents: 自动创建父目录（可选），默认 true
    """
    file_path: str = Field(
        ...,
        description="JSON文件的绝对路径（必填）。如 D:/output/data.json"
    )
    data: Union[Dict[str, Any], List[Any]] = Field(
        ...,
        description="要写入的数据（必填）。可以是字典、列表等可序列化的对象"
    )
    encoding: Optional[str] = Field(
        default="utf-8",
        description="文件编码。默认 utf-8。若文件已存在，Agent 读取原编码保持一致"
    )
    indent: Optional[int] = Field(
        default=2,
        description="缩进空格数。默认 2（人类可读）。若用于程序间传输，Agent 自动设 None（紧凑格式）"
    )
    ensure_ascii: Optional[bool] = Field(
        default=False,
        description="是否转义非 ASCII 字符。默认 false（保留中文原文）。若下游仅支持 ASCII，Agent 自动设 true"
    )
    backup_before_write: bool = Field(
        default=True,
        description="写入前是否备份。默认 true。备份至 %TEMP% 会话临时目录，绝不污染原目录"
    )
    create_parents: bool = Field(
        default=True,
        description="是否自动创建父目录。默认 true。防路径不存在报错"
    )


class ReadCsvBasicInput(BaseModel):
    """read_csv_basic 工具的输入参数 - 小沈 2026-05-03修正
    
    按文档7.4节参数定义：
    - file_path: CSV文件路径（必填）
    - encoding: 文件编码（可选），默认 auto_detect
    - delimiter: 分隔符（可选），默认 auto_detect
    - has_header: 是否有表头（可选），默认 true
    - max_rows: 最大读取行数（可选），默认 500
    - skip_blank_lines: 跳过空行（可选），默认 true
    """
    file_path: str = Field(
        ...,
        description="CSV文件的绝对路径（必填）。如 D:/data/users.csv"
    )
    encoding: Optional[str] = Field(
        default="auto_detect",
        description="文件编码。默认 auto_detect。Agent 优先探测 UTF-8/GBK，适配中文 CSV"
    )
    delimiter: Optional[str] = Field(
        default="auto_detect",
        description="分隔符。默认 auto_detect。Agent 使用 Sniffer 扫描前 10 行识别；若失败或列数不一致，自动 fallback 到 ,"
    )
    has_header: Optional[bool] = Field(
        default=True,
        description="是否有表头。默认 true。Agent 扫描首行内容判断；若推断失败，fallback 到 true 防错位"
    )
    max_rows: int = Field(
        default=500,
        ge=1,
        le=10000,
        description="最大读取行数。默认 500。Agent 根据意图动态调整：概览 50 行，分析 1000 行"
    )
    skip_blank_lines: bool = Field(
        default=True,
        description="是否跳过空行和纯空白行。默认 true。防解析中断"
    )
