# -*- coding: utf-8 -*-
"""
generate_chart — 使用matplotlib生成数据可视化图表
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""

import os
import time as _time_mod
from pathlib import Path
from typing import Dict, Any, Optional, Union, Literal

import pandas as pd

from app.utils.time_utils import timestamp_for_filename
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.common_helper import _check_module
from app.utils.json_utils import coerce_json
from app.constants import ERR_DOC_CHART_GENERATE


def _validate_chart_data(chart_data: dict) -> dict:
    """验证图表数据格式 — 小健 2026-06-22 内聚(原document_tools._validate_chart_data已删除)"""
    labels = chart_data.get("labels", [])
    values = chart_data.get("values", [])
    if not labels or not values:
        return {"code": "INVALID", "data": {"valid": False, "error": "数据必须包含labels和values字段"}}
    if len(labels) != len(values):
        return {"code": "INVALID", "data": {"valid": False, "error": f"labels({len(labels)})和values({len(values)})长度不一致"}}
    return {"code": "SUCCESS", "data": {"valid": True}}


def _build_generate_chart_llm_data(exec_code, duration_ms, chart_type="", output_path="", detail=""):
    """generate_chart的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"生成图表失败: {detail}",
            "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": {"chart_type": chart_type}},
            "status": {"exec_code": "error", "message": "生成图表失败", "code": ERR_DOC_CHART_GENERATE, "detail": detail, "hint": "请检查数据和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"成功生成{chart_type}图表: {output_path}",
        "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": {"chart_type": chart_type}},
        "status": {"exec_code": "success", "message": "图表生成成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def generate_chart(data: Union[str, Dict[str, Any]], chart_type: Literal["bar", "line", "pie", "scatter"] = "bar",
                   title: Optional[str] = None, x_label: Optional[str] = None,
                   y_label: Optional[str] = None, output_path: Optional[str] = None) -> Dict[str, Any]:
    """使用matplotlib生成数据可视化图表 — 小健 2026-06-22 拆分独立文件"""
    data = coerce_json(data)
    t0 = _time_mod.perf_counter()
    if not _check_module("matplotlib"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="matplotlib库未安装")
        return build_error(data={"error_detail": "matplotlib库未安装"}, llm_data=llm_data)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        source_file_dir = None
        chart_data = None

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=f"文件不存在: {data}")
                return build_error(data={"error_detail": f"文件不存在: {data}"}, llm_data=llm_data)
            source_file_dir = str(path.parent)

            if data.endswith('.xlsx') or data.endswith('.xls'):
                df = pd.read_excel(data, engine="openpyxl")
            else:
                df = pd.read_csv(data)

            if len(df.columns) < 2:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据至少需要2列(标签列+数值列)")
                return build_error(data={"error_detail": "数据至少需要2列"}, llm_data=llm_data)

            labels = df.iloc[:, 0].tolist()
            values = df.iloc[:, 1].tolist()
            chart_data = {"labels": labels, "values": values}
        elif isinstance(data, dict):
            chart_data = data
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="data参数必须是文件路径(str)或图表数据(dict)")
            return build_error(data={"error_detail": "data参数必须是文件路径或图表数据"}, llm_data=llm_data)

        validation = _validate_chart_data(chart_data)
        if validation["code"] != "SUCCESS" or not validation["data"].get("valid", False):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_detail = validation["data"].get("error", "数据格式错误")
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=err_detail)
            return build_error(data={"error_detail": err_detail}, llm_data=llm_data)

        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])

        if not labels or not values:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据格式错误,需要包含labels和values字段")
            return build_error(data={"error_detail": "数据格式错误"}, llm_data=llm_data)

        if output_path is None:
            timestamp = timestamp_for_filename()
            if source_file_dir:
                output_path = os.path.join(source_file_dir, f"chart_{timestamp}.png")
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="data为字典时必须指定output_path参数")
                return build_error(data={"error_detail": "data为字典时必须指定output_path"}, llm_data=llm_data)

        fig, ax = plt.subplots(figsize=(10, 6))
        chart_type_lower = chart_type

        try:
            if chart_type_lower == "pie":
                ax.pie(values, labels=labels, autopct="%1.1f%%")
            elif chart_type_lower == "bar":
                ax.bar(labels, values)
            elif chart_type_lower == "line":
                ax.plot(labels, values, marker="o")
            elif chart_type_lower == "scatter":
                ax.scatter(labels, values)
            else:
                ax.bar(labels, values)

            if title:
                ax.set_title(title)
            if x_label and chart_type_lower != "pie":
                ax.set_xlabel(x_label)
            if y_label and chart_type_lower != "pie":
                ax.set_ylabel(y_label)

            plt.tight_layout()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
        finally:
            plt.close(fig)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("success", duration_ms, chart_type_lower, output_path)
        return build_success(data={"output_path": output_path, "chart_type": chart_type_lower}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=str(e))
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


__all__ = ["generate_chart"]