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
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


# ============================================================
# 工具描述(10个)
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "read_text_file": """读取文本文件。支持分页读取(head/tail/offset/limit)。encoding默认utf-8,读取失败自动尝试gbk。适用场景:需要读取源代码、日志文件、配置文件等纯文本内容时使用。""",

    "write_text_file": """写文本文件：创建新文件或追加内容。自动检测编码，支持中文路径。content 参数传入实际文件内容（禁止传入思考/状态描述），append=True 追加到末尾。适用场景:需要创建或修改代码文件、配置文件、日志文件等文本内容时使用。""",

    "read_media_file": """读取图片、音频、视频文件,返回Base64编码数据和MIME类型。自动识别媒体类型,支持常见图片(jpg/png/gif/bmp)、音频(mp3/wav/ogg)和视频(mp4/avi/mkv)格式。不支持PDF文件(PDF请使用read_document工具)。适用场景:需要获取非文本文件内容并将其传递给LLM进行图像识别、音频分析等任务。""",

    "edit_text_file": """替换文本文件中的内容。old_string定位被替换文本,new_string替换为的内容。replace_all替换所有匹配项,dry_run仅预览。适用场景:需要精确修改代码中的某个函数名、变量引用、配置值时使用。""",

    "list_directory": """列出目录内容,支持扁平列表(format="list")和JSON树结构(format="tree")两种输出格式。list格式返回包含文件大小/修改时间的条目列表,tree格式返回嵌套的JSON目录树。始终返回统计信息(文件数/目录数/总大小)。支持递归列出子目录、按名称/大小/修改时间排序、分页读取,以及过滤隐藏文件。适用场景:需要了解项目目录结构、查看文件大小和修改时间、获取文件统计信息时使用。""",

    "search_files": """递归搜索匹配glob模式的文件/目录。search_dir为必填的搜索起始目录。pattern支持glob通配符(*?**)和中文文件名。可指定搜索类型(文件/目录)、递归深度、大小写敏感。分页返回结果,每页包含匹配列表和总数。适用场景:需要按文件名查找特定文件、统计项目中某类文件数量时使用。""",

    "grep_file_content": """基于ripgrep在文件中搜索文本内容,支持正则表达式和中文搜索。可指定搜索路径、文件过滤(glob通配符,如"*.py")、匹配前后上下文行数、大小写敏感、多行匹配模式、返回条数限制。分页返回结果,包含匹配行内容、匹配文件和总匹配数。适用场景:需要在代码或文档中查找特定函数定义、关键字、TODO标记,并了解其上下文时使用。""",

    "archive_tool": """支持文件的压缩/解压操作功能,支持zip/tar/tar.gz/tar.bz2格式。
action参数决定操作类型:
- compress: 压缩文件/目录到归档包,source→destination(可选format/compression_level/password/exclude_patterns)
- extract: 解压归档包到目录,source→destination(可选password/overwrite)

使用示例:
- 压缩 → archive_tool(action="compress", source="D:/project", destination="D:/backup.zip")
- 解压 → archive_tool(action="extract", source="D:/backup.zip", destination="D:/output")""",

    "file_operation": """支持文件的move/copy/delete/rename操作功能。
action参数决定操作类型:
- move: 移动文件,source→destination(可选overwrite)
- copy: 复制,source→destination(目录需recursive=True;可选overwrite/preserve_metadata)
- delete: 删除,source(非空目录需recursive=True;force=True永久删除,默认回收站)
- rename: 重命名文件/目录,source旧名→destination新名

使用示例:
- 移动 → file_operation(action="move", source="D:/a.txt", destination="E:/b.txt")
- 复制 → file_operation(action="copy", source="D:/a.txt", destination="D:/backup/a.txt")
- 删除 → file_operation(action="delete", source="D:/temp.txt")
- 重命名 → file_operation(action="rename", source="D:/old.txt", destination="D:/new.txt")""",

    "data_file_format": """支持结构化配置文件的读/写操作功能,支持JSON/YAML/TOML/INI/XML/Properties格式。
action参数决定操作类型:
- read: 读取配置文件,file_path(自动检测格式;可选format/encoding)
- write: 写入配置文件,file_path+data(支持JSON/YAML/TOML;可选format/encoding/indent)

使用示例:
- 读取 → data_file_format(action="read", file_path="D:/config.json")
- 写入 → data_file_format(action="write", file_path="D:/config.yaml", data={"key":"value"})""",
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
    
    # 【2026-06-16 小沈】二元安全配置（替代5级枚举）
    CONFIRMATION_MAP = {
        "file_operation": {"delete": True},  # file_operation的delete需要确认
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
            needs_confirmation=False,  # file工具默认不需要确认
            action_confirmation=CONFIRMATION_MAP.get(name),
        )

        logger.debug(
            f"[file_register] 已注册工具: {name}, Pydantic模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个"
        )

__all__ = [
    "FileTools",
    "get_file_tools",
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
]


from app.services.tools.file.file_tools import FileTools, get_file_tools

