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
from typing import Optional, List, Dict, Any, Literal


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
        default=500,
        ge=1,
        le=10000,
        description="最大读取行数，默认为500行，最大10000行"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认为utf-8"
    )


class WriteTextFileInput(BaseModel):
    """write_text_file 工具的输入参数 - 小健 2026-05-02"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径）"
    )
    text: str = Field(
        description="要写入文件的文本内容"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认为utf-8"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=在文件末尾追加内容，False=覆盖写入（默认）。对.log文件Agent可自动设为True"
    )
    create_parents: bool = Field(
        default=True,
        description="是否自动创建父目录，默认为True。若父目录不存在则自动创建"
    )
    unescape: bool = Field(
        default=True,
        description="是否自动反转义转义字符（如 \\n 转为真实换行、\\\" 转为引号），默认为True"
    )


class WriteFileInput(WriteTextFileInput):
    """write_file 兼容别名 - 小健 2026-05-02"""
    pass


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
        description="分页令牌（位置编码），用于获取下一页结果"
    )
    sortBy: str = Field(
        default="name",
        description="排序方式。可选值：name（按名称字母排序，默认值）、size（按文件大小排序，从大到小）"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件（以.开头的文件），默认为False"
    )


class DeleteFileInput(BaseModel):
    """delete_file 工具的输入参数 - 小健 2026-05-02 增加force"""
    file_path: str = Field(
        description="要删除的文件或目录的完整路径"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归删除目录（目录非空时需要设为True）"
    )
    force: bool = Field(
        default=False,
        description="是否强制删除只读文件。遇到只读文件报错时，设为True可自动解除只读属性后删除，默认为False"
    )


class MoveFileInput(BaseModel):
    """move_file 工具的输入参数 - 小健 2026-05-02 增加overwrite"""
    source_path: str = Field(
        description="源文件或目录的完整路径"
    )
    destination_path: str = Field(
        description="目标路径（可以是新文件名或新目录位置）"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在的目标文件，默认为False（不覆盖，目标存在时报错）"
    )


class SearchFileContentInput(BaseModel):
    """search_file_content 工具的输入参数"""
    pattern: str = Field(
        description="搜索内容的关键字（必填，不能为空）"
    )
    path: str = Field(
        default="~",
        description="搜索的起始目录（绝对路径），默认为用户主目录"
    )
    file_pattern: str = Field(
        default="*",
        description="文件名匹配模式，支持通配符（* 匹配任意字符），默认为*（所有文件）"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录，默认为True"
    )
    # 【新增】分页令牌，用于获取下一页结果
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌（位置编码），用于获取下一页结果"
    )


class SearchFilesInput(BaseModel):
    """search_files 工具的输入参数 - 小健 2026-05-02 增加excludePatterns/ignore_case/type"""
    file_pattern: str = Field(
        description="文件名匹配模式，支持通配符（* 匹配任意字符，? 匹配单个字符）"
    )
    path: str = Field(
        default="~",
        description="搜索的起始目录（绝对路径），默认为用户主目录"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归搜索子目录，默认为True"
    )
    max_depth: int = Field(
        default=100000,
        ge=1,
        description="最大递归深度，仅当recursive=True时有效，默认为100000"
    )
    excludePatterns: Optional[List[str]] = Field(
        default=None,
        description="排除模式数组，符合排除模式的目录/文件不会包含在结果中。如 ['node_modules', '.git', '__pycache__']"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写匹配文件名，默认为True（Windows风格）。设为False则大小写敏感"
    )
    type: Optional[str] = Field(
        default=None,
        description="搜索类型过滤：'file'只返回文件，'directory'只返回目录，None(默认)两者都返回"
    )
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌（位置编码），用于获取下一页结果"
    )


class GenerateReportInput(BaseModel):
    """generate_report 工具的输入参数"""
    output_dir: Optional[str] = Field(
        default=None,
        description="报告输出目录，默认为None（使用默认目录）"
    )


class CopyFileInput(BaseModel):
    """copy_file 工具的输入参数 - 小健 2026-05-02 增强"""
    source_path: str = Field(
        description="源文件或目录的完整路径（必须是绝对路径）"
    )
    destination_path: str = Field(
        description="目标路径（可以是新文件名或新目录位置）"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归复制目录，仅当源路径是目录时有效，默认为False"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在的目标文件，默认为False（不覆盖）"
    )
    preserve_metadata: bool = Field(
        default=True,
        description="是否保留文件元数据（修改时间、访问时间等），默认为True。若用户意图是'备份'，Agent自动设True；若仅需内容不需元数据可设False"
    )


class CreateDirectoryInput(BaseModel):
    """create_directory 工具的输入参数"""
    dir_path: str = Field(
        description="要创建的目录的完整路径（必须是绝对路径）"
    )
    parents: bool = Field(
        default=True,
        description="是否创建父目录，默认为True（如果父目录不存在则创建）"
    )
    exist_ok: bool = Field(
        default=True,
        description="如果目录已存在是否报错，默认为True（不报错）"
    )


class GetFileInfoInput(BaseModel):
    """get_file_info 工具的输入参数 - 小健 2026-05-02 增加follow_symlinks"""
    file_path: str = Field(
        description="文件或目录的完整路径（必须是绝对路径）"
    )
    follow_symlinks: bool = Field(
        default=True,
        description="是否跟随符号链接获取真实文件信息，默认为True。设为False则获取链接文件本身的信息"
    )


class CompareFilesInput(BaseModel):
    """compare_files 工具的输入参数"""
    file_path1: str = Field(
        description="第一个文件的完整路径（必须是绝对路径）"
    )
    file_path2: str = Field(
        description="第二个文件的完整路径（必须是绝对路径）"
    )
    algorithm: str = Field(
        default="content",
        description="比较算法：content（内容）、size（大小）、mtime（修改时间）",
        pattern="^(content|size|mtime)$"
    )
    chunk_size: int = Field(
        default=8192,
        ge=1024,
        le=1048576,
        description="分块大小（字节），用于大文件比较，默认8192字节"
    )


class BatchRenameInput(BaseModel):
    """batch_rename 工具的输入参数"""
    directory: str = Field(
        description="目标目录的完整路径（必须是绝对路径）"
    )
    pattern: str = Field(
        description="匹配模式（支持正则表达式）"
    )
    replacement: str = Field(
        description="替换字符串"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归处理子目录，默认为False"
    )
    preview: bool = Field(
        default=False,
        description="是否只预览不执行，默认为False"
    )
    conflict_strategy: Literal["skip", "overwrite", "rename"] = Field(
        default="skip",
        description="冲突处理策略：skip（跳过）、overwrite（覆盖）、rename（自动重命名），默认为skip"
    )


class CompressFilesInput(BaseModel):
    """compress_files 工具的输入参数"""
    source_path: str = Field(
        description="源文件或目录的完整路径（必须是绝对路径）"
    )
    destination_path: str = Field(
        description="目标压缩文件路径（必须是绝对路径）"
    )
    format: Literal["zip", "tar.gz"] = Field(
        default="zip",
        description="压缩格式：zip、tar.gz，默认为zip"
    )
    compression_level: int = Field(
        default=6,
        ge=0,
        le=9,
        description="压缩级别（0-9，0不压缩，9最高压缩），默认为6"
    )
    password: Optional[str] = Field(
        default=None,
        description="压缩密码（可选），用于加密压缩文件"
    )
    split_size: Optional[int] = Field(
        default=None,
        ge=1024,
        description="分卷大小（字节），None表示不分卷"
    )


class FileMonitorInput(BaseModel):
    """file_monitor 工具的输入参数"""
    directory: str = Field(
        description="监控目录的完整路径（必须是绝对路径）"
    )
    event_types: List[str] = Field(
        default=["created", "modified", "deleted", "renamed"],
        description="监控事件类型列表，默认为所有事件类型"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归监控子目录，默认为True"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="过滤条件字典，支持file_type、min_size、max_size、modified_after等字段"
    )
    duration: Optional[int] = Field(
        default=None,
        ge=1,
        description="监控持续时间（秒），None表示持续监控直到手动停止"
    )


class FileStatisticsInput(BaseModel):
    """file_statistics 工具的输入参数"""
    directory: str = Field(
        description="统计目录的完整路径（必须是绝对路径）"
    )
    recursive: bool = Field(
        default=True,
        description="是否递归统计子目录，默认为True"
    )
    max_depth: int = Field(
        default=100000,
        ge=1,
        description="最大递归深度，默认为100000"
    )
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="过滤条件字典，支持file_type、min_size、max_size等字段"
    )
    output_format: str = Field(
        default="json",
        description="输出格式：json、csv、text，默认为json"
    )


class ReadTextFileInput(BaseModel):
    """read_text_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径，必须是绝对路径，支持中文路径（如 D:/文档/测试.txt）"
    )
    head: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取文件的前 N 行，不能与 tail 参数同时使用。用于只查看文件开头部分内容"
    )
    tail: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="读取文件的后 N 行，不能与 head 参数同时使用。用于查看文件末尾部分内容，如日志文件的最新记录"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。可选参数，由 Agent 根据文件内容自动检测。常见值：utf-8（默认）、gbk、gb2312、utf-8-sig"
    )


class ReadMediaFileInput(BaseModel):
    """read_media_file 工具的输入参数"""
    file_path: str = Field(
        description="媒体文件的完整路径，必须是绝对路径，支持图片（JPG、PNG、GIF、BMP、WebP）和音频（MP3、WAV、OGG、M4A）格式"
    )


class ReadBatchFileInput(BaseModel):
    """read_batch_file 工具的输入参数"""
    file_paths: List[str] = Field(
        description="文件路径数组，每个元素必须是文件的完整绝对路径，支持中文路径。数组长度建议不超过100个文件"
    )


class PreciseReplaceInFileInput(BaseModel):
    """precise_replace_in_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的绝对路径，支持中文路径（如 D:/项目/代码/main.py）"
    )
    old_string: str = Field(
        description="要替换的精确文本，支持中文。必须是文件中确实存在的文本，进行精确匹配（非正则表达式）"
    )
    new_string: str = Field(
        description="替换后的文本，支持中文。用于替换 old_string 的内容"
    )
    replace_all: bool = Field(
        default=False,
        description="是否替换所有匹配项。设置为 true 时替换文件中所有匹配的 old_string，设置为 false 时只替换第一个匹配项"
    )
    ignore_case: bool = Field(
        default=False,
        description="是否忽略大小写。由 Agent 根据上下文智能判断"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。由 Agent 根据文件内容自动检测。常见值：utf-8、gbk、gb2312"
    )


class EditFileInput(BaseModel):
    """edit_file 工具的输入参数"""
    file_path: str = Field(
        description="要编辑的文件路径，支持中文路径"
    )
    edits: List[Dict[str, str]] = Field(
        description="编辑操作数组，每个元素包含 oldText（要替换的文本）和 newText（替换后的文本），支持同时执行多个编辑操作"
    )
    dryRun: bool = Field(
        default=False,
        description="预览模式。设置为 true 时只返回修改后的内容预览，不实际修改文件；设置为 false 时执行实际修改"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。可选参数，由 Agent 根据文件内容自动检测。常见值：utf-8、gbk、gb2312"
    )


class RenameFileInput(BaseModel):
    """rename_file 工具的输入参数"""
    file_path: str = Field(
        description="当前文件或目录的路径。必须是已存在的文件或目录"
    )
    new_name: str = Field(
        description="新的文件名或目录名。不能包含路径分隔符，只输入文件名或目录名"
    )


class GlobFilesInput(BaseModel):
    """glob_files 工具的输入参数"""
    pattern: str = Field(
        description="Glob 模式，用于匹配文件名。如 \"**/*.js\" 匹配所有 JS 文件，\"src/**/*.ts\" 匹配 src 目录下所有 TS 文件，\"*.py\" 匹配当前目录所有 Python 文件"
    )
    search_dir: Optional[str] = Field(
        default=None,
        description="搜索目录，默认为当前工作目录。必须是绝对路径，支持中文目录名"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否包含隐藏文件（如 .env、.gitignore）。Agent 智能判断"
    )


class GrepFileContentInput(BaseModel):
    """grep_file_content 工具的输入参数"""
    pattern: str = Field(
        description="正则表达式搜索模式，支持中文内容搜索。常用示例：搜索\"函数定义\"或\"class.*方法\""
    )
    search_dir: Optional[str] = Field(
        default=None,
        description="搜索路径，默认当前目录。必须是绝对路径，支持中文目录名"
    )
    output_mode: Optional[str] = Field(
        default=None,
        description="输出模式。可选值：content（显示匹配行的内容）、files_with_matches（只显示包含匹配的文件名）、count（显示每个文件的匹配数量）"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件类型过滤，使用 glob 通配符。例如：\"*.ts\" 只搜索 TS 文件，\"*.{js,py}\" 搜索 JS 和 Python 文件"
    )
    type: Optional[str] = Field(
        default=None,
        description="语言类型，简化 glob 匹配。常用值：js（JavaScript）、py（Python）、rust、html、json 等"
    )
    after_lines: Optional[int] = Field(
        default=None,
        ge=0,
        le=1000,
        description="匹配行之后额外显示的行数，用于查看后续上下文"
    )
    before_lines: Optional[int] = Field(
        default=None,
        ge=0,
        le=1000,
        description="匹配行之前额外显示的行数，用于查看前面上下文"
    )
    context_lines: Optional[int] = Field(
        default=None,
        ge=0,
        le=500,
        description="匹配行前后各显示的行数，同时设置 before 和 after，用于查看完整上下文"
    )
    ignore_case: bool = Field(
        default=False,
        description="搜索时是否忽略大小写。设置为 true 时，\"test\" 会匹配 \"Test\" 和 \"TEST\"。默认 false"
    )
    show_line_no: bool = Field(
        default=False,
        description="是否在输出中显示行号，便于定位。默认 false"
    )
    multiline: bool = Field(
        default=False,
        description="启用多行匹配模式，允许正则表达式中的 . 匹配换行符。默认 false"
    )
    head_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=100000,
        description="限制返回的匹配结果数量，用于大文件搜索避免输出过多"
    )



class GetDirectoryTreeInput(BaseModel):
    """get_directory_tree 工具的输入参数"""
    dir_path: str = Field(
        description="起始目录，必须是绝对路径，支持中文目录名"
    )
    excludePatterns: Optional[List[str]] = Field(
        default=None,
        description="排除模式数组，符合排除模式的目录不会包含在结果中。格式为 glob 通配符，如 [\"node_modules\", \"__pycache__\", \"*.pyc\"]"
    )
    max_depth: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="最大递归深度。可选参数，由 Agent 根据系统资源和目录规模动态设置。若未设置则默认无限制。"
    )


class ListAllowedDirectoriesInput(BaseModel):
    """list_allowed_directories 工具的输入参数"""
    pass


class FileChecksumInput(BaseModel):
    """file_checksum 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径）"
    )
    algorithm: str = Field(
        default="md5",
        description="哈希算法：md5、sha1、sha256、sha512，默认为md5"
    )
    verify_hash: Optional[str] = Field(
        default=None,
        description="验证哈希值（如果提供则进行验证）"
    )
    chunk_size: int = Field(
        default=65536,
        ge=1024,
        le=1048576,
        description="分块大小（字节），用于大文件哈希计算，默认65536字节"
    )


__all__ = [
    "ReadFileInput",
    "WriteTextFileInput",
    "WriteFileInput",
    "ListDirectoryInput",
    "DeleteFileInput",
    "MoveFileInput",
    "SearchFileContentInput",
    "SearchFilesInput",
    "GenerateReportInput",
    "CopyFileInput",
    "CreateDirectoryInput",
    "GetFileInfoInput",
    "CompareFilesInput",
    "BatchRenameInput",
    "CompressFilesInput",
    "FileMonitorInput",
    "FileStatisticsInput",
    "FileChecksumInput",
    "ReadTextFileInput",
    "ReadMediaFileInput",
    "ReadBatchFileInput",
    "PreciseReplaceInFileInput",
    "EditFileInput",
    "RenameFileInput",
    "GlobFilesInput",
    "GrepFileContentInput",
    "ListDirectoryWithSizesInput",
    "GetDirectoryTreeInput",
    "ListAllowedDirectoriesInput",
]
