# -*- coding: utf-8 -*-
"""
数据分析辅助函数 — 不注册LLM，仅内部代码调用

【创建时间】2026-05-22 小沈
【来源】从 document_tools.py + data_analysis_tools.py 提取的共享Helper

包含函数：
- _serialize_rows: DataFrame行序列化为JSON安全格式
- _load_dataframe: 统一文件/数组→DataFrame加载

Author: 小沈 - 2026-05-22
"""

from typing import List, Any, Union, Dict
from pathlib import Path
import pandas as pd


def _serialize_rows(df) -> List[List[Any]]:
    """将DataFrame行数据序列化为JSON安全格式 — 小沈 2026-05-22
    合并 document_tools._serialize_pandas_rows + data_analysis_tools._serialize_rows
    处理：NaN→None / numpy标量→Python原生类型 / datetime→ISO格式字符串
    """
    rows = df.values.tolist()
    serialized_rows = []
    for row in rows:
        serialized_row = []
        for val in row:
            if pd.isna(val):
                serialized_row.append(None)
            elif hasattr(val, 'item'):
                serialized_row.append(val.item())
            elif hasattr(val, 'isoformat'):
                serialized_row.append(val.isoformat())
            else:
                serialized_row.append(val)
        serialized_rows.append(serialized_row)
    return serialized_rows


def _load_dataframe(source: Union[str, List[Dict[str, Any]]], **kwargs):
    """统一加载DataFrame — 小沈 2026-05-22
    供 analyze_data / filter_data 内部调用

    Args:
        source: 文件路径或数据数组
        **kwargs: 传递给 pd.read_csv/pd.read_excel 的额外参数

    Returns:
        pd.DataFrame

    Raises:
        ValueError: source类型不支持
        FileNotFoundError: 文件不存在
    """
    if isinstance(source, str):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {source}")
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(source, engine="openpyxl" if suffix == ".xlsx" else None, **kwargs)
        else:
            return pd.read_csv(source, **kwargs)
    elif isinstance(source, list):
        return pd.DataFrame(source)
    else:
        raise ValueError("source必须是文件路径或数据数组")


__all__ = [
    "_serialize_rows",
    "_load_dataframe",
]
