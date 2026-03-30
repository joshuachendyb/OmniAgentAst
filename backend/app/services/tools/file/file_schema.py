# -*- coding: utf-8 -*-
"""
File Intent 工具参数 Schema 定义

【创建时间】2026-03-21 小沈
【设计依据】多意图处理架构设计-小沈-2026-03-20.md (v2.18) - 12.2节

职责：
定义 file 意图的7个工具的参数 Pydantic 模型，作为独立的 Schema 定义文件。
其他模块（如 file_tools.py、react_schema.py）从这里导入模型使用。

各意图的 Schema 文件统一放在 tools/{intent}/ 目录下：
- tools/file/file_schema.py  → file 意图的工具参数 Schema
- tools/network/network_schema.py → network 意图的工具参数 Schema（待实现）
- tools/desktop/desktop_schema.py → desktop 意图的工具参数 Schema（待实现）

Author: 小沈 - 2026-03-21
"""

from pydantic import BaseModel, Field
from typing import Optional


class ReadFileInput(BaseModel):
    """read_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/file.txt）"
    )
    offset: int = Field(
        default=1,
        ge=1,
        description="起始行号，从1开始计数，默认为1"
    )
    limit: int = Field(
        default=2000,
        ge=1,
        le=10000,
        description="最大读取行数，默认为2000行，最大10000行"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认为utf-8"
    )


class WriteFileInput(BaseModel):
    """write_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径）"
    )
    content: str = Field(
        description="要写入文件的内容"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认为utf-8"
    )


class ListDirectoryInput(BaseModel):
    """list_directory 工具的输入参数"""
    dir_path: str = Field(
        description="目录的完整路径（必须是绝对路径，如 D:/项目代码）"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归列出所有子目录，默认为False（不递归）"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大递归深度，仅当 recursive=True 时有效，默认为10"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌，用于获取下一页结果，默认为None"
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="每页返回数量，默认为100，最大500"
    )


class DeleteFileInput(BaseModel):
    """delete_file 工具的输入参数"""
    file_path: str = Field(
        description="要删除的文件或目录的完整路径"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归删除目录（目录非空时需要设为True）"
    )


class MoveFileInput(BaseModel):
    """move_file 工具的输入参数"""
    source_path: str = Field(
        description="源文件或目录的完整路径"
    )
    destination_path: str = Field(
        description="目标路径（可以是新文件名或新目录位置）"
    )


class SearchFileContentInput(BaseModel):
    """search_file_content 工具的输入参数"""
    pattern: str = Field(
        description="搜索内容的关键字（必填，不能为空）"
    )
    path: str = Field(
        default=".",
        description="搜索的起始目录，默认为当前目录"
    )
    file_pattern: str = Field(
        default="*",
        description="文件名匹配模式，支持通配符（* 匹配任意字符），默认为*（所有文件）"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录，默认为True"
    )


class SearchFilesByNameInput(BaseModel):
    """search_files 工具的输入参数（搜索文件名）"""
    file_pattern: str = Field(
        description="文件名匹配模式，支持通配符（* 匹配任意字符，? 匹配单个字符）"
    )
    path: str = Field(
        default=".",
        description="搜索的起始目录，默认为当前目录"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录，默认为True"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大递归深度，仅当recursive=True时有效，默认为10"
    )
    max_results: int = Field(
        default=None,
        ge=1,
        description="限制每次最多获取结果数量，不设置则搜索全部结果"
    )
    after: Optional[str] = Field(
        default=None,
        description="上次搜索结束的文件名，用于继续搜索（分页）"
    )


class GenerateReportInput(BaseModel):
    """generate_report 工具的输入参数"""
    output_dir: Optional[str] = Field(
        default=None,
        description="报告输出目录，默认为None（使用默认目录）"
    )


__all__ = [
    "ReadFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFileContentInput",
    "SearchFilesByNameInput",
    "GenerateReportInput",
]
