# -*- coding: utf-8 -*-
"""
环境检查工具函数模块（已清空）

【2026-05-18 小沈】5个验证工具已迁入document_tools.py作为内部helper：
- validate_csv_format → _validate_csv_format
- validate_chart_data → _validate_chart_data
- check_pdf_readable → _check_pdf_readable
- check_docx_readable → _check_docx_readable
- check_xlsx_readable → _check_xlsx_readable

read_document()路由函数在调用各_read_xxx()之前自动调用对应_check_xxx_readable()
generate_chart()在执行前自动调用_validate_chart_data()

原LLM可见的5个独立工具已从system_register.py中删除，不再暴露给LLM。

Author: 小沈 - 2026-05-18
"""
