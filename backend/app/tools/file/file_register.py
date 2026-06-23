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

from app.tools.file.read_text_file import read_text_file
from app.tools.file.write_text_file import write_text_file
from app.tools.file.read_media_file import read_media_file
from app.tools.file.edit_text_file import edit_text_file
from app.tools.file.list_directory import list_directory
from app.tools.file.search_files import search_files
from app.tools.file.grep_file_content import grep_file_content
from app.tools.file.compress_files import compress_files
from app.tools.file.extract_archive import extract_archive
from app.tools.file.move_file import move_file
from app.tools.file.copy_file import copy_file
from app.tools.file.delete_file import delete_file
from app.tools.file.rename_file import rename_file
from app.tools.file.read_data_file import read_data_file
from app.tools.file.write_data_file import write_data_file
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 文件工具依赖配置 — 小健 2026-06-18
# compress_files的pyzipper是可选依赖(仅加密ZIP时需要) — 小健 2026-06-19
FILE_TOOL_DEPENDENCIES = {
    tool_name: [] for tool_name in [
        "read_text_file", "write_text_file", "read_media_file", "edit_text_file",
        "list_directory", "search_files", "grep_file_content",
        "extract_archive", "move_file", "copy_file", "delete_file", "rename_file",
        "read_data_file", "write_data_file"
    ]
}
FILE_TOOL_DEPENDENCIES["compress_files"] = ["pyzipper"]


# ============================================================
# 工具描述(15个)
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "read_text_file": """读取文本文件内容。适用场景:需要查看或分析源代码、日志、配置文件等纯文本时使用。""",

    "write_text_file": """创建或修改文本文件。适用场景:需要写入代码、配置、日志等内容到文件时使用。""",

    "read_media_file": """读取图片、音频、视频等非文本文件。不支持PDF文件(请用read_pdf)。适用场景:需要获取媒体文件内容进行图像识别、音频分析等时使用。""",

    "edit_text_file": """替换文本文件中的指定内容。适用场景:需要精确修改代码中的函数名、变量、配置值等时使用。""",

    "list_directory": """列出目录内容,支持扁平列表和目录树两种格式。适用场景:需要查看目录结构、文件大小、文件数量统计时使用。""",

    "search_files": """按文件名匹配模式递归搜索文件或目录。适用场景:需要查找特定文件、统计项目中某类文件数量时使用。""",

    "grep_file_content": """在文件中搜索文本内容,支持正则表达式。适用场景:需要查找代码或文档中的函数定义、关键字、TODO等文本时使用。""",

    "compress_files": """将单个文件或目录压缩为归档包,可选加密。多文件打包请用通配符(如*.txt)或分多次调用(设overwrite=true)。适用场景:需要备份文件、打包项目、创建加密压缩包时使用。""",

    "extract_archive": """解压归档包到指定目录。适用场景:需要解压下载的压缩包、恢复备份时使用。""",

    "move_file": """移动文件或目录到新位置。适用场景:需要整理文件位置、迁移文件时使用。""",

    "copy_file": """复制文件或目录到目标位置。适用场景:需要备份文件、复制模板时使用。""",

    "delete_file": """删除文件或目录(默认可恢复)。适用场景:需要清理临时文件、删除过期数据时使用。""",

    "rename_file": """重命名文件或目录。适用场景:需要修改文件名、规范化命名时使用。""",

    "read_data_file": """读取JSON/YAML/TOML等结构化配置文件。CSV文件需指定format参数。适用场景:需要查看或分析配置文件内容时使用。""",

    "write_data_file": """写入结构化配置文件(JSON/YAML/TOML)。适用场景:需要创建或修改配置文件时使用。""",
}


# ============================================================
# 工具示例(15个)
# ============================================================

FILE_TOOL_EXAMPLES = {
    "read_text_file": [
        {"file_path": "D:/project/main.py"},                               # 全文
        {"file_path": "D:/logs/app.log", "offset": -50},                  # 末50行(看日志尾部)
        {"file_path": "D:/project/main.py", "offset": 1, "limit": 200},  # 分页
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
        {"dir_path": "D:/project", "tree": True},
    ],
    "search_files": [
        {"pattern": "**/*.py", "search_dir": "D:/project"},
    ],
    "grep_file_content": [
        {"pattern": "def read_text_file", "search_dir": "D:/backend"},
        {"pattern": "TODO", "search_dir": "D:/src", "head_limit": 50},
        {"pattern": "error", "search_dir": "D:/logs", "output_mode": "files_with_matches"},
        {"pattern": "class.*Component", "search_dir": "D:/src", "context_lines": 3},
    ],
    "compress_files": [
        {"source": "D:/project", "destination": "D:/backup.zip"},
        {"source": "D:/secret.txt", "destination": "D:/secret_encrypted.zip", "password": "my_password"},
        {"source": "D:/dir/*.txt", "destination": "D:/all_txt.zip"},
        {"source": "D:/b.txt", "destination": "D:/archive.zip", "overwrite": True},
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
    注册15个文件工具 — 小健 2026-06-18 函数式设计重构
    """

    tool_methods = {
        "read_text_file": read_text_file,
        "write_text_file": write_text_file,
        "read_media_file": read_media_file,
        "edit_text_file": edit_text_file,
        "list_directory": list_directory,
        "search_files": search_files,
        "grep_file_content": grep_file_content,
        "compress_files": compress_files,
        "extract_archive": extract_archive,
        "move_file": move_file,
        "copy_file": copy_file,
        "delete_file": delete_file,
        "rename_file": rename_file,
        "read_data_file": read_data_file,
    }
    if write_data_file is not None:
        tool_methods["write_data_file"] = write_data_file
    
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
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
]


