# -*- coding: utf-8 -*-
"""
Document Register - 文档读写工具注册点

【架构规范】2026-05-02 小沈
- 使用 @register_tool 装饰器注册所有文档读写工具
- 工具函数从 document_tools.py 导入

【注意】2026-05-02 小沈
- document_tools.py 中的 @register_tool 装饰器会自动注册
- 这里只需要导入以触发加载
"""

from app.services.tools.document import document_tools

__all__ = [
    "read_pdf",
    "read_docx",
    "read_xlsx",
]
