# -*- coding: utf-8 -*-
"""
Data Analysis Register - 数据分析工具注册点

【架构规范】2026-05-02 小沈
- 使用 @register_tool 装饰器注册所有数据分析工具
- 工具函数从 data_analysis_tools.py 导入

【注意】2026-05-02 小沈
- data_analysis_tools.py 中的 @register_tool 装饰器会自动注册
- 这里只需要导入以触发加载
"""

from app.services.tools.data_analysis import data_analysis_tools

__all__ = [
    "read_csv_dataframe",
    "generate_chart",
    "analyze_data",
]
