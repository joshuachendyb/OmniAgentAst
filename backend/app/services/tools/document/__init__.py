# -*- coding: utf-8 -*-
"""Document 模块 - 文档读写工具"""

from app.services.tools.document.document_register import *
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
