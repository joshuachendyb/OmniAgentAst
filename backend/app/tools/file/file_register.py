# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点 v3.0

【架构规范】2026-04-26 小沈
【精简时间】2026-05-18 小沈 — 第17章工具精简:26→11
【拆分时间】2026-06-16 小沈 — 组合工具拆分:archive_tool→2, file_operation→4
【拆分时间】2026-06-17 小欧 — data_file_format→2: read_config_file, write_config_file
【删除时间】2026-06-24 小欧 — 删除read_config_file/write_config_file，text工具已覆盖

14个工具清单(F1-F13):
F1  readtext     — 读取文本文件
F2  writetext    — 写文本文件
F3  readmedia    — 读媒体文件
F4  edittext     — 编辑文本文件
F5a listdir            — 列出目录内容
F5b tree               — 列出目录树
F6  find       — 搜索文件名
F7  grep  — 搜索文件内容
F8  compress     — 压缩文件
F9  extract    — 解压文件
F10 move          — 移动文件
F11 copy          — 复制文件
F12 delete        — 删除文件
F13 rename        — 重命名文件


创建时间: 2026-04-26
精简时间: 2026-05-18
拆分时间: 2026-06-16
更新时间: 2026-06-17
"""

from app.tools.file.file_schema import (
    CompressInput,
    CopyInput,
    DeleteInput,
    EdittextInput,
    ExtractInput,
    GrepInput,
    ListdirInput,
    TreeInput,
    MoveInput,
    ReadtextInput,
    ReadmediaInput,
    RenameInput,
    FindInput,
    WritetextInput,
)

from app.tools.file.read_text_file import readtext
from app.tools.file.write_text_file import writetext
from app.tools.file.read_media_file import readmedia
from app.tools.file.edit_text_file import edittext
from app.tools.file.list_directory import listdir
from app.tools.file.tree import tree
from app.tools.file.search_files import find
from app.tools.file.grep_file_content import grep
from app.tools.file.compress_files import compress
from app.tools.file.extract_archive import extract
from app.tools.file.move_file import move
from app.tools.file.copy_file import copy
from app.tools.file.delete_file import delete
from app.tools.file.rename_file import rename
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

# 文件工具依赖配置 — 小健 2026-06-18
# compress的pyzipper是可选依赖(仅加密ZIP时需要) — 小健 2026-06-19
FILE_TOOL_DEPENDENCIES = {
    tool_name: [] for tool_name in [
        "readtext", "writetext", "readmedia", "edittext",
        "listdir", "tree", "find", "grep",
        "extract", "move", "copy", "delete", "rename",
    ]
}
FILE_TOOL_DEPENDENCIES["compress"] = ["pyzipper"]


# ============================================================
# 工具描述(14个)
# ============================================================

FILE_TOOL_DESCRIPTIONS = {
    "readtext": """读取文本文件内容。适用场景:需要查看或分析源代码、日志、配置文件等纯文本时使用。""",

    "writetext": """创建或修改文本文件。适用场景:需要写入代码、配置、日志等内容到文件时使用。""",

    "readmedia": """读取图片、音频、视频等非文本文件。适用场景:需要获取媒体文件内容进行图像识别、音频分析等时使用。""",

    "edittext": """替换/插入文本文件中的指定内容。mode=once(只替换第一个), all(替换全部), before(在锚点前插入), after(在锚点后插入)。适用场景:需要精确修改函数名/变量/配置值,或在代码前后插入新逻辑。""",

    "listdir": """列出目录内容,返回扁平列表(当前层所有文件+目录)。适用场景:需要查看目录结构、文件大小、文件数量统计时使用。""",

    "tree": """列出目录树,仅显示目录层级(不含文件)。适用场景:需要查看项目目录结构、快速了解文件夹组织时使用。""",

    "find": """按文件名匹配模式递归搜索文件或目录。适用场景:需要查找特定文件、统计项目中某类文件数量时使用。""",

    "grep": """在文件中搜索文本内容,支持正则表达式。适用场景:需要查找代码或文档中的函数定义、关键字、TODO等文本时使用。""",

    "compress": """将单个文件或目录压缩为归档包,可选加密。多文件打包请用通配符(如*.txt)或分多次调用(设overwrite=true)。适用场景:需要备份文件、打包项目、创建加密压缩包时使用。""",

    "extract": """解压归档包到指定目录。适用场景:需要解压下载的压缩包、恢复备份时使用。""",

    "move": """移动文件或目录到新位置。适用场景:需要整理文件位置、迁移文件时使用。""",

    "copy": """复制文件或目录到目标位置。适用场景:需要备份文件、复制模板时使用。""",

    "delete": """删除文件或目录(默认可恢复)。适用场景:需要清理临时文件、删除过期数据时使用。""",

    "rename": """重命名文件或目录。适用场景:需要修改文件名、规范化命名时使用。""",
}


# ============================================================
# 工具示例(14个)
# ============================================================

FILE_TOOL_EXAMPLES = {
    "readtext": [
        {"path": "D:/project/main.py"},                               # 全文
        {"path": "D:/logs/app.log", "tail": 50},                     # 末50行(看日志尾部)
        {"path": "D:/project/main.py", "offset": 1, "limit": 200},  # 分页
    ],
    "writetext": [
        {"path": "D:/output/test.txt", "content": "Hello World"},
        {"path": "D:/report.md", "content": "# 标题\n\n第一段内容\n\n第二段内容"},
        {"path": "D:/config.json", "content": "{\"name\": \"test\", \"value\": 123}"},
        {"path": "D:/logs/app.log", "content": "[2026-05-18] Done\n", "append": True},
    ],
    "readmedia": [
        {"path": "D:/screenshot.png"},
    ],
    "edittext": [
        {"path": "D:/main.py", "old_string": "def old():", "new_string": "def new():"},
        {"path": "D:/main.py", "old_string": "import os", "new_string": "import sys\nimport json", "mode": "all"},
        {"path": "D:/main.py", "mode": "before", "old_string": "def main():", "new_string": "# new function above main\ndef helper():\n    pass\n\n"},
        {"path": "D:/main.py", "mode": "after", "old_string": "def main():", "new_string": "\n    # added after main start\n    pass"},
    ],
    "listdir": [
        {"path": "D:/project"},
        {"path": "D:/project", "sort_by": "size"},
        {"path": "D:/project", "offset": 500},
    ],
    "tree": [
        {"path": "D:/project"},
        {"path": "D:/project", "include_hidden": True},
        {"path": "D:/project/node_modules", "max_depth": 2},
    ],
    "find": [
        {"pattern": "**/*.py", "path": "D:/project"},
        {"pattern": "**/*.py", "path": "D:/project", "offset": 500},
    ],
    "grep": [
        {"pattern": "def readtext", "path": "D:/backend"},
        {"pattern": "TODO", "path": "D:/src"},
        {"pattern": "error", "path": "D:/logs", "output_mode": "only_files"},
        {"pattern": "class.*Component", "path": "D:/src", "glob": "*.py"},
        {"pattern": "arr[0]", "path": "D:/src", "literal": True},
        {"pattern": "def run", "path": "D:/backend", "context": 2}
    ],
    "compress": [
        {"source": "D:/project", "destination": "D:/backup.zip"},
        {"source": "D:/secret.txt", "destination": "D:/secret_encrypted.zip", "password": "my_password"},
        {"source": "D:/dir/*.txt", "destination": "D:/all_txt.zip"},
        {"source": "D:/b.txt", "destination": "D:/archive.zip", "overwrite": True},
    ],
    "extract": [
        {"source": "D:/backup.zip", "destination": "D:/extracted"},
    ],
    "move": [
        {"source": "D:/a.txt", "destination": "E:/b.txt"},
    ],
    "copy": [
        {"source": "D:/a.txt", "destination": "D:/backup/a.txt"},
    ],
    "delete": [
        {"source": "D:/temp.txt"},
    ],
    "rename": [
        {"source": "D:/old.txt", "destination": "new.txt"},
    ],
}


# ============================================================
# 工具名到Pydantic模型的映射(14个)
# ============================================================

TOOL_INPUT_MODELS = {
    "readtext": ReadtextInput,
    "writetext": WritetextInput,
    "readmedia": ReadmediaInput,
    "edittext": EdittextInput,
    "listdir": ListdirInput,
    "tree": TreeInput,
    "find": FindInput,
    "grep": GrepInput,
    "compress": CompressInput,
    "extract": ExtractInput,
    "move": MoveInput,
    "copy": CopyInput,
    "delete": DeleteInput,
    "rename": RenameInput,
}


# ============================================================
# 注册函数
# ============================================================

def _register_file_tools():
    """
    注册14个文件工具 — 小健 2026-06-18 函数式设计重构 — 小沈 2026-07-03 拆分list_directory
    """

    tool_methods = {
        "readtext": readtext,
        "writetext": writetext,
        "readmedia": readmedia,
        "edittext": edittext,
        "listdir": listdir,
        "tree": tree,
        "find": find,
        "grep": grep,
        "compress": compress,
        "extract": extract,
        "move": move,
        "copy": copy,
        "delete": delete,
        "rename": rename,
    }
    
    CONFIRMATION_MAP = {
        "delete": True,
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


