# -*- coding: utf-8 -*-
"""
Data Analysis 模块 - 数据分析工具

【架构规范】2026-05-02 小沈
- data_analysis_register.py: 工具注册点（导入触发注册）
- data_analysis_tools.py: 具体实现
- data_analysis_schema.py: Pydantic 模型

目录结构：
    data_analysis/
    ├── __init__.py                # 本文件，导入 data_analysis_register 触发注册
    ├── data_analysis_register.py # 工具注册点
    ├── data_analysis_tools.py    # 具体实现
    └── data_analysis_schema.py   # Pydantic 模型

Author: 小沈 - 2026-05-02
"""

from app.services.tools.data_analysis.data_analysis_register import *
from app.services.tools.data_analysis.data_analysis_tools import (
    read_csv_dataframe,
    generate_chart,
    analyze_data,
    read_excel_dataframe,
    filter_data,
)

__all__ = [
    "read_csv_dataframe",
    "generate_chart",
    "analyze_data",
    "read_excel_dataframe",
    "filter_data",
]
