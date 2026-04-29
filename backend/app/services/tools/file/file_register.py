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

【工具列表】（共17个）
1. read_file - 读取文件
2. write_file - 写入文件
3. list_directory - 列出目录
4. delete_file - 删除文件
5. move_file - 移动文件
6. search_file_content - 搜索文件内容
7. search_files_by_name - 按名称搜索文件
8. generate_report - 生成报告
9. copy_file - 复制文件
10. create_directory - 创建目录
11. get_file_info - 获取文件信息
12. compress_files - 压缩文件
13. compare_files - 比较文件
14. batch_rename - 批量重命名
15. file_checksum - 文件校验
16. file_statistics - 文件统计
17. file_monitor - 文件监控

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
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFileContentInput,
    SearchFilesByNameInput,
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
)

# 导入工具类
from app.services.tools.file.file_tools import FileTools, get_file_tools

# 工具描述（用于注册）
FILE_TOOL_DESCRIPTIONS = {
    "read_file": "读取文件内容",
    "write_file": "写入文件内容",
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
}

# 【小沈 2026-04-29】补充 examples 参数 - 17个工具的使用示例
FILE_TOOL_EXAMPLES = {
    "read_file": [
        {"file_path": "C:/Users/用户名/Documents/config.json", "offset": 1, "limit": 100},
        {"file_path": "D:/项目代码/src/main.py", "offset": 1, "limit": 2000},
        {"file_path": "C:/Users/用户名/Desktop/README.md", "offset": 1, "limit": 500, "encoding": "utf-8"}
    ],
    "write_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "content": "Hello World"},
        {"file_path": "D:/项目代码/config.json", "content": "{\"key\": \"value\"}", "encoding": "utf-8"}
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
        {"source_path": "C:/Users/用户名/Desktop/old.txt", "dest_path": "C:/Users/用户名/Documents/new.txt"},
        {"source_path": "D:/项目代码/a.txt", "dest_path": "D:/项目代码/b.txt"}
    ],
    "search_file_content": [
        {"dir_path": "D:/项目代码", "pattern": "TODO", "file_types": ["*.py", "*.js"]},
        {"dir_path": "C:/Users/用户名/Documents", "pattern": "import", "case_sensitive": False}
    ],
    "search_files": [
        {"dir_path": "D:/项目代码", "pattern": "*.py"},
        {"dir_path": "C:/Users/用户名/Documents", "pattern": "config*"}
    ],
    "generate_report": [
        {"dir_path": "D:/项目代码", "output_path": "D:/项目代码/report.txt", "format": "text"},
        {"dir_path": "C:/Users/用户名/Documents", "output_path": "C:/Users/用户名/Documents/report.json", "format": "json"}
    ],
    "copy_file": [
        {"source_path": "C:/Users/用户名/Documents/source.txt", "dest_path": "C:/Users/用户名/Documents/dest.txt"},
        {"source_path": "D:/项目代码/a.py", "dest_path": "D:/项目代码/b.py"}
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
        {"file1_path": "C:/Users/用户名/Documents/a.txt", "file2_path": "C:/Users/用户名/Documents/b.txt"},
        {"file1_path": "D:/项目代码/v1.py", "file2_path": "D:/项目代码/v2.py"}
    ],
    "batch_rename": [
        {"dir_path": "C:/Users/用户名/Documents", "pattern": "*.txt", "replacement": "新文件_"},
        {"dir_path": "D:/项目代码", "pattern": "old_", "replacement": "new_"}
    ],
    "compress_files": [
        {"files": ["C:/Users/用户名/Documents/a.txt", "C:/Users/用户名/Documents/b.txt"], "output_path": "C:/Users/用户名/Documents/archive.zip"},
        {"files": ["D:/项目代码/file1.py", "D:/项目代码/file2.py"], "output_path": "D:/项目代码/code.zip"}
    ],
    "file_monitor": [
        {"dir_path": "C:/Users/用户名/Documents", "events": ["create", "modify"]},
        {"dir_path": "D:/项目代码", "events": ["delete"]}
    ],
    "file_statistics": [
        {"dir_path": "C:/Users/用户名/Documents"},
        {"dir_path": "D:/项目代码", "include_patterns": ["*.py", "*.js"]}
    ],
    "file_checksum": [
        {"file_path": "C:/Users/用户名/Documents/data.zip", "algorithm": "md5"},
        {"file_path": "D:/项目代码/main.py", "algorithm": "sha256"}
    ]
}


def _register_file_tools():
    """
    【2026-04-29 小沈更新】按文档5.1设计注册所有文件工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    【小健 2026-04-29】强制要求：此函数在新增工具时必须在TOOL_INPUT_MODELS中添加映射，并传入input_model参数
    【小健 2026-04-29】禁止后续新增工具使用旧的非规范注册方式（直接传input_schema字典）
    """
    # 只创建一个 FileTools 实例
    ft = FileTools()
    
    # 统一的工具映射 - 注册名与实际方法名一致
    tool_methods = {
        "read_file": ft.read_file,
        "write_file": ft.write_file,
        "list_directory": ft.list_directory,
        "delete_file": ft.delete_file,
        "move_file": ft.move_file,
        "search_file_content": ft.search_file_content,
        "search_files": ft.search_files,      # 统一：注册名 = 方法名
        "generate_report": ft.generate_report,
        "copy_file": ft.copy_file,
        "create_directory": ft.create_directory,
        "get_file_info": ft.get_file_info,
        "compare_files": ft.compare_files,
        "batch_rename": ft.batch_rename,
        "compress_files": ft.compress_files,
        "file_monitor": ft.file_monitor,
        "file_statistics": ft.file_statistics,
        "file_checksum": ft.file_checksum,
    }
    
    # 【小健 2026-04-29】强制映射：工具名与Pydantic模型一一对应，禁止新增工具时跳过此映射
    # 【小健 2026-04-29】后续新增工具必须在此字典中添加映射，否则无法按规范生成Schema
    # 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）
    TOOL_INPUT_MODELS = {
        "read_file": ReadFileInput,
        "write_file": WriteFileInput,
        "list_directory": ListDirectoryInput,
        "delete_file": DeleteFileInput,
        "move_file": MoveFileInput,
        "search_file_content": SearchFileContentInput,
        "search_files": SearchFilesByNameInput,
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