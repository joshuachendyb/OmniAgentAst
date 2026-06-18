# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点 v3.0

【架构规范】2026-04-26 小沈
【精简时间】2026-05-18 小沈 — 第17章工具精简:26→11
【拆分时间】2026-06-16 小沈 — 组合工具拆分:archive_tool→2, file_operation→4
【拆分时间】2026-06-17 小欧 — data_file_format→2: read_data_file, write_data_file

15个工具清单(F1-F15):
F1  read_text_file     — 读取文本文件
F2  write_text_file    — 写文本文件
F3  read_media_file    — 读媒体文件
F4  edit_text_file     — 编辑文本文件
F5  list_directory     — 列出目录内容
F6  search_files       — 搜索文件名
F7  grep_file_content  — 搜索文件内容
F8  compress_files     — 压缩文件
F9  extract_archive    — 解压文件
F10 move_file          — 移动文件
F11 copy_file          — 复制文件
F12 delete_file        — 删除文件
F13 rename_file        — 重命名文件
F14 read_data_file     — 读取结构化配置文件
F15 write_data_file    — 写入结构化配置文件


创建时间: 2026-04-26
精简时间: 2026-05-18
拆分时间: 2026-06-16
更新时间: 2026-06-17
"""

from app.tools.file.file_schema import (
    CompressFilesInput,
    CopyFileInput,
    ReadDataFileInput,
    WriteDataFileInput,
    DeleteFileInput,
    EditTextFileInput,
    ExtractArchiveInput,
    GrepFileContentInput,
    ListDirectoryInput,
    MoveFileInput,
    ReadTextFileInput,
    ReadMediaFileInput,
    RenameFileInput,
    SearchFilesInput,
    WriteTextFileInput,
)

from app.tools.file.file_tools import FileTools, get_file_tools
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 文件工具依赖配置 — 小健 2026-06-18
# 文件工具使用内置库，无第三方依赖
FILE_TOOL_DEPENDENCIES = {
    tool_name: [] for tool_name in [
        "read_text_file", "write_text_file", "read_media_file", "edit_text_file",
        "list_directory", "search_files", "grep_file_content", "compress_files",
        "extract_archive", "move_file", "copy_file", "delete_file", "rename_file",
        "read_data_file", "write_data_file"
    ]
}


# ============================================================
# 工具描述(15个)
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "read_text_file": """读取文本文件。支持分页读取(head/tail/offset/limit)。encoding默认utf-8,读取失败自动尝试gbk。适用场景:需要读取源代码、日志文件、配置文件等纯文本内容时使用。""",

    "write_text_file": """写文本文件：创建新文件或追加内容。自动检测编码，支持中文路径。content 参数传入实际文件内容（禁止传入思考/状态描述），append=True 追加到末尾。适用场景:需要创建或修改代码文件、配置文件、日志文件等文本内容时使用。""",

    "read_media_file": """读取图片、音频、视频文件,返回Base64编码数据和MIME类型。自动识别媒体类型,支持常见图片(jpg/png/gif/bmp)、音频(mp3/wav/ogg)和视频(mp4/avi/mkv)格式。不支持PDF文件(PDF请使用read_pdf工具)。适用场景:需要获取非文本文件内容并将其传递给LLM进行图像识别、音频分析等任务。""",

    "edit_text_file": """替换文本文件中的内容。old_string定位被替换文本,new_string替换为的内容。replace_all替换所有匹配项,dry_run仅预览。适用场景:需要精确修改代码中的某个函数名、变量引用、配置值时使用。""",

    "list_directory": """列出目录内容,支持扁平列表(format="list")和JSON树结构(format="tree")两种输出格式。list格式返回包含文件大小/修改时间的条目列表,tree格式返回嵌套的JSON目录树。始终返回统计信息(文件数/目录数/总大小)。支持递归列出子目录、按名称/大小/修改时间排序、分页读取,以及过滤隐藏文件。适用场景:需要了解项目目录结构、查看文件大小和修改时间、获取文件统计信息时使用。""",

    "search_files": """递归搜索匹配glob模式的文件/目录。search_dir为必填的搜索起始目录。pattern支持glob通配符(*?**)和中文文件名。可指定搜索类型(文件/目录)、递归深度、大小写敏感。分页返回结果,每页包含匹配列表和总数。适用场景:需要按文件名查找特定文件、统计项目中某类文件数量时使用。""",

    "grep_file_content": """基于ripgrep在文件中搜索文本内容,支持正则表达式和中文搜索。可指定搜索路径、文件过滤(glob通配符,如"*.py")、匹配前后上下文行数、大小写敏感、多行匹配模式、返回条数限制。分页返回结果,包含匹配行内容、匹配文件和总匹配数。适用场景:需要在代码或文档中查找特定函数定义、关键字、TODO标记,并了解其上下文时使用。""",

    "compress_files": """压缩文件或目录为归档包。支持zip/tar/tar.gz/tar.bz2格式,可设置压缩级别(0-9)和加密密码(ZIP专用)。可排除指定文件/目录模式。适用场景:需要备份文件、打包项目、减小文件体积时使用。
使用示例: compress_files(source="D:/project", destination="D:/backup.zip")""",

    "extract_archive": """解压归档包到指定目录。支持zip/tar/tar.gz/tar.bz2格式,支持加密解压(ZIP专用)。destination可选,不填则自动创建同名目录。适用场景:需要解压下载的压缩包、恢复备份时使用。
使用示例: extract_archive(source="D:/backup.zip", destination="D:/output")""",

    "move_file": """移动文件或目录。同盘移动为原子操作(瞬间完成),跨盘移动先复制后删除。overwrite=True覆盖已存在目标。适用场景:需要整理文件位置、迁移文件时使用。
使用示例: move_file(source="D:/a.txt", destination="E:/b.txt")""",

    "copy_file": """复制文件或目录。复制目录需recursive=True。preserve_metadata=True保留修改时间/访问时间等元数据。overwrite=True覆盖已存在目标。适用场景:需要备份文件、复制模板时使用。
使用示例: copy_file(source="D:/a.txt", destination="D:/backup/a.txt")""",

    "delete_file": """删除文件或目录。默认放入回收站(可恢复),force=True永久删除(不可恢复)。删除非空目录需recursive=True。文件已不存在时返回成功(幂等)。适用场景:需要清理临时文件、删除过期数据时使用。
使用示例: delete_file(source="D:/temp.txt")""",

    "rename_file": """重命名文件或目录。destination只需提供新文件名(不含目录路径),在同一目录下重命名。适用场景:需要修改文件名、规范化命名时使用。
使用示例: rename_file(source="D:/old.txt", destination="new.txt")""",

    "read_data_file": """读取结构化配置文件,支持JSON/YAML/TOML/INI/XML/Properties格式。file_path为必填。自动检测格式(通过扩展名),也可通过format参数指定。适用场景:需要读取配置文件内容进行查看或分析时使用。""",

    "write_data_file": """写入结构化配置文件,支持JSON/YAML/TOML格式。file_path和data均为必填。不支持INI/XML/Properties格式写入。自动检测格式(通过扩展名),也可通过format参数指定。适用场景:需要创建或修改配置文件时使用。""",
}


# ============================================================
# 工具示例(15个)
# ============================================================

FILE_TOOL_EXAMPLES = {
    "read_text_file": [
        {"file_path": "D:/project/main.py"},
        {"file_path": "D:/project/main.py", "head": 10},
    ],
    "write_text_file": [
        {"file_path": "D:/output/test.txt", "content": "Hello World"},
        {"file_path": "D:/logs/app.log", "content": "[2026-05-18] Done\\n", "append": True},
    ],
    "read_media_file": [
        {"file_path": "D:/screenshot.png"},
    ],
    "edit_text_file": [
        {"file_path": "D:/main.py", "old_string": "def old():", "new_string": "def new():"},
        {"file_path": "D:/main.py", "old_string": "import os", "new_string": "import sys"},
    ],
    "list_directory": [
        {"dir_path": "D:/project"},
        {"dir_path": "D:/project", "recursive": True, "max_depth": 3},
        {"dir_path": "D:/project", "format": "tree"},
    ],
    "search_files": [
        {"pattern": "**/*.py", "search_dir": "D:/project"},
    ],
    "grep_file_content": [
        {"pattern": "def read_text_file", "search_dir": "D:/backend"},
        {"pattern": "TODO", "search_dir": "D:/src", "context": {"around": 3}},
    ],
    "compress_files": [
        {"source": "D:/project", "destination": "D:/backup.zip"},
    ],
    "extract_archive": [
        {"source": "D:/backup.zip", "destination": "D:/extracted"},
    ],
    "move_file": [
        {"source": "D:/a.txt", "destination": "E:/b.txt"},
    ],
    "copy_file": [
        {"source": "D:/a.txt", "destination": "D:/backup/a.txt"},
    ],
    "delete_file": [
        {"source": "D:/temp.txt"},
    ],
    "rename_file": [
        {"source": "D:/old.txt", "destination": "new.txt"},
    ],
    "read_data_file": [
        {"file_path": "D:/config.json"},
        {"file_path": "D:/config.yaml"},
    ],
    "write_data_file": [
        {"file_path": "D:/config.yaml", "data": {"key": "value"}},
        {"file_path": "D:/config.json", "data": {"key": "value"}, "indent": 2},
    ],
}


# ============================================================
# 工具名到Pydantic模型的映射(15个)
# ============================================================

TOOL_INPUT_MODELS = {
    "read_text_file": ReadTextFileInput,
    "write_text_file": WriteTextFileInput,
    "read_media_file": ReadMediaFileInput,
    "edit_text_file": EditTextFileInput,
    "list_directory": ListDirectoryInput,
    "search_files": SearchFilesInput,
    "grep_file_content": GrepFileContentInput,
    "compress_files": CompressFilesInput,
    "extract_archive": ExtractArchiveInput,
    "move_file": MoveFileInput,
    "copy_file": CopyFileInput,
    "delete_file": DeleteFileInput,
    "rename_file": RenameFileInput,
    "read_data_file": ReadDataFileInput,
    "write_data_file": WriteDataFileInput,
}


# ============================================================
# 注册函数
# ============================================================

def _register_file_tools():
    """
    注册15个文件工具 — 小欧 2026-06-17
    """

    ft = None

    def _get_ft():
        nonlocal ft
        if ft is None:
            from app.tools.file.file_tools import FileTools
            ft = FileTools()
        return ft

    tool_methods = {
        "read_text_file": lambda **kw: _get_ft().read_text_file(**kw),
        "write_text_file": lambda **kw: _get_ft().write_text_file(**kw),
        "read_media_file": lambda **kw: _get_ft().read_media_file(**kw),
        "edit_text_file": lambda **kw: _get_ft().edit_text_file(**kw),
        "list_directory": lambda **kw: _get_ft().list_directory(**kw),
        "search_files": lambda **kw: _get_ft().search_files(**kw),
        "grep_file_content": lambda **kw: _get_ft().grep_file_content(**kw),
        "compress_files": lambda **kw: _get_ft().compress_files(**kw),
        "extract_archive": lambda **kw: _get_ft().extract_archive(**kw),
        "move_file": lambda **kw: _get_ft().move_file(**kw),
        "copy_file": lambda **kw: _get_ft().copy_file(**kw),
        "delete_file": lambda **kw: _get_ft().delete_file(**kw),
        "rename_file": lambda **kw: _get_ft().rename_file(**kw),
        "read_data_file": lambda **kw: _get_ft().read_data_file(**kw),
        "write_data_file": lambda **kw: _get_ft().write_data_file(**kw),
    }
    
    CONFIRMATION_MAP = {
        "delete_file": True,
    }


    for name, method in tool_methods.items():
        desc = FILE_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = FILE_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FILE,
            implementation=method,
            version="2.0.0",
            input_model=input_model,
            examples=examples,
            dependencies=FILE_TOOL_DEPENDENCIES.get(name, []),
            needs_confirmation=bool(CONFIRMATION_MAP.get(name, False)),
        )

        logger.debug(
            f"[file_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个"
        )

__all__ = [
    "_register_file_tools",
    "FileTools",
    "get_file_tools",
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
]


