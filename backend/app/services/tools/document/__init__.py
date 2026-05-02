# -*- coding: utf-8 -*-
"""
Document 模块 - 文档读写工具

【架构规范】2026-05-02 小沈
- document_register.py: 工具注册点（导入触发注册）
- document_tools.py: 具体实现

目录结构：
    document/
    ├── __init__.py           # 本文件，导入 document_register 触发注册
    ├── document_schema.py    # Pydantic模型定义
    ├── document_register.py  # 工具注册点
    └── document_tools.py     # 具体实现

Author: 小沈 - 2026-05-02
"""

from app.services.tools.document import document_register
from app.services.tools.document import document_tools

from app.services.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_xlsx,
)

__all__ = [
    "read_pdf",
    "read_docx",
    "read_xlsx",
]
