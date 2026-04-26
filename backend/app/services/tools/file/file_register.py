# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点

【架构规范】2026-04-26 小沈
- file_register.py 作为文件工具的注册点
- 实际工具实现在 file_tools.py 的 FileTools 类中
- 通过 _sync_from_old_registry() 自动同步到 tool_registry

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
- file_tools.py 使用独立的 @register_tool 装饰器注册到 _TOOL_REGISTRY
- registry.py 的 tool_registry 通过 _sync_from_old_registry() 同步
- 保留两层注册以兼容现有代码

创建时间: 2026-04-26
更新时间: 2026-04-26
"""

# ============================================================
# 文件工具注册
# ============================================================
# 
# 所有文件工具通过 file_tools.FileTools 类的方法实现
# 注册通过 file_tools._TOOL_REGISTRY 和 registry.py 同步
# 
# 如果需要在 registry.py 中显式注册，可以取消注释以下代码：
# 
# from app.services.tools.registry import register_tool, ToolCategory, tool_registry
# from app.services.tools.file import file_tools
# 
# @register_tool(
#     name="read_file",
#     description="读取文件内容",
#     category=ToolCategory.FILE,
# )
# def _register_read_file():
#     return file_tools.FileTools().read_file
# 
# 或者使用自动同步：
# from app.services.tools.registry import _sync_from_old_registry
# _sync_from_old_registry()  # 触发同步

# ============================================================
# 导出的工具类（用于获取实例）
# ============================================================
from app.services.tools.file.file_tools import FileTools, get_file_tools

__all__ = [
    "FileTools",
    "get_file_tools",
]