# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点

【架构规范】2026-04-26 小沈（更新2026-04-29）
- file_register.py 作为文件工具的注册点
- 实际工具实现在 file_tools.py 的 FileTools 类中
- 使用 registry.py 的 tool_registry.register() 显式注册

【2026-04-29 小沈更新】
- 按文档设计，使用 Pydantic 模型注册
- 使用 input_model 参数，自动生成 OpenAI Schema

【工具列表】（共28个）
1. read_file - 读取文件
2. write_text_file - 写入文本文件 - 小健 2026-05-02 新增
3. write_file - 写入文件（兼容别名）
4. list_directory - 列出目录
5. delete_file - 删除文件
6. move_file - 移动文件
7. search_file_content - 搜索文件内容
8. search_files_by_name - 按名称搜索文件
9. generate_report - 生成报告
10. copy_file - 复制文件
11. create_directory - 创建目录
12. get_file_info - 获取文件信息
13. compress_files - 压缩文件
14. compare_files - 比较文件
15. batch_rename - 批量重命名
16. file_checksum - 文件校验
17. file_statistics - 文件统计
18. file_monitor - 文件监控
19. read_text_file - 读取文本文件
20. read_media_file - 读取媒体文件
21. read_batch_file - 批量读取文件
22. precise_replace_in_file - 精确替换文件内容
23. edit_file - 编辑文件
24. rename_file - 重命名文件/目录
25. glob_files - Glob匹配文件
26. grep_file_content - 搜索文件内容
27. get_directory_tree - 获取目录树
28. list_allowed_directories - 列出允许访问的目录

【注册说明】
- file_tools.py 的旧 _TOOL_REGISTRY 已移除（2026-04-26）
- 使用 registry.py 的 tool_registry 统一注册
- 导入 file_register 时自动触发注册

创建时间: 2026-04-26
更新时间: 2026-04-29
"""

# ============================================================
# 文件工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
import logging
from typing import Optional
from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

# 导入 Pydantic 模型（按文档5.1设计）
# 【小健 2026-04-29】强制规范：新增工具必须从file_schema导入对应Pydantic模型，禁止手动编写input_schema字典
# 【小健 2026-04-29】后续新增tool类型（time/shell/network等）也必须按此要求，从对应schema文件导入模型注册
from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteTextFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFileContentInput,
    SearchFilesInput,
    GenerateReportInput,
    CopyFileInput,
    CreateDirectoryInput,
    GetFileInfoInput,
    CompareFilesInput,
    BatchRenameInput,
    CompressFilesInput,
    FileMonitorInput,
    FileStatisticsInput,
    FileChecksumInput,
    ReadTextFileInput,
    ReadMediaFileInput,
    ReadBatchFileInput,
    PreciseReplaceInFileInput,
    EditFileInput,
    RenameFileInput,
    GlobFilesInput,
    GrepFileContentInput,
    GetDirectoryTreeInput,
    ListAllowedDirectoriesInput,
)

# 导入工具类
from app.services.tools.file.file_tools import FileTools, get_file_tools

# 工具描述（用于注册）
FILE_TOOL_DESCRIPTIONS = {
    "read_file": "读取文件内容",
    "write_text_file": "写入文本文件",
    "write_file": "写入文件内容（兼容别名）",
    "list_directory": "列出目录内容",
    "delete_file": "删除文件",
    "move_file": "移动文件",
    "search_file_content": "搜索文件内容",
    "search_files": "搜索文件名",
    "generate_report": "生成报告",
    "copy_file": "复制文件",
    "create_directory": "创建目录",
    "get_file_info": "获取文件信息",
    "compare_files": "比较文件",
    "batch_rename": "批量重命名",
    "compress_files": "压缩文件",
    "file_monitor": "文件监控",
    "file_statistics": "文件统计",
    "file_checksum": "文件校验",
    "read_text_file": "读取文本文件",
    "read_media_file": "读取媒体文件",
    "read_batch_file": "批量读取文件",
    "precise_replace_in_file": "精确替换文件内容",
    "edit_file": "编辑文件",
    "rename_file": "重命名文件",
    "glob_files": "Glob匹配文件",
    "grep_file_content": "搜索文件内容",
    "get_directory_tree": "获取目录树",
    "list_allowed_directories": "列出允许访问的目录",
}

# 【小沈 2026-04-29】补充 examples 参数 - 17个工具的使用示例
FILE_TOOL_EXAMPLES = {
    "read_file": [
        {"file_path": "C:/Users/用户名/Documents/config.json", "offset": 1, "limit": 100},
        {"file_path": "D:/项目代码/src/main.py", "offset": 1, "limit": 2000},
        {"file_path": "C:/Users/用户名/Desktop/README.md", "offset": 1, "limit": 500, "encoding": "utf-8"}
    ],
    "write_text_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "text": "Hello World"},
        {"file_path": "D:/项目代码/config.json", "text": "{\"key\": \"value\"}", "encoding": "utf-8"},
        {"file_path": "D:/项目代码/logs/app.log", "text": "新增日志行\\n", "append": True}
    ],
    "write_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "text": "Hello World"},
        {"file_path": "D:/项目代码/config.json", "text": "{\"key\": \"value\"}", "encoding": "utf-8"}
    ],
    "list_directory": [
        {"dir_path": "C:/Users/用户名/Documents"},
        {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3}
    ],
    "delete_file": [
        {"file_path": "C:/Users/用户名/Documents/temp.txt"},
        {"file_path": "D:/项目代码/logs/app.log"}
    ],
    "move_file": [
        {"source_path": "C:/Users/用户名/Desktop/old.txt", "destination_path": "C:/Users/用户名/Documents/new.txt"},
        {"source_path": "D:/项目代码/a.txt", "destination_path": "D:/项目代码/b.txt"}
    ],
    "search_file_content": [
        {"path": "D:/项目代码", "pattern": "TODO", "file_pattern": "*.py"},
        {"path": "C:/Users/用户名/Documents", "pattern": "import", "ignore_case": True}
    ],
    "search_files": [
        {"path": "D:/项目代码", "file_pattern": "*.py"},
        {"path": "C:/Users/用户名/Documents", "file_pattern": "config*"}
    ],
    "generate_report": [
        {"output_dir": "D:/项目代码"},
        {"output_dir": "C:/Users/用户名/Documents"}
    ],
    "copy_file": [
        {"source_path": "C:/Users/用户名/Documents/source.txt", "destination_path": "C:/Users/用户名/Documents/dest.txt"},
        {"source_path": "D:/项目代码/a.py", "destination_path": "D:/项目代码/b.py"}
    ],
    "create_directory": [
        {"dir_path": "C:/Users/用户名/Documents/新文件夹"},
        {"dir_path": "D:/项目代码/src/components"}
    ],
    "get_file_info": [
        {"file_path": "C:/Users/用户名/Documents/config.json"},
        {"file_path": "D:/项目代码/main.py"}
    ],
    "compare_files": [
        {"file_path1": "C:/Users/用户名/Documents/a.txt", "file_path2": "C:/Users/用户名/Documents/b.txt"},
        {"file_path1": "D:/项目代码/v1.py", "file_path2": "D:/项目代码/v2.py", "algorithm": "content"}
    ],
    "batch_rename": [
        {"dir_path": "C:/Users/用户名/Documents", "pattern": "*.txt", "replacement": "新文件_"},
        {"dir_path": "D:/项目代码", "pattern": "old_", "replacement": "new_"}
    ],
    "compress_files": [
        {"source_path": "C:/Users/用户名/Documents/a.txt", "destination_path": "C:/Users/用户名/Documents/archive.zip"},
        {"source_path": "D:/项目代码/src", "destination_path": "D:/项目代码/code.zip", "format": "zip", "compression_level": 6}
    ],
    "file_monitor": [
        {"directory": "C:/Users/用户名/Documents", "event_types": ["created", "modified"]},
        {"directory": "D:/项目代码", "event_types": ["deleted"]}
    ],
    "file_statistics": [
        {"directory": "C:/Users/用户名/Documents"},
        {"directory": "D:/项目代码", "filters": {"file_type": ["*.py", "*.js"]}}
    ],
    "file_checksum": [
        {"file_path": "C:/Users/用户名/Documents/data.zip", "algorithm": "md5"},
        {"file_path": "D:/项目代码/main.py", "algorithm": "sha256"}
    ],
    "read_text_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py"},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/services/agent.py", "head": 10},
        {"file_path": "D:/OmniAgentAs-desk/logs/app.log", "tail": 5}
    ],
    "read_media_file": [
        {"file_path": "D:/OmniAgentAs-desk/docs/screenshot.png"},
        {"file_path": "D:/OmniAgentAs-desk/audio/notification.mp3"}
    ],
    "read_batch_file": [
        {"file_paths": ["D:/OmniAgentAs-desk/backend/app/main.py", "D:/OmniAgentAs-desk/backend/app/config.py"]},
        {"file_paths": ["D:/OmniAgentAs-desk/config.yaml", "D:/OmniAgentAs-desk/.env"]}
    ],
    "precise_replace_in_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "def old_func():", "new_string": "def new_func():"},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "print(\"debug\")", "new_string": "# print(\"debug\")", "replace_all": True}
    ],
    "edit_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "def old():", "newText": "def new():"}]},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "import os", "newText": "import os\nimport sys"}], "dryRun": True}
    ],
    "rename_file": [
        {"file_path": "D:/documents/report_old.txt", "new_name": "report_final.txt"},
        {"file_path": "D:/projects/old_folder", "new_name": "new_folder"}
    ],
    "glob_files": [
        {"pattern": "**/*.js"},
        {"pattern": "src/**/*.ts", "search_dir": "D:/OmniAgentAs-desk"}
    ],
    "grep_file_content": [
        {"pattern": "def read_file", "search_dir": "D:/OmniAgentAs-desk/backend"},
        {"pattern": "class.*Component", "search_dir": "D:/OmniAgentAs-desk/frontend", "glob": "*.tsx", "ignore_case": True}
    ],
    "get_directory_tree": [
        {"dir_path": "D:/OmniAgentAs-desk"},
        {"dir_path": "D:/OmniAgentAs-desk", "excludePatterns": ["node_modules", "__pycache__"]}
    ],
    "list_allowed_directories": [
        {}
    ]
}


def _register_file_tools():
    """
    【2026-04-29 小沈更新】按文档5.1设计注册所有文件工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    【小健 2026-04-29】强制要求：此函数在新增工具时必须在TOOL_INPUT_MODELS中添加映射，并传入input_model参数
    【小健 2026-04-29】禁止后续新增工具使用旧的非规范注册方式（直接传input_schema字典）
    """
    # 【重要】延迟创建 FileTools 实例，避免循环导入
    # 工具方法的绑定在函数被调用时才创建，此时 agent已完成初始化
    ft = None
    
    def _get_ft():
        nonlocal ft
        if ft is None:
            from app.services.tools.file.file_tools import FileTools
            ft = FileTools()
        return ft
    
    # 【重要】使用 lambda 延迟绑定方法，避免在注册时立即访问 FileTools
    tool_methods = {
        "read_file": lambda: _get_ft().read_file,
        "write_text_file": lambda: _get_ft().write_text_file,
        "write_file": lambda: _get_ft().write_file,
        "list_directory": lambda: _get_ft().list_directory,
        "delete_file": lambda: _get_ft().delete_file,
        "move_file": lambda: _get_ft().move_file,
        "search_file_content": lambda: _get_ft().search_file_content,
        "search_files": lambda: _get_ft().search_files,
        "generate_report": lambda: _get_ft().generate_report,
        "copy_file": lambda: _get_ft().copy_file,
        "create_directory": lambda: _get_ft().create_directory,
        "get_file_info": lambda: _get_ft().get_file_info,
        "compare_files": lambda: _get_ft().compare_files,
        "batch_rename": lambda: _get_ft().batch_rename,
        "compress_files": lambda: _get_ft().compress_files,
        "file_monitor": lambda: _get_ft().file_monitor,
        "file_statistics": lambda: _get_ft().file_statistics,
        "file_checksum": lambda: _get_ft().file_checksum,
        "read_text_file": lambda: _get_ft().read_text_file,
        "read_media_file": lambda: _get_ft().read_media_file,
        "read_batch_file": lambda: _get_ft().read_batch_file,
        "precise_replace_in_file": lambda: _get_ft().precise_replace_in_file,
        "edit_file": lambda: _get_ft().edit_file,
        "rename_file": lambda: _get_ft().rename_file,
        "glob_files": lambda: _get_ft().glob_files,
        "grep_file_content": lambda: _get_ft().grep_file_content,
        "get_directory_tree": lambda: _get_ft().get_directory_tree,
        "list_allowed_directories": lambda: _get_ft().list_allowed_directories,
    }
    
    # 【小健 2026-04-29】强制映射：工具名与Pydantic模型一一对应，禁止新增工具时跳过此映射
    # 【小健 2026-04-29】后续新增工具必须在此字典中添加映射，否则无法按规范生成Schema
    # 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）
    TOOL_INPUT_MODELS = {
        "read_file": ReadFileInput,
        "write_text_file": WriteTextFileInput,
        "write_file": WriteFileInput,
        "list_directory": ListDirectoryInput,
        "delete_file": DeleteFileInput,
        "move_file": MoveFileInput,
        "search_file_content": SearchFileContentInput,
        "search_files": SearchFilesInput,
        "generate_report": GenerateReportInput,
        "copy_file": CopyFileInput,
        "create_directory": CreateDirectoryInput,
        "get_file_info": GetFileInfoInput,
        "compare_files": CompareFilesInput,
        "batch_rename": BatchRenameInput,
        "compress_files": CompressFilesInput,
        "file_monitor": FileMonitorInput,
        "file_statistics": FileStatisticsInput,
        "file_checksum": FileChecksumInput,
        "read_text_file": ReadTextFileInput,
        "read_media_file": ReadMediaFileInput,
        "read_batch_file": ReadBatchFileInput,
        "precise_replace_in_file": PreciseReplaceInFileInput,
        "edit_file": EditFileInput,
        "rename_file": RenameFileInput,
        "glob_files": GlobFilesInput,
        "grep_file_content": GrepFileContentInput,
        "get_directory_tree": GetDirectoryTreeInput,
        "list_allowed_directories": ListAllowedDirectoriesInput,
    }
    
    # 【2026-04-29 小沈更新】使用 Pydantic 模型注册
    for name, method in tool_methods.items():
        desc = FILE_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)  # 获取对应的 Pydantic 模型
        examples = FILE_TOOL_EXAMPLES.get(name, [])  # 获取工具的使用示例
        
        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FILE,
            implementation=method,
            version="1.0.0",
            input_model=input_model,  # 【小健 2026-04-29】强制要求：必须传入Pydantic模型，禁止传input_schema字典
            examples=examples  # 【小沈 2026-04-29】补充 examples 参数
        )
        logger.info(f"[file_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


# 触发注册
_register_file_tools()


# ============================================================
# 导出的工具类
# ============================================================
from app.services.tools.file.file_tools import FileTools, get_file_tools


__all__ = [
    "FileTools",
    "get_file_tools",
]