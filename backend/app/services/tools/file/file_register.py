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

【工具列表】（共24个）
1. write_text_file - 写入文本文件 - 小健 2026-05-02 新增
2. list_directory - 列出目录
3. delete_file - 删除文件
5. move_file - 移动文件
6. search_files_by_name - 按名称搜索文件
7. generate_report - 生成报告
8. copy_file - 复制文件
9. create_directory - 创建目录
10. get_file_info - 获取文件信息
11. compress_files - 压缩文件
12. compare_files - 比较文件
13. batch_rename - 批量重命名
14. file_checksum - 文件校验
15. file_statistics - 文件统计
16. file_monitor - 文件监控
17. read_text_file - 读取文本文件
18. read_media_file - 读取媒体文件
19. read_batch_file - 批量读取文件
20. precise_replace_in_file - 精确替换文件内容
21. edit_text_file - 编辑文本文件
22. rename_file - 重命名文件/目录
23. grep_file_content - 搜索文件内容
24. get_directory_tree - 获取目录树
25. list_allowed_directories - 列出允许访问的目录

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
    WriteTextFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
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
    EditTextFileInput,
    RenameFileInput,
    GrepFileContentInput,
    GetDirectoryTreeInput,
    ListAllowedDirectoriesInput,
)

# 导入工具类
from app.services.tools.file.file_tools import FileTools, get_file_tools

# 工具描述（用于注册）
FILE_TOOL_DESCRIPTIONS = {
    "write_text_file": "写入或追加文本文件内容，支持中文内容写入、编码自动检测、追加模式（追加时保留原文件内容）。仅支持文本文件，禁止写入二进制文件。自动创建父目录",
    "list_directory": "列出目录内容，包含文件大小、修改时间，支持递归、分页、排序（name/size）、隐藏文件过滤。适合查看目录、找大文件、清理空间",
    "delete_file": "删除文件或目录，默认放入回收站更安全（force=False）。设force=True则永久删除不可恢复。支持递归删除目录",
    "move_file": "移动或重命名文件（跨目录操作），目标目录不存在会自动创建。支持overwrite覆盖控制。适合'移动文件'或'把文件改名并移动'场景",
    "search_files": "递归搜索匹配或排除模式的文件/目录，支持中文文件名搜索、通配符、排除模式、排序（mtime/name/size）、分页。适合找特定文件、按时间排序找最近修改",
    "generate_report": "生成文件操作报告，记录所有操作历史",
    "copy_file": "复制文件或目录到指定位置，支持递归复制、覆盖控制、保留元数据（修改时间等）。适合备份文件",
    "create_directory": "创建新目录，如需要会自动创建父目录，目录已存在则静默成功（确保操作幂等性）",
    "get_file_info": "获取文件/目录的详细元数据，包括大小、创建/修改/访问时间、类型、权限。支持跟随/不跟随符号链接",
    "compare_files": "比较两个文件的内容/大小/修改时间差异，支持分块比较大文件",
    "batch_rename": "批量重命名文件（正则匹配），支持预览、冲突处理（skip/overwrite/rename）。首次执行建议preview=true先预览",
    "compress_files": "压缩文件或目录为zip/tar.gz，支持加密（password）和分卷（split_size）。支持任意类型文件",
    "file_monitor": "监控目录文件变化（创建/修改/删除/重命名事件），支持递归监控、过滤条件、限时监控",
    "file_statistics": "统计目录的文件数量、总大小、类型分布，支持递归统计、过滤条件、多种输出格式（json/csv/text）",
    "file_checksum": "计算文件的MD5/SHA1/SHA256/SHA512哈希值，用于校验文件完整性。支持验证哈希值、分块计算大文件",
    "read_text_file": "读取文本文件内容，支持head/tail/offset/limit分页读取。仅支持文本文件，禁止读取二进制文件。适合查看日志、代码、配置文件",
    "read_media_file": "读取图片或音频文件，返回Base64编码数据和MIME类型。支持JPG/PNG/GIF/BMP/WebP图片和MP3/WAV/OGG/M4A音频",
    "read_batch_file": "同时读取多个文本文件内容，单个文件失败不会中断整个操作。自动跳过二进制文件并提示。适合对比多个文件、批量查看配置",
    "precise_replace_in_file": "执行精确的字符串替换，支持中文内容精确匹配和替换、replace_all全局替换。仅支持文本文件，禁止编辑二进制文件",
    "edit_text_file": "使用高级模式匹配进行选择性编辑，支持同时多处编辑、缩进保留、dryRun预览模式。仅支持文本文件，禁止编辑二进制文件",
    "rename_file": "重命名文件或目录（仅同目录改名，不改变所在目录），内部通过move_file实现。适合'重命名'场景，语义明确",
    "grep_file_content": "基于ripgrep的强大内容搜索，支持正则表达式、中文内容搜索、上下文行、文件类型过滤、分页。适合搜索代码、查找函数定义、搜索关键词",
    "get_directory_tree": "获取目录的递归JSON树形结构，每个条目包含name、type、children。支持排除模式和深度限制。适合查看项目整体结构、生成目录文档",
    "list_allowed_directories": "列出服务器允许访问的所有目录，用于确定文件操作的边界",
}

# 【小沈 2026-04-29】补充 examples 参数 - 17个工具的使用示例
FILE_TOOL_EXAMPLES = {
    "write_text_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "text": "Hello World"},
        {"file_path": "D:/项目代码/config.json", "text": "{\"key\": \"value\"}", "encoding": "utf-8"},
        {"file_path": "D:/项目代码/logs/app.log", "text": "新增日志行\\n", "append": True}
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
        {"source_path": "C:/Users/用户名/Documents/a.txt", "output_path": "C:/Users/用户名/Documents/archive.zip"},
        {"source_path": "D:/项目代码/src", "output_path": "D:/项目代码/code.zip", "format": "zip", "compression_level": 6},
        {"source_path": "D:/项目代码", "output_path": "D:/backup/bak.tar.gz", "format": "tar.gz", "exclude_patterns": ["node_modules", "__pycache__"], "overwrite": false}
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
    "edit_text_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "def old():", "newText": "def new():"}]},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "import os", "newText": "import os\nimport sys"}], "dryRun": True}
    ],
    "rename_file": [
        {"file_path": "D:/documents/report_old.txt", "new_name": "report_final.txt"},
        {"file_path": "D:/projects/old_folder", "new_name": "new_folder"}
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
        "write_text_file": lambda: _get_ft().write_text_file,
        "list_directory": lambda: _get_ft().list_directory,
        "delete_file": lambda: _get_ft().delete_file,
        "move_file": lambda: _get_ft().move_file,
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
        "edit_text_file": lambda: _get_ft().edit_file,
        "rename_file": lambda: _get_ft().rename_file,
        "grep_file_content": lambda: _get_ft().grep_file_content,
        "get_directory_tree": lambda: _get_ft().get_directory_tree,
        "list_allowed_directories": lambda: _get_ft().list_allowed_directories,
    }
    
    # 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）
    TOOL_INPUT_MODELS = {
        "write_text_file": WriteTextFileInput,
        "list_directory": ListDirectoryInput,
        "delete_file": DeleteFileInput,
        "move_file": MoveFileInput,
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
        "edit_text_file": EditTextFileInput,
        "rename_file": RenameFileInput,
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
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
    "get_all_file_tool_names",
    "get_tool_input_models",
]


def get_all_file_tool_names() -> list:
    """获取所有已注册的文件工具名 - 小健 2026-05-02"""
    return list(TOOL_INPUT_MODELS.keys())


def get_tool_input_models() -> dict:
    """获取所有工具的Pydantic输入模型映射 - 小健 2026-05-02"""
    return TOOL_INPUT_MODELS