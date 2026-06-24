# -*- coding: utf-8 -*-
"""
表格辅助函数 - 供write_docx/write_pptx/write_pdf共享使用

【铁规】helper函数只返回原始数据，严禁：
1. 调用build_success/build_error/build_warning
2. 构建llm_data
3. 直接退出tool

创建时间: 2026-06-24
作者: 小健
"""
from typing import List, Tuple, Dict, Any


def parse_markdown_table(lines: List[str], start_idx: int) -> Tuple[List[List[str]], int]:
    """
    解析Markdown表格，返回(表格数据, 结束索引)
    
    格式：
    | 列1 | 列2 | 列3 |
    |-----|-----|-----|
    | A   | B   | C   |
    
    返回：[["列1", "列2", "列3"], ["A", "B", "C"]]
    
    — 小健 2026-06-24
    """
    table_rows = []
    i = start_idx
    
    while i < len(lines):
        line = lines[i].strip()
        if not line or not line.startswith('|'):
            break
        
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        if cells:
            if not all(c.replace('-', '').replace(':', '') == '' for c in cells):
                table_rows.append(cells)
        i += 1
    
    return table_rows, i


def calculate_column_widths(table_data: List[List[str]], total_width: float = 1.0) -> List[float]:
    """
    计算列宽比例（按内容长度自适应）
    
    参数：
    - table_data: 表格数据（二维数组）
    - total_width: 总宽度（默认1.0，返回比例；可传具体值如6.0英寸）
    
    返回：每列的宽度列表
    
    — 小健 2026-06-24
    """
    if not table_data or not table_data[0]:
        return []
    
    cols = len(table_data[0])
    col_max_lens = []
    
    for ci in range(cols):
        max_len = 0
        for ri in range(len(table_data)):
            if ci < len(table_data[ri]):
                cell_text = str(table_data[ri][ci])
                max_len = max(max_len, len(cell_text))
        col_max_lens.append(max(max_len, 1))
    
    total_len = sum(col_max_lens)
    if total_len == 0:
        return [total_width / cols] * cols
    
    return [total_width * w / total_len for w in col_max_lens]


def get_table_header_style_config() -> Dict[str, Any]:
    """
    获取表头样式配置（共享配置，各工具自行应用）
    
    返回配置字典：
    {
        "bold": True,
        "font_size": 12,
        "bg_color": "003366",  # 深蓝色
        "text_color": "FFFFFF",  # 白色
    }
    
    — 小健 2026-06-24
    """
    return {
        "bold": True,
        "font_size": 12,
        "bg_color": "003366",
        "text_color": "FFFFFF",
    }


def get_table_border_config() -> Dict[str, Any]:
    """
    获取表格边框配置（共享配置，各工具自行应用）
    
    返回配置字典：
    {
        "style": "single",
        "width": 1,
        "color": "000000",  # 黑色
    }
    
    — 小健 2026-06-24
    """
    return {
        "style": "single",
        "width": 1,
        "color": "000000",
    }


def normalize_table_data(table_data: List[List[Any]]) -> List[List[str]]:
    """
    标准化表格数据（所有元素转字符串）
    
    — 小健 2026-06-24
    """
    return [[str(cell) if cell is not None else "" for cell in row] for row in table_data]


__all__ = [
    "parse_markdown_table",
    "calculate_column_widths",
    "get_table_header_style_config",
    "get_table_border_config",
    "normalize_table_data",
]