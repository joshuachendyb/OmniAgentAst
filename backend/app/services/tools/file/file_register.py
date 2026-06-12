# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点(精简版 v2.0)

【架构规范】2026-04-26 小沈
【精简时间】2026-05-18 小沈 — 第17章工具精简:26→11

10个工具清单(F1-F10):
F1  read_text_file     — 读取文本文件
F2  write_text_file    — 写文本文件
F3  read_media_file    — 读媒体文件
F4  edit_text_file     — 编辑文本文件
F5  list_directory     — 列出目录内容
F6  search_files       — 搜索文件名
F7  grep_file_content  — 搜索文件内容
F8  archive_tool       — 压缩/解压
F9  file_operation     — 文件操作(move/copy/delete/rename)
F10 data_file_format   — 结构化配置文件读写


创建时间: 2026-04-26
精简时间: 2026-05-18
"""

import logging

from app.services.tools.file.file_schema import (
    ArchiveToolInput,
    DataFileFormatInput,
    EditTextFileInput,
    FileOperationInput,
    GrepFileContentInput,
    ListDirectoryInput,
    ReadTextFileInput,
    ReadMediaFileInput,
    SearchFilesInput,
    WriteTextFileInput,
)

from app.services.tools.file.file_tools import FileTools, get_file_tools
from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory, ToolSafetyLevel
from app.utils.logger import logger


# ============================================================
# 工具描述(10个)
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "read_text_file": """读取文本文件。支持分页读取(head/tail/offset/limit)。encoding默认utf-8,读取失败自动尝试gbk。""",

    "write_text_file": """写文本文件：创建新文件或追加内容。自动检测编码，支持中文路径。content 参数传入实际文件内容（禁止传入思考/状态描述），append=True 追加到末尾。""",

    "read_media_file": """读取图片、音频、视频文件,返回Base64编码数据和MIME类型。PDF文件请使用 read_document 工具。

使用示例:
- 读取图片:{"file_path": "D:/screenshot.png"}
- 读取音频:{"file_path": "D:/notification.mp3"}
- 读取PDF:{"file_path": "D:/report.pdf"}

返回数据说明:
- data.success/data.data(Base64)/data.mime_type/data.file_size""",

    "edit_text_file": """替换文本文件中的内容。old_string定位被替换文本,new_string替换为的内容。replace_all替换所有匹配项,dry_run仅预览。""",

    "list_directory": """列出目录内容(统一入口)- 合并list_directory + get_directory_tree + file_statistics功能。

使用方式:
- format="list":扁平列表(含文件大小/修改时间)
- format="tree":JSON树结构
- 始终返回statistics统计信息

使用示例:【常用名转换说明】
- 列出文件/list_directory → list_directory(dir_path="D:/project")
- 递归列出 → list_directory(dir_path="D:/project", recursive=true, max_depth=3)
- 树结构/get_directory_tree → list_directory(dir_path="D:/project", format="tree")
- 统计信息/file_statistics → list_directory(dir_path="D:/project", format="list")

返回数据说明:
- data.success/data.entries(list)/data.tree(tree)/data.statistics(统计)""",

    "search_files": """递归搜索匹配模式的文件/目录,支持中文文件名。search_dir为必填项。

使用示例:
- 搜索Python文件:{"pattern": "**/*.py", "search_dir": "D:/project"}
- 只搜目录:{"pattern": "src", "search_dir": "D:/project", "type": "directory"}

返回数据说明:
- data.success/data.matches/data.total/data.has_more""",

    "grep_file_content": """基于ripgrep的内容搜索,支持正则表达式和中文搜索。

使用示例:
- 简单搜索:{"pattern": "def read_text_file", "search_dir": "D:/backend"}
- 搜索TS文件:{"pattern": "class.*Component", "search_dir": "D:/frontend", "glob": "*.tsx"}
- 带上下文:{"pattern": "TODO", "search_dir": "D:/src", "context": {"around": 3}}

返回数据说明:
- data.success/data.matches/data.total_files/data.total_matches""",

    "archive_tool": """压缩/解压工具 - 合并compress_files + extract_archive + test_archive功能。支持zip/tar/tar.gz/tar.bz2格式。

使用方式:
- action="compress":压缩文件/目录
- action="extract":解压到指定目录
- action="test":验证压缩包完整性

使用示例:【常用名转换说明】
- 压缩/compress_files → archive_tool(action="compress", source="D:/project", destination="D:/backup.zip")
- 解压/extract_archive → archive_tool(action="extract", source="D:/backup.zip", destination="D:/output")
- 验证/test_archive → archive_tool(action="test", source="D:/backup.zip")
- 压缩目录/zip_files → archive_tool(action="compress", source="D:/project", destination="D:/project.zip")
- 解压/unzip → archive_tool(action="extract", source="D:/project.zip", destination="D:/extracted")

返回数据说明:
- data.success/data.compressed_size(压缩)/data.extracted_files(解压)""",

    "file_operation": """文件操作统一入口 - move/copy/delete/rename。

使用方式:
- action="move":移动文件
- action="copy":复制文件
- action="delete":删除文件(可放回收站)
- action="rename":重命名文件

使用示例:
- 移动 → file_operation(action="move", source="D:/a.txt", destination="E:/b.txt")
- 复制 → file_operation(action="copy", source="D:/a.txt", destination="D:/backup/a.txt")
- 删除 → file_operation(action="delete", source="D:/temp.txt")
- 重命名 → file_operation(action="rename", source="D:/old.txt", destination="D:/new.txt")

返回数据说明:
- data.success/data.action/data.source/data.destination""",

    "data_file_format": """结构化配置文件读写 - 合并read_json + write_json + read_yaml + write_yaml等功能。

支持格式:JSON/YAML/TOML/INI/XML/Properties
⚠️ CSV/Excel使用read_document工具
⚠️ write模式仅支持JSON/YAML/TOML,INI/XML/Properties暂不支持写入

使用示例:【常用名转换说明】
- 读JSON/read_json → data_file_format(action="read", file_path="D:/config.json")
- 写JSON/write_json → data_file_format(action="write", file_path="D:/config.json", data={"key":"value"})
- 读YAML/read_yaml → data_file_format(action="read", file_path="D:/config.yaml")
- 写YAML/write_yaml → data_file_format(action="write", file_path="D:/config.yaml", data={"key":"value"})
- 读TOML → data_file_format(action="read", file_path="D:/config.toml")
- 读INI/read_config → data_file_format(action="read", file_path="D:/config.ini")

返回数据说明:
- data.success/data.data(读取)/data.format/data.bytes_written(写入)""",
}


# ============================================================
# 工具示例(10个)
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
# 工具名到Pydantic模型的映射(10个)
# ============================================================

TOOL_INPUT_MODELS = {
    "read_text_file": ReadTextFileInput,
    "write_text_file": WriteTextFileInput,
    "read_media_file": ReadMediaFileInput,
    "edit_text_file": EditTextFileInput,
    "list_directory": ListDirectoryInput,
    "search_files": SearchFilesInput,
    "grep_file_content": GrepFileContentInput,
    "archive_tool": ArchiveToolInput,
    "file_operation": FileOperationInput,
    "data_file_format": DataFileFormatInput,
}


# ============================================================
# 注册函数
# ============================================================

def _register_file_tools():
    """
    注册10个文件工具 — 小沈 2026-06-09
    【v3.4新增 2026-06-09 小沈】添加安全级别标注
    """

    ft = None

    def _get_ft():
        nonlocal ft
        if ft is None:
            from app.services.tools.file.file_tools import FileTools
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
        "archive_tool": lambda **kw: _get_ft().archive_tool(**kw),
        "file_operation": lambda **kw: _get_ft().file_operation(**kw),
        "data_file_format": lambda **kw: _get_ft().data_file_format(**kw),
    }
    
    # 【v3.4新增】安全级别配置
    safety_levels = {
        "read_text_file": ToolSafetyLevel.READ_ONLY,
        "write_text_file": ToolSafetyLevel.SAFE,
        "read_media_file": ToolSafetyLevel.READ_ONLY,
        "edit_text_file": ToolSafetyLevel.SAFE,
        "list_directory": ToolSafetyLevel.READ_ONLY,
        "search_files": ToolSafetyLevel.READ_ONLY,
        "grep_file_content": ToolSafetyLevel.READ_ONLY,
        "archive_tool": ToolSafetyLevel.SAFE,
        "file_operation": ToolSafetyLevel.SAFE,  # move/copy=SAFE, delete=DESTRUCTIVE(action级)
        "data_file_format": ToolSafetyLevel.SAFE,
    }
    
    # 【v3.4新增】action级安全覆盖（file_operation的delete分级）
    action_safety_maps = {
        "file_operation": {
            "move": ToolSafetyLevel.SAFE,
            "copy": ToolSafetyLevel.SAFE,
            "rename": ToolSafetyLevel.SAFE,
            "delete": ToolSafetyLevel.DESTRUCTIVE,
        },
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
            safety_level=safety_levels.get(name, ToolSafetyLevel.SAFE),  # 【v3.4新增】
            action_safety_map=action_safety_maps.get(name),  # 【v3.4新增】
        )

        logger.debug(
            f"[file_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个, safety: {safety_levels.get(name, ToolSafetyLevel.SAFE).value}"
        )

__all__ = [
    "FileTools",
    "get_file_tools",
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
]


from app.services.tools.file.file_tools import FileTools, get_file_tools

