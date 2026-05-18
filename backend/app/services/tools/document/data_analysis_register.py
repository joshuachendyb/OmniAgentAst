# -*- coding: utf-8 -*-
"""
Data Analysis Register - 数据分析工具注册点（已废弃）

【架构规范】2026-05-02 小沈
【废弃 2026-05-18 小健】
- analyze_data/filter_data/generate_chart 已迁入 document_register.py
- read_csv_dataframe/read_excel_dataframe 保留在本文件（不再注册为LLM工具）
- 本注册函数已废弃，调用时仅打印警告

创建时间: 2026-05-02
更新时间: 2026-05-18
"""

import logging
from app.utils.logger import logger

from app.services.tools.document.data_analysis_tools import (
    read_csv_dataframe,
    generate_chart,
    analyze_data,
    read_excel_dataframe,
    filter_data,
)


def _register_data_analysis_tools():
    """【已废弃 2026-05-18 小健】工具已迁入document_register.py，此函数不再注册"""
    pass  # 小沈 2026-05-18：显式pass，不做任何操作
    logger.warning(
        "[data_analysis_register] _register_data_analysis_tools 已废弃，"
        "analyze_data/filter_data/generate_chart 已迁入 document_register.py"
    )

__all__ = [
    "_register_data_analysis_tools",
    "read_csv_dataframe",
    "generate_chart",
    "analyze_data",
    "read_excel_dataframe",
    "filter_data",
]
