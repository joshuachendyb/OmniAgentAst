# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点

【架构规范】2026-04-26 小沈（更新2026-04-26）
- file_register.py 作为文件工具的注册点
- 实际工具实现在 file_tools.py 的 FileTools 类中
- 使用 registry.py 的 tool_registry.register() 显式注册

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
更新时间: 2026-04-26
"""

# ============================================================
# 文件工具注册 - 使用新的注册方式
# ============================================================
from typing import Optional
from app.services.tools.registry import register_tool, ToolCategory, tool_registry

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
    "search_files_by_name": "按名称搜索文件",  # 注册名search_files_by_name，实际方法search_files
    "generate_report": "生成报告",
    "copy_file": "复制文件",
    "create_directory": "创建目录",
    "get_file_info": "获取文件信息",
    "compress_files": "压缩文件",
    "compare_files": "比较文件",
    "batch_rename": "批量重命名",
    "file_checksum": "文件校验",
    "file_statistics": "文件统计",
    "file_monitor": "文件监控",
}


def _register_file_tools():
    """注册所有文件工具到 tool_registry"""
    ft = FileTools()
    
    # 17个工具方法映射（准确的名称）
    tool_methods = {
        "read_file": ft.read_file,
        "write_file": ft.write_file,
        "list_directory": ft.list_directory,
        "delete_file": ft.delete_file,
        "move_file": ft.move_file,
        "search_file_content": ft.search_file_content,
        "search_files_by_name": ft.search_files,  # 注意：实际方法名是search_files
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
    
    # 注册每个工具
    for name, method in tool_methods.items():
        desc = FILE_TOOL_DESCRIPTIONS.get(name, "")
        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FILE,
            implementation=method,
            version="1.0.0"
        )


# 触发注册
_register_file_tools()


# ============================================================
# 导出的工具类
# ============================================================
from app.services.tools.file.file_tools import FileTools, get_file_tools

# 兼容导出（用于旧代码）
def get_registered_tools(category: Optional[str] = None):
    """获取已注册的工具列表（兼容旧接口）"""
    return tool_registry.list_tools(category=category and ToolCategory(category))


def get_tool(name: str):
    """获取指定工具的信息（兼容旧接口）"""
    return tool_registry.get(name)


__all__ = [
    "FileTools",
    "get_file_tools",
    "get_registered_tools",  # 兼容导出
    "get_tool",              # 兼容导出
]