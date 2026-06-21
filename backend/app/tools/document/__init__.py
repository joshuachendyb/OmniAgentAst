# -*- coding: utf-8 -*-
"""Document 模块 - 文档读写 + 数据分析 + 数据库工具

【2026-05-18 小沈】Database工具迁入(query_sql/execute_sql/get_db_schema)
"""

from app.tools.document.document_register import *
from app.tools.document.read_pdf import read_pdf
from app.tools.document.read_docx import read_docx
from app.tools.document.read_pptx import read_pptx
from app.tools.document.read_xlsx import read_xlsx
from app.tools.document.write_docx import write_docx
from app.tools.dataanalysis.dataanalysis_tools import (
    analyze_data,
    filter_data,
    generate_chart,
)
from app.tools.dataanalysis.database_tools import (
    query_sql,
    execute_sql,
    get_db_schema,
)

__all__ = [
    "read_pdf",
    "read_docx",
    "read_pptx",
    "read_xlsx",
    "write_docx",
    "write_xlsx",
    "write_pdf",
    "write_pptx",
    "analyze_data",
    "filter_data",
    "generate_chart",
    "query_sql",
    "execute_sql",
    "get_db_schema",
]
