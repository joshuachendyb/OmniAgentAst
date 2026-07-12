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
from typing import List, Tuple, Dict, Any, Optional


def _equalize_column_count(table_data: List[List[str]]) -> List[List[str]]:
    """列数对齐：以最大列数为基准，短行右侧补空串，保证各行列数一致 — 小欧 2026-07-12

    仅补空、不截断、不丢数据；整齐表格为恒等变换，无行为变化。
    """
    if table_data:
        _max_cols = max(len(row) for row in table_data)
        for row in table_data:
            if len(row) < _max_cols:
                row.extend([""] * (_max_cols - len(row)))
    return table_data


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

    # 列数对齐：以最大列数为基准，短行右侧补空串，保证各行列数一致
    # 防止渲染层按表头列数建表后因行宽不一触发 IndexError（小欧 2026-07-12）
    _equalize_column_count(table_rows)
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


def dict_table_to_rows(dict_table: dict) -> List[List[str]]:
    """把dict型表格{headers,rows}转成list[list]

    — 小欧 2026-07-08（从write_pptx迁入共享）
    """
    rows = []
    headers = dict_table.get("headers", [])
    if headers:
        rows.append([str(h) if h is not None else "" for h in headers])
    for row in dict_table.get("rows", []):
        if isinstance(row, list):
            rows.append([str(c) if c is not None else "" for c in row])
        else:
            rows.append([str(row) if row is not None else ""])
    return rows


def normalize_table_data(table_data: Any) -> Optional[List[List[str]]]:
    """归一化表格数据为list[list[str]]标准格式

    覆盖格式:
    - list[list] → 原样，元素转str
    - dict{headers,rows} → 转list[list]（调dict_table_to_rows）
    - list[dict{headers,rows}] → 逐个转，合并成一张表
    - None/空 → 返回None

    — 小健 2026-06-24 创建
    — 小欧 2026-07-08 扩展支持dict/list[dict]/None
    """
    if not table_data:
        return None
    if isinstance(table_data, dict):
        rows = dict_table_to_rows(table_data)
        return _equalize_column_count(rows) if rows else None
    if isinstance(table_data, list):
        if not table_data:
            return None
        first = table_data[0]
        if isinstance(first, dict):
            result = []
            for td in table_data:
                rows = dict_table_to_rows(td)
                if rows:
                    result.extend(rows)
            return _equalize_column_count(result) if result else None
        return _equalize_column_count(
            [[str(c) if c is not None else "" for c in row] for row in table_data]
        )
    return None


__all__ = [
    "parse_markdown_table",
    "calculate_column_widths",
    "get_table_header_style_config",
    "get_table_border_config",
    "dict_table_to_rows",
    "normalize_table_data",
]