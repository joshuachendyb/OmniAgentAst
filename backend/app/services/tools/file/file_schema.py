# -*- coding: utf-8 -*-
"""
File 工具参数 Schema 定义

职责:
定义 file 分类的工具参数 Pydantic 模型。

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
    create_parents: bool = Field(
        default=True,
        description="是否自动创建父目录,默认为True。若父目录不存在则自动创建"
    )
    unescape: bool = Field(
        default=True,
        description="是否自动反转义转义字符(如 \\n 转为真实换行、\\\" 转为引号),默认为True"
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
    dry_run: bool = Field(
        default=False,
        description="预览模式,True=只预览不修改,默认False"
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
    format: Literal["list", "tree"] = Field(
        default="list",
        description="输出格式:list(扁平列表)或 tree(JSON树结构),默认list"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归列出所有子目录,默认False"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大递归深度,仅当recursive=True时有效,默认10"
    )
    sortBy: Literal["name", "size", "mtime"] = Field(
        default="name",
        description="排序方式:name/size/mtime,默认name"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件),默认False"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌,用于获取后续页面结果"
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
    max_depth: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大递归深度,仅当recursive=True时有效,默认50"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    type: Optional[Literal["file", "directory"]] = Field(
        default=None,
        description="搜索类型过滤:file=只返回文件,directory=只返回目录,不设则全部返回"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌,用于获取下一页结果"
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
    output_mode: Optional[Literal["content", "files_with_matches", "count"]] = Field(
        default=None,
        description="输出模式,默认content。content=显示匹配行内容,files_with_matches=只返回匹配的文件名列表,count=只返回每个文件的匹配数量"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件过滤(glob通配符),如 \"*.py\"、\"*.{js,ts}\""
    )
    context: Optional[Dict[str, int]] = Field(
        default=None,
        description="上下文行数(可选):{\"after\":N}匹配后N行, {\"before\":N}匹配前N行, {\"around\":N}上下各N行。如 {\"around\":3}"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    head_limit: Optional[int] = Field(
        default=None,
        description="限制返回的最大匹配行数,避免结果过多。不设则返回全部"
    )
    multiline: bool = Field(
        default=False,
        description="是否启用多行匹配模式,默认False"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌,用于获取下一页结果"
    )


# ============================================================
# F8: compress_files — 压缩文件
# ============================================================

class CompressFilesInput(BaseModel):
    source: str = Field(description="要压缩的文件/目录路径(必填)")
    destination: str = Field(description="输出压缩包路径(必填)")
    format: Literal["zip", "tar", "tar.gz", "tar.bz2"] = Field(
        default="zip", description="压缩格式:zip/tar/tar.gz/tar.bz2,默认zip"
    )
    compression_level: int = Field(
        default=6, ge=0, le=9, description="压缩级别0-9(0=不压缩,6=平衡,9=最高),默认6"
    )
    password: Optional[str] = Field(default=None, description="加密密码(仅ZIP格式支持),可选")
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
    preserve_metadata: bool = Field(default=True, description="是否保留文件元数据(修改时间/访问时间等),默认True")


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
# F11: data_file_format — 结构化配置文件读写
# ============================================================

class DataFileFormatInput(BaseModel):
    action: Literal["read", "write"] = Field(
        default="read",
        description="操作类型:read(读取)或 write(写入)"
    )
    file_path: str = Field(
        description="文件路径(必须是绝对路径)"
    )
    format: Optional[Literal["json", "yaml", "toml", "ini", "xml", "properties"]] = Field(
        default=None,
        description="强制指定格式:json/yaml/toml/ini/xml/properties。不填则根据文件扩展名自动检测"
    )
    data: Optional[Any] = Field(
        default=None,
        description="写入数据(action=write时【必填】)。JSON/YAML/TOML格式传dict或list,Properties传dict。INI/XML暂不支持写入。action=read时忽略"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码,默认utf-8"
    )
    indent: Optional[int] = Field(
        default=None,
        description="JSON写入时的格式化缩进空格数(仅action=write且JSON格式时使用),默认2"
    )



# ============================================================
# ============================================================
# __all__ — 14个工具的Schema导出
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
    "DataFileFormatInput",
]
