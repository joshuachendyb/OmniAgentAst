# -*- coding: utf-8 -*-
"""
File 工具参数 Schema 定义 — 精简版 v2.0

【创建时间】2026-03-21 小沈
【精简时间】2026-05-18 小沈 — 第17章工具精简：26→11

职责：
定义 file 分类的11个工具的参数 Pydantic 模型。

11个工具清单（F1-F11）：
F1  read_file          — 合并read_text_file + read_batch_file
F2  write_text_file    — 写文本文件
F3  read_media_file    — 读媒体文件
F4  edit_file          — 合并precise_replace_in_file + edit_text_file
F5  list_directory     — 合并list_directory + get_directory_tree + file_statistics
F6  search_files       — 搜索文件名
F7  grep_file_content  — 搜索文件内容
F8  rename_file        — 合并rename_file + batch_rename
F9  archive_tool       — 合并compress_files + extract_archive
F10 file_operation     — 合并move_file + copy_file + delete_file
F11 data_file_format   — 合并json/yaml/toml/ini/xml/properties

Author: 小沈 - 2026-03-21
更新: 小沈 - 2026-05-18 精简为11个工具
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union


# ============================================================
# F1: read_file — 合并read_text_file + read_batch_file
# ============================================================

class ReadFileInput(BaseModel):
    """read_file 统一入口 — 小沈 2026-05-18
    
    合并 read_text_file + read_batch_file
    - 传入1个路径：单文件模式，支持 head/tail/offset/limit 分页
    - 传入多个路径：批量模式，每个文件返回完整内容
    
    【小沈 2026-05-19】合并file_path+file_paths→file_paths，消除LLM双参数混淆
    """
    file_paths: List[str] = Field(
        min_length=1,
        max_length=100,
        description="文件路径列表。传1个路径=单文件模式(支持head/tail/offset/limit分页)；传多个=批量模式(读取完整内容)"
    )
    head: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取前N行（仅单文件模式，不能与tail/offset同时使用）"
    )
    tail: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取后N行（仅单文件模式，不能与head/offset同时使用）"
    )
    offset: Optional[int] = Field(
        default=None,
        ge=1,
        le=10000000,
        description="起始行号，1-indexed（仅单文件模式，不能与head/tail同时使用，配合limit分页读取）"
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="最大读取行数（仅单文件模式，配合offset分页读取）"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码，默认utf-8。读取失败时自动尝试gbk/gb2312/utf-8-sig"
    )


# ============================================================
# F2: write_text_file — 写文本文件
# ============================================================

class WriteTextFileInput(BaseModel):
    """write_text_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径，支持中文路径）"
    )
    text: str = Field(
        description="要写入文件的文本内容（必须是实际内容，禁止传入思考/计划/状态描述）"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。追加时检测已有文件编码，新建时默认为utf-8。也可指定gbk/gb2312等"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=追加，False=覆盖。对.log文件Agent可自动设为True"
    )
    create_parents: bool = Field(
        default=True,
        description="是否自动创建父目录，默认为True。若父目录不存在则自动创建"
    )
    unescape: bool = Field(
        default=True,
        description="是否自动反转义转义字符（如 \\n 转为真实换行、\\\" 转为引号），默认为True"
    )


# ============================================================
# F3: read_media_file — 读媒体文件
# ============================================================

class ReadMediaFileInput(BaseModel):
    """read_media_file 工具的输入参数"""
    file_path: str = Field(
        description="媒体文件的完整路径。支持图片(JPG/PNG/GIF/BMP/WebP/SVG/ICO/TIFF)、音频(MP3/WAV/OGG/M4A/FLAC/AAC)、视频(MP4/AVI/MOV/MKV)。返回Base64编码数据"
    )


# ============================================================
# F4: edit_file — 合并precise_replace_in_file + edit_text_file
# ============================================================

class EditFileInput(BaseModel):
    """edit_file 统一入口 — 小沈 2026-05-19 精简8→7参数

    合并 precise_replace_in_file + edit_text_file
    - old_string+new_string: 单处精确替换
    - edits: 多处结构化编辑

    P17互斥校验：old_string 和 edits 不能同时传入
    """
    file_path: str = Field(
        description="目标文件的绝对路径（仅支持文本文件，二进制文件将被拒绝）"
    )
    old_string: Optional[str] = Field(
        default=None,
        description="待替换的旧字符串（与edits互斥，二选一）"
    )
    new_string: Optional[str] = Field(
        default=None,
        description="替换的新字符串（配合old_string使用）"
    )
    edits: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="多处编辑列表，每项含oldText和newText（与old_string互斥，二选一）"
    )
    replace_all: bool = Field(
        default=False,
        description="是否替换所有匹配项（仅old_string模式有效），默认False只替换第一个"
    )
    dry_run: bool = Field(
        default=False,
        description="预览模式，True=只预览不修改，默认False"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码，默认utf-8"
    )


# ============================================================
# F5: list_directory — 合并list_directory + get_directory_tree + file_statistics
# ============================================================

class ListDirectoryInput(BaseModel):
    """list_directory 统一入口 — 小沈 2026-05-19 精简8→7参数

    合并 list_directory + get_directory_tree + file_statistics
    - format="list": 扁平列表（原list_directory）
    - format="tree": JSON树结构（原get_directory_tree）
    - 始终返回statistics统计信息（原file_statistics）
    """
    dir_path: str = Field(
        description="目录路径（绝对路径，必填）。如 D:/项目代码"
    )
    format: Literal["list", "tree"] = Field(
        default="list",
        description="输出格式：list（扁平列表）或 tree（JSON树结构），默认list"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归列出所有子目录，默认False"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大递归深度，仅当recursive=True时有效，默认10"
    )
    sortBy: Literal["name", "size", "mtime"] = Field(
        default="name",
        description="排序方式：name/size/mtime，默认name"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件（以.开头的文件），默认False"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌，用于获取后续页面结果"
    )


# ============================================================
# F6: search_files — 搜索文件名
# ============================================================

class SearchFilesInput(BaseModel):
    """search_files 工具的输入参数 — 小沈 2026-05-19 精简9→7参数"""
    pattern: str = Field(
        description="文件名匹配模式，支持glob通配符（* ? **）和中文文件名。如 \"*.py\"、\"**/*.ts\"、\"config*\""
    )
    search_dir: str = Field(
        description="搜索的起始目录（绝对路径，必填）。如 D:/项目代码"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录，默认True"
    )
    max_depth: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="最大递归深度，仅当recursive=True时有效，默认50"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写，默认True"
    )
    type: Optional[Literal["file", "directory"]] = Field(
        default=None,
        description="搜索类型过滤：file=只返回文件，directory=只返回目录，不设则全部返回"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌，用于获取下一页结果"
    )


# ============================================================
# F7: grep_file_content — 搜索文件内容
# ============================================================

class GrepFileContentInput(BaseModel):
    """grep_file_content 工具的输入参数 — 小沈 2026-05-19 精简13→9参数"""
    pattern: str = Field(
        description="正则表达式搜索模式，支持中文内容搜索。如 \"def read_file\" 或 \"class.*Component\""
    )
    search_dir: Optional[str] = Field(
        default=None,
        description="搜索路径（绝对路径），默认当前目录"
    )
    output_mode: Optional[Literal["content", "files_with_matches", "count"]] = Field(
        default=None,
        description="输出模式，默认content。content=显示匹配行内容，files_with_matches=只返回匹配的文件名列表，count=只返回每个文件的匹配数量"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件过滤（glob通配符），如 \"*.py\"、\"*.{js,ts}\""
    )
    context: Optional[Dict[str, int]] = Field(
        default=None,
        description="上下文行数（可选）：{\"after\":N}匹配后N行, {\"before\":N}匹配前N行, {\"around\":N}上下各N行。如 {\"around\":3}"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写，默认True"
    )
    head_limit: Optional[int] = Field(
        default=None,
        description="限制返回的最大匹配行数，避免结果过多。不设则返回全部"
    )
    multiline: bool = Field(
        default=False,
        description="是否启用多行匹配模式，默认False"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌，用于获取下一页结果"
    )


# ============================================================
# F8: rename_file — 合并rename_file + batch_rename
# ============================================================

class RenameFileInput(BaseModel):
    """rename_file — 小沈 2026-05-19 精简9→6参数

    - mode="single": file_path+new_name 单文件重命名
    - mode="batch": directory+pattern+replacement 批量正则重命名
    """
    mode: Literal["single", "batch"] = Field(
        default="single",
        description="模式：single=单文件(file_path+new_name)，batch=批量(directory+pattern+replacement)"
    )
    file_path: Optional[str] = Field(
        default=None,
        description="单文件路径（mode=single时必填）"
    )
    new_name: Optional[str] = Field(
        default=None,
        description="新文件名（mode=single时必填）。仅文件名，不能含路径分隔符(/或\\)，不能含Windows非法字符(<>:\"|?*)"
    )
    directory: Optional[str] = Field(
        default=None,
        description="批量重命名的目录（mode=batch时必填）"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="匹配正则表达式（mode=batch时必填）"
    )
    replacement: Optional[str] = Field(
        default=None,
        description="替换字符串，支持反向引用如 \\1（mode=batch时必填）"
    )


# ============================================================
# F9: archive_tool — 合并compress_files + extract_archive
# ============================================================

class ArchiveToolInput(BaseModel):
    """archive_tool 统一入口 — 小沈 2026-05-19 精简11→8参数

    合并 compress_files + extract_archive
    - action="compress": source=源路径, destination=输出压缩包路径
    - action="extract": source=压缩包路径, destination=解压目标目录(可选)
    """
    action: Literal["compress", "extract"] = Field(
        description="操作类型：compress（压缩）或 extract（解压）"
    )
    source: Optional[str] = Field(
        default=None,
        description="源路径。compress=要压缩的文件/目录路径(必填)；extract=压缩包路径(必填)"
    )
    destination: Optional[str] = Field(
        default=None,
        description="目标路径。compress=输出压缩包路径(必填)；extract=解压目标目录(可选，默认自动创建同名目录)"
    )
    format: Literal["zip", "tar", "tar.gz", "tar.bz2"] = Field(
        default="zip",
        description="压缩格式：zip/tar/tar.gz/tar.bz2，默认zip"
    )
    compression_level: int = Field(
        default=6,
        ge=0,
        le=9,
        description="压缩级别0-9（0=不压缩，6=平衡，9=最高），默认6"
    )
    password: Optional[str] = Field(
        default=None,
        description="加密/解密密码（仅ZIP格式支持），可选"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在文件，默认False"
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="compress模式：排除的文件/目录模式列表，如 ['node_modules', '__pycache__']"
    )


# ============================================================
# F10: file_operation — 合并move_file + copy_file + delete_file
# ============================================================

class FileOperationInput(BaseModel):
    """file_operation 统一入口 — 小沈 2026-05-18

    合并 move_file + copy_file + delete_file
    - action="move": 移动文件/目录
    - action="copy": 复制文件/目录
    - action="delete": 删除文件/目录
    """
    action: Literal["move", "copy", "delete"] = Field(
        description="操作类型：move（移动）/ copy（复制）/ delete（删除）"
    )
    source: str = Field(
        description="源路径（move/copy: 源文件路径；delete: 要删除的路径）"
    )
    destination: Optional[str] = Field(
        default=None,
        description="目标路径。move和copy时必须填写（⚠️ delete模式不填），delete时自动忽略此参数"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归操作（copy目录/delete非空目录时需True），默认False"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖目标文件（move/copy有效），默认False"
    )
    force: bool = Field(
        default=False,
        description="仅delete模式有效：True=跳过回收站永久删除，False=放入回收站。默认False"
    )
    preserve_metadata: bool = Field(
        default=True,
        description="copy模式：是否保留文件元数据（修改时间/访问时间等），默认True"
    )


# ============================================================
# F11: data_file_format — 合并json/yaml/toml/ini/xml/properties
# ============================================================

class DataFileFormatInput(BaseModel):
    """data_file_format 统一入口 — 小沈 2026-05-18

    统一结构化配置格式（json/yaml/toml/ini/xml/properties）
    归入File分类（不是data_format分类）
    注意：CSV/Excel属于Document分类，不在本工具范围内
    限制：write模式仅支持json/yaml/toml，ini/xml/properties暂不支持写入
    """
    action: Literal["read", "write"] = Field(
        default="read",
        description="操作类型：read（读取）或 write（写入）"
    )
    file_path: str = Field(
        description="文件路径（必须是绝对路径）"
    )
    format: Optional[Literal["json", "yaml", "toml", "ini", "xml", "properties"]] = Field(
        default=None,
        description="强制指定格式：json/yaml/toml/ini/xml/properties。不填则根据文件扩展名自动检测"
    )
    data: Optional[Union[dict, list]] = Field(
        default=None,
        description="write模式要写入的数据。JSON/YAML/TOML格式传dict或list，Properties传dict。INI/XML暂不支持写入。read模式不填此字段"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认utf-8"
    )
    indent: Optional[int] = Field(
        default=None,
        description="JSON写入时的格式化缩进空格数（默认2），可选。YAML/TOML不支持此参数"
    )



# ============================================================
# __all__ — 11个工具的Schema导出
# ============================================================

__all__ = [
    "ReadFileInput",
    "WriteTextFileInput",
    "ReadMediaFileInput",
    "EditFileInput",
    "ListDirectoryInput",
    "SearchFilesInput",
    "GrepFileContentInput",
    "RenameFileInput",
    "ArchiveToolInput",
    "FileOperationInput",
    "DataFileFormatInput",
]
