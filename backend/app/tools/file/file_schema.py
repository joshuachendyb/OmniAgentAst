# -*- coding: utf-8 -*-
"""
File Schema - 文件工具参数模型

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

Author: 小沈 - 2026-03-21
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union


# ============================================================
# F1: read_text_file — 读取文本文件
# ============================================================

# ⚠️ Pydantic class docstring 会进入 JSON Schema 的 parameters.description 并发给 LLM
# 禁止在这里写文档字符串。工具描述写在 file_register.py 的 FILE_TOOL_DESCRIPTIONS 里。
class ReadTextFileInput(BaseModel):
    file_path: str = Field(
        description="要读取的文件路径(绝对路径)"
    )
    head: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取前N行(仅单文件模式,不能与tail/offset同时使用)"
    )
    tail: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取后N行(仅单文件模式,不能与head/offset同时使用)"
    )
    offset: Optional[int] = Field(
        default=None,
        ge=1,
        le=10000000,
        description="起始行号,1-indexed(仅单文件模式,不能与head/tail同时使用,配合limit分页读取)"
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="最大读取行数(仅单文件模式,配合offset分页读取)"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码,默认utf-8。读取失败时自动尝试gbk/gb2312/utf-8-sig"
    )



# ============================================================
# F2: write_text_file — 写文本文件
# ============================================================

class WriteTextFileInput(BaseModel):
    file_path: str = Field(
        description="文件的完整路径(必须是绝对路径,支持中文路径)"
    )
    content: str = Field(
        description="要写入文件的文本内容(必须是实际内容,禁止传入思考/计划/状态描述)"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。追加时检测已有文件编码,新建时默认为utf-8。也可指定gbk/gb2312等"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=追加,False=覆盖。对.log文件Agent可自动设为True"
    )


# ============================================================
# F3: read_media_file — 读媒体文件
# ============================================================

class ReadMediaFileInput(BaseModel):
    file_path: str = Field(
        description="媒体文件的完整路径。支持图片(JPG/PNG/GIF/BMP/WebP/SVG/ICO/TIFF)、音频(MP3/WAV/OGG/M4A/FLAC/AAC)、视频(MP4/AVI/MOV/MKV)。返回Base64编码数据"
    )


# ============================================================
# F4: edit_text_file — 编辑文本文件
# ============================================================

class EditTextFileInput(BaseModel):
    file_path: str = Field(
        description="目标文件的绝对路径(仅支持文本文件,二进制文件将被拒绝)"
    )
    old_string: str = Field(
        description="待替换的旧字符串(必须唯一，若需替换所有匹配项请设 replace_all=True)"
    )
    new_string: str = Field(
        default="",
        description="替换的新字符串。传空字符串 '' 表示删除匹配到的文本"
    )
    replace_all: bool = Field(
        default=False,
        description="是否替换所有匹配项,默认False只替换第一个"
    )

    encoding: Optional[str] = Field(
        default=None,
        description="文件编码,默认utf-8"
    )



# ============================================================
# F5: list_directory — 列出目录内容
# ============================================================

class ListDirectoryInput(BaseModel):
    dir_path: str = Field(
        description="目录路径(绝对路径,必填)。如 D:/项目代码"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归列出子目录。True=树形结构(含所有层级),False=扁平列表(仅当前层),默认False"
    )
    sort_by: Literal["name", "size", "mtime"] = Field(
        default="name",
        description="排序方式:name/size/mtime,默认name"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件),默认False"
    )


# ============================================================
# F6: search_files — 搜索文件名
# ============================================================

class SearchFilesInput(BaseModel):
    pattern: str = Field(
        description="文件名匹配模式,支持glob通配符(* ? **)和中文文件名。如 \"*.py\"、\"**/*.ts\"、\"config*\""
    )
    search_dir: str = Field(
        description="搜索的起始目录(绝对路径,必填)。如 D:/项目代码"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录,默认True"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    type: Optional[Literal["file", "directory"]] = Field(
        default=None,
        description="搜索类型过滤:file=只返回文件,directory=只返回目录,不设则全部返回"
    )


# ============================================================
# F7: grep_file_content — 搜索文件内容
# ============================================================

class GrepFileContentInput(BaseModel):
    pattern: str = Field(
        description="正则表达式搜索模式,支持中文内容搜索。如 \"def read_file\" 或 \"class.*Component\""
    )
    search_dir: Optional[str] = Field(
        default=None,
        description="搜索路径(绝对路径),默认当前目录"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件过滤(glob通配符),如 \"*.py\"、\"*.{js,ts}\""
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )



# ============================================================
# F8: compress_files — 压缩文件
# ============================================================

class CompressFilesInput(BaseModel):
    source: str = Field(description="要压缩的文件/目录路径(必填),支持通配符如*.txt")
    destination: str = Field(description="输出压缩包路径(必填)")
    format: Literal["zip", "tar", "tar.gz", "tar.bz2"] = Field(
        default="zip", description="压缩格式:zip/tar/tar.gz/tar.bz2,默认zip"
    )

    password: Optional[str] = Field(default=None, description="ZIP加密密码,设置后创建AES-256加密ZIP,仅ZIP格式支持,可选")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件,默认False")
    exclude_patterns: Optional[List[str]] = Field(
        default=None, description="排除的文件/目录模式列表,如 ['node_modules', '__pycache__']"
    )


# ============================================================
# F8b: extract_archive — 解压文件
# ============================================================

class ExtractArchiveInput(BaseModel):
    source: str = Field(description="压缩包路径(必填)")
    destination: Optional[str] = Field(
        default=None, description="解压目标目录(可选,默认自动创建同名目录)"
    )
    password: Optional[str] = Field(default=None, description="解密密码(仅ZIP格式支持),可选")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件,默认False")


# ============================================================
# F9a: move_file — 移动文件
# ============================================================

class MoveFileInput(BaseModel):
    source: str = Field(description="源文件路径(绝对路径)")
    destination: str = Field(description="目标路径(绝对路径)")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件,默认False")


# ============================================================
# F9b: copy_file — 复制文件
# ============================================================

class CopyFileInput(BaseModel):
    source: str = Field(description="源文件路径(绝对路径)")
    destination: str = Field(description="目标路径(绝对路径)")
    recursive: bool = Field(default=False, description="复制目录时需True,默认False")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件,默认False")



# ============================================================
# F9c: delete_file — 删除文件
# ============================================================

class DeleteFileInput(BaseModel):
    source: str = Field(description="要删除的文件/目录路径(绝对路径)")
    recursive: bool = Field(default=False, description="删除非空目录时需True,默认False")
    force: bool = Field(default=False, description="True=跳过回收站永久删除,False=放入回收站。默认False")


# ============================================================
# F9d: rename_file — 重命名文件
# ============================================================

class RenameFileInput(BaseModel):
    source: str = Field(description="原文件/目录路径(绝对路径)")
    destination: str = Field(description="新名称(仅文件名,不含目录路径)")


# ============================================================
# F11a: read_data_file — 读取结构化配置文件
# ============================================================

class ReadDataFileInput(BaseModel):
    file_path: str = Field(
        description="文件路径(必须是绝对路径)"
    )
    format: Optional[Literal["json", "yaml", "toml", "ini", "xml", "properties"]] = Field(
        default=None,
        description="强制指定格式:json/yaml/toml/ini/xml/properties。不填则根据文件扩展名自动检测"
    )



# ============================================================
# F11b: write_data_file — 写入结构化配置文件
# ============================================================

class WriteDataFileInput(BaseModel):
    file_path: str = Field(
        description="文件路径(必须是绝对路径)"
    )
    data: Any = Field(
        description="写入数据。JSON/YAML/TOML格式传dict或list,Properties传dict。INI/XML暂不支持写入"
    )
    format: Optional[Literal["json", "yaml", "toml"]] = Field(
        default=None,
        description="强制指定格式:json/yaml/toml。不填则根据文件扩展名自动检测"
    )




# ============================================================
# ============================================================
# __all__ — 15个工具的Schema导出
# ============================================================

__all__ = [
    "ReadTextFileInput",
    "WriteTextFileInput",
    "ReadMediaFileInput",
    "EditTextFileInput",
    "ListDirectoryInput",
    "SearchFilesInput",
    "GrepFileContentInput",

    "CompressFilesInput",
    "ExtractArchiveInput",
    "MoveFileInput",
    "CopyFileInput",
    "DeleteFileInput",
    "RenameFileInput",
    "ReadDataFileInput",
    "WriteDataFileInput",
]
