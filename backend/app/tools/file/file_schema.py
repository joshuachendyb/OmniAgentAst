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
        description="要读取的文件路径(绝对路径)。支持文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"
    )
    offset: Optional[int] = Field(
        default=None,
        description="读取模式：不传=读全文；负数=从尾倒数(如-20返回末20行,此时limit无效)；正数=分页起始行(必须配合limit)"
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="最大读取行数。仅offset为正数时有效(分页模式)"
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
        description="文件的完整路径(绝对路径,支持中文路径)。用于写入文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"
    )
    content: str = Field(
        description="要写入文件的文本内容"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。追加时检测已有文件编码,新建时默认为utf-8。也可指定gbk/gb2312等"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=追加,False=覆盖"
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
        description="目标文件的绝对路径(仅支持文本文件)"
    )
    old_string: str = Field(
        description="待替换的旧字符串。若需替换所有匹配项请设replace_all=True"
    )
    new_string: str = Field(
        default="",
        description="替换的新字符串。传空字符串''表示删除匹配到的文本"
    )
    replace_all: bool = Field(
        default=False,
        description="是否替换所有匹配项,默认False只替换第一个"
    )
    ignore_case: bool = Field(
        default=False,
        description="是否忽略大小写,默认False"
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
    tree: bool = Field(
        default=False,
        description="是否以目录树形式列出。True=仅显示目录层级(不含文件节点,输出紧凑,统计信息仍含文件数),False=扁平列表(当前层所有文件+目录),默认False"
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
    search_dir: str = Field(
        description="搜索路径(绝对路径,必填)"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件过滤(glob通配符),如 \"*.py\"、\"*.{js,ts}\""
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    output_mode: Literal["content", "count", "files_with_matches"] = Field(
        default="content",
        description="输出模式: content=返回匹配内容(默认), count=只返回匹配数量, files_with_matches=只返回文件名列表(节省token)"
    )



# ============================================================
# F8: compress_files — 压缩文件
# ============================================================

class CompressFilesInput(BaseModel):
    source: str = Field(description="要压缩的文件/目录路径(绝对路径),支持通配符如*.txt")
    destination: str = Field(description="输出压缩包路径(绝对路径,必填)")
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
    source: str = Field(description="压缩包路径(绝对路径,必填)。支持格式:zip/tar/tar.gz/tar.bz2")
    destination: Optional[str] = Field(
        default=None, description="解压目标目录(绝对路径,可选,默认自动创建同名目录)"
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
    preserve_metadata: bool = Field(default=True, description="是否保留文件元数据(修改时间等),默认True")



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
# ============================================================
# __all__ — 13个工具的Schema导出
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
]
