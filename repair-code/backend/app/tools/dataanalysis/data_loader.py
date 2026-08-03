# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-26 - 小欧 - 从 analyze_data.py / filter_data.py 抽取OOD公共函数(load_data_to_df/convert_pd_value/validate_top_n)
# 2026-07-26 - 小欧 - Bug#A: .xlsx大小写不敏感修复(data.lower().endswith); Bug#B: convert_pd_value加DataFrame防御
# 2026-07-26 - 小沈 - load_data_to_df入口调normalize_list_dict展平[[{...}]]→[{...}](覆盖generate_chart直入路径)
# 2026-07-31 - 小欧 - Bug⑬修复: .xls旧格式需xlrd(防落入pd.read_csv报ParserError), .xlsm纳入openpyxl; 大小写不敏感延续 | py_compile ✓
"""
data_loader  dataanalysis模块的数据加载公用函数
【2026-07-26 小欧】从 analyze_data.py / filter_data.py 抽取OOD公共函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
from typing import Dict, Any, List, Optional, Union

import pandas as pd

from app.tools.validate.file_path_checker import validate_path, OpCategory
from app.tools.tool_fc_helper import _check_module
from app.utils.json_utils import normalize_list_dict


def load_data_to_df(data: Union[str, List[Dict[str, Any]]]) -> dict:
    """加载数据为 DataFrame（公用函数） - 小欧 2026-07-26
    异常策略：预期错误(路径无效/库缺失/类型错误)返回dict含error_detail；
             非预期异常(OOM/文件损坏/格式错误)不catch，自然抛出给调用方的try/except Exception捕获后报error给LLM"""
    data = normalize_list_dict(data)
    if isinstance(data, str):
        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 - 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 - 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, data)
        if not is_valid:
            return {"error_detail": err, "params": {"path": data}}
        # 大小写不敏感检查，防 .XLSX / .Xlsx 走pd.read_csv报解析错误 - 小欧 2026-07-26(Bug#A)
        # 2026-07-31 小欧: Bug⑬修复 — .xlsm纳入openpyxl; .xls旧格式需xlrd, 防落入pd.read_csv报ParserError
        if data.lower().endswith(('.xlsx', '.xlsm')):
            if not _check_module("openpyxl"):
                return {"error_detail": "openpyxl库未安装", "params": {"library": "openpyxl"}}
            return {"df": pd.read_excel(data, engine="openpyxl")}  # 不try/except，异常自然抛出给调用方
        if data.lower().endswith('.xls'):
            if not _check_module("xlrd"):
                return {"error_detail": "xlrd库未安装(读取.xls旧格式Excel需要)", "params": {"library": "xlrd"}}
            return {"df": pd.read_excel(data, engine="xlrd")}  # 不try/except，异常自然抛出给调用方
        return {"df": pd.read_csv(data)}  # 不try/except，异常(OOM等)自然抛出给调用方
    if isinstance(data, list):
        return {"df": pd.DataFrame(data)}
    return {"error_detail": "data参数必须是文件路径或数据数组", "params": {"data_type": type(data).__name__}}


def convert_pd_value(val: Any) -> Any:
    """统一 pandas 值转换为 Python 原生类型（公用函数） - 小欧 2026-07-26"""
    # DataFrame防御：pd.isna(DataFrame)返回DataFrame，if判断抛ValueError - 小欧 2026-07-26(Bug#B)
    if isinstance(val, pd.DataFrame):
        return None
    if isinstance(val, pd.Series):
        return {k: convert_pd_value(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val


def validate_top_n(top_n: Optional[int], lo: int = 1, hi: int = 1000) -> Optional[str]:
    """校验top_n参数范围，有效返回None，无效返回错误描述（公用函数） - 小欧 2026-07-26"""
    if top_n is not None and (top_n < lo or top_n > hi):
        return f"top_n参数必须在{lo}-{hi}之间,传入值: {top_n}"
    return None


__all__ = ["load_data_to_df", "convert_pd_value", "validate_top_n"]
