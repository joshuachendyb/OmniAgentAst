# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点（精简版 v2.0）

【架构规范】2026-04-26 小沈
【精简时间】2026-05-18 小沈 — 第17章工具精简：26→11

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


创建时间: 2026-04-26
精简时间: 2026-05-18
"""

import logging

from app.services.tools.file.file_schema import (
    ArchiveToolInput,
    DataFileFormatInput,
    EditFileInput,
    FileOperationInput,
    GrepFileContentInput,
    ListDirectoryInput,
    ReadFileInput,
    ReadMediaFileInput,
    RenameFileInput,
    SearchFilesInput,
    WriteTextFileInput,
)

from app.services.tools.file.file_tools import FileTools, get_file_tools
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger


# ============================================================
# 工具描述（11个）
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "read_file": """读取文本文件 - 合并read_text_file + read_batch_file功能。

【常用名转换实例】
- 单文件读取/read_text_file → read_file(file_paths=["D:/test.txt"])
- 分页读取 → read_file(file_paths=["D:/test.txt"], head=10, limit=100)
- 批量读取/read_batch_file → read_file(file_paths=["D:/a.txt", "D:/b.txt"])

返回：data.content/data.total_lines/data.encoding（单文件）或data.results（批量）""",

    "write_text_file": """写入或追加文本文件内容，支持中文、编码自动检测、追加模式。仅支持文本文件。

使用场景：
- 创建新文件并写入内容
- 在已有文件末尾追加内容

【重要】text参数必须传入实际文件内容，禁止传入思考/计划/状态描述

使用示例：
- 创建文件：{"file_path": "D:/output/result.txt", "text": "Hello World"}
- 追加日志：{"file_path": "D:/logs/app.log", "text": "[2026-05-18] Done", "append": true}

返回数据说明：
- data.success/data.file_path/data.bytes_written/data.encoding""",

    "read_media_file": """读取图片、音频、视频文件，返回Base64编码数据和MIME类型。PDF文件请使用 read_document 工具。

使用示例：
- 读取图片：{"file_path": "D:/screenshot.png"}
- 读取音频：{"file_path": "D:/notification.mp3"}
- 读取PDF：{"file_path": "D:/report.pdf"}

返回数据说明：
- data.success/data.data(Base64)/data.mime_type/data.file_size""",

    "edit_file": """编辑文本文件 - 合并precise_replace_in_file + edit_text_file功能。

【常用名转换实例】
- 单处替换/precise_replace_in_file → edit_file(file_path="D:/main.py", old_string="old", new_string="new")
- 替换所有 → edit_file(file_path="D:/main.py", old_string="old", new_string="new", replace_all=true)
- 多处编辑/edit_text_file → edit_file(file_path="D:/main.py", edits=[{"oldText":"old","newText":"new"}])
- 预览修改 → edit_file(file_path="D:/main.py", old_string="old", new_string="new", dry_run=true)

返回：data.success/data.replaced_count""",

    "list_directory": """列出目录内容 - 合并list_directory + get_directory_tree + file_statistics功能。

【常用名转换实例】
- 列出文件/list_directory → list_directory(dir_path="D:/project")
- 递归列出 → list_directory(dir_path="D:/project", recursive=true, max_depth=3)
- 树结构/get_directory_tree → list_directory(dir_path="D:/project", format="tree")
- 统计信息/file_statistics → list_directory(dir_path="D:/project", format="list")

返回：data.entries/data.tree/data.statistics""",

    "search_files": """递归搜索匹配模式的文件/目录，支持中文文件名。search_dir为必填项。

使用示例：
- 搜索Python文件：{"pattern": "**/*.py", "search_dir": "D:/project"}
- 只搜目录：{"pattern": "src", "search_dir": "D:/project", "type": "directory"}

返回数据说明：
- data.success/data.matches/data.total/data.has_more""",

    "grep_file_content": """基于ripgrep的内容搜索，支持正则表达式和中文搜索。

使用示例：
- 简单搜索：{"pattern": "def read_file", "search_dir": "D:/backend"}
- 搜索TS文件：{"pattern": "class.*Component", "search_dir": "D:/frontend", "glob": "*.tsx"}
- 带上下文：{"pattern": "TODO", "search_dir": "D:/src", "context": {"around": 3}}

返回数据说明：
- data.success/data.matches/data.total_files/data.total_matches""",

    "rename_file": """重命名文件 - 合并rename_file + batch_rename功能。

【常用名转换实例】
- 单文件重命名/rename_file → rename_file(file_path="D:/old.txt", new_name="new.txt")
- 批量重命名/batch_rename → rename_file(mode="batch", directory="D:/files", pattern="file_(\\d+).txt", replacement="renamed_\\1.txt")

返回：data.success/data.new_path""",

    "archive_tool": """压缩/解压工具 - 合并compress_files + extract_archive + test_archive功能。

【常用名转换实例】
- 压缩/compress_files → archive_tool(action="compress", source="D:/project", destination="D:/backup.zip")
- 解压/extract_archive → archive_tool(action="extract", source="D:/backup.zip", destination="D:/output")
- 验证/test_archive → archive_tool(action="test", source="D:/backup.zip")
- 压缩目录/zip_files → archive_tool(action="compress", source="D:/project", destination="D:/project.zip")
- 解压/unzip → archive_tool(action="extract", source="D:/project.zip", destination="D:/extracted")

返回：data.success/data.compressed_size/data.extracted_files""",

    "file_operation": """文件操作统一入口 - 合并move_file + copy_file + delete_file等文件处理功能。

【常用名转换实例】
- 移动/move_file → file_operation(action="move", source="D:/a.txt", destination="E:/b.txt")
- 复制/copy_file → file_operation(action="copy", source="D:/a.txt", destination="D:/backup/a.txt")
- 删除/delete_file → file_operation(action="delete", source="D:/temp.txt")
- 备份/backup_file → file_operation(action="copy", source="D:/original.txt", destination="D:/backup.txt")
- 恢复/restore_backup → file_operation(action="copy", source="D:/backup.txt", destination="D:/original.txt")
- 永久删除 → file_operation(action="delete", source="D:/temp", force=true, recursive=true)

返回：data.success/data.action/data.source/data.destination""",

    "data_file_format": """结构化配置文件读写 - 合并read_json + write_json + read_yaml + write_yaml等功能。

【常用名转换实例】
- 读JSON/read_json → data_file_format(action="read", file_path="D:/config.json")
- 写JSON/write_json → data_file_format(action="write", file_path="D:/config.json", data={"key":"value"})
- 读YAML/read_yaml → data_file_format(action="read", file_path="D:/config.yaml")
- 写YAML/write_yaml → data_file_format(action="write", file_path="D:/config.yaml", data={"key":"value"})
- 读TOML → data_file_format(action="read", file_path="D:/config.toml")
- 读INI/read_config → data_file_format(action="read", file_path="D:/config.ini")

⚠️ CSV/Excel使用read_document工具

返回：data.success/data.data/data.format""",
}


# ============================================================
# 工具示例（11个）
# ============================================================

FILE_TOOL_EXAMPLES = {
    "read_file": [
        {"file_paths": ["D:/project/main.py"]},
        {"file_paths": ["D:/project/main.py"], "head": 10},
        {"file_paths": ["D:/a.txt", "D:/b.txt"]},
    ],
    "write_text_file": [
        {"file_path": "D:/output/test.txt", "text": "Hello World"},
        {"file_path": "D:/logs/app.log", "text": "[2026-05-18] Done\\n", "append": True},
    ],
    "read_media_file": [
        {"file_path": "D:/screenshot.png"},
    ],
    "edit_file": [
        {"file_path": "D:/main.py", "old_string": "def old():", "new_string": "def new():"},
        {"file_path": "D:/main.py", "edits": [{"oldText": "old", "newText": "new"}]},
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
        {"pattern": "def read_file", "search_dir": "D:/backend"},
        {"pattern": "TODO", "search_dir": "D:/src", "context": {"around": 3}},
    ],
    "rename_file": [
        {"file_path": "D:/old.txt", "new_name": "new.txt"},
        {"mode": "batch", "directory": "D:/files", "pattern": "file_(\\\\d+).txt", "replacement": "renamed_\\\\1.txt"},
    ],
    "archive_tool": [
        {"action": "compress", "source": "D:/project", "destination": "D:/backup.zip"},
        {"action": "extract", "source": "D:/backup.zip", "destination": "D:/extracted"},
    ],
    "file_operation": [
        {"action": "move", "source": "D:/a.txt", "destination": "E:/b.txt"},
        {"action": "copy", "source": "D:/a.txt", "destination": "D:/backup/a.txt"},
        {"action": "delete", "source": "D:/temp.txt"},
    ],
    "data_file_format": [
        {"action": "read", "file_path": "D:/config.json"},
        {"action": "write", "file_path": "D:/config.yaml", "data": {"key": "value"}},
    ],
}


# ============================================================
# 工具名到Pydantic模型的映射（11个）
# ============================================================

TOOL_INPUT_MODELS = {
    "read_file": ReadFileInput,
    "write_text_file": WriteTextFileInput,
    "read_media_file": ReadMediaFileInput,
    "edit_file": EditFileInput,
    "list_directory": ListDirectoryInput,
    "search_files": SearchFilesInput,
    "grep_file_content": GrepFileContentInput,
    "rename_file": RenameFileInput,
    "archive_tool": ArchiveToolInput,
    "file_operation": FileOperationInput,
    "data_file_format": DataFileFormatInput,
}


# ============================================================
# 注册函数
# ============================================================

def _register_file_tools():
    """注册11个文件工具 — 小沈 2026-05-18"""

    ft = None

    def _get_ft():
        nonlocal ft
        if ft is None:
            from app.services.tools.file.file_tools import FileTools
            ft = FileTools()
        return ft

    tool_methods = {
        "read_file": lambda **kw: _get_ft().read_file(**kw),
        "write_text_file": lambda **kw: _get_ft().write_text_file(**kw),
        "read_media_file": lambda **kw: _get_ft().read_media_file(**kw),
        "edit_file": lambda **kw: _get_ft().edit_file(**kw),
        "list_directory": lambda **kw: _get_ft().list_directory(**kw),
        "search_files": lambda **kw: _get_ft().search_files(**kw),
        "grep_file_content": lambda **kw: _get_ft().grep_file_content(**kw),
        "rename_file": lambda **kw: _get_ft().rename_file(**kw),
        "archive_tool": lambda **kw: _get_ft().archive_tool(**kw),
        "file_operation": lambda **kw: _get_ft().file_operation(**kw),
        "data_file_format": lambda **kw: _get_ft().data_file_format(**kw),
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
        )

        logger.info(
            f"[file_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个"
        )


_initialized = False

__all__ = [
    "FileTools",
    "get_file_tools",
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
    "get_all_file_tool_names",
    "get_tool_input_models",
]


from app.services.tools.file.file_tools import FileTools, get_file_tools


def get_all_file_tool_names() -> list:
    """获取所有已注册的文件工具名"""
    return list(TOOL_INPUT_MODELS.keys())


def get_tool_input_models() -> dict:
    """获取所有工具的Pydantic输入模型映射"""
    return TOOL_INPUT_MODELS
