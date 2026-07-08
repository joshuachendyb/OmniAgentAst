# -*- coding: utf-8 -*-
"""
generate_chart — 使用matplotlib生成数据可视化图表
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import os
import time as _time_mod
from pathlib import Path
from typing import Dict, Any, Optional, Union, Literal

import pandas as pd

from app.utils.time_utils import timestamp_for_filename
from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.utils.json_utils import coerce_json
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger
from app.utils.paths import get_default_project_root
from app.tools.tool_constants import ERR_DOC_CHART_GENERATE


def _validate_chart_data(chart_data: dict) -> dict:
    """验证图表数据格式 — 小健 2026-06-22 内聚(原document_tools._validate_chart_data已删除)"""
    labels = chart_data.get("labels", [])
    values = chart_data.get("values", [])
    if not labels or not values:
        return {"code": "INVALID", "data": {"valid": False, "error": "数据必须包含labels和values字段"}}
    if len(labels) != len(values):
        return {"code": "INVALID", "data": {"valid": False, "error": f"labels({len(labels)})和values({len(values)})长度不一致"}}
    return {"code": "SUCCESS", "data": {"valid": True}}


def _build_generate_chart_llm_data(exec_code, duration_ms, chart_type="", output_path="", detail="", hint="",
                                    data="", title="", x_label="", y_label="", file_size=0):
    """generate_chart的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-06 data字段加[:200]截断"""
    _act_params = {"chart_type": chart_type}
    if data:
        _act_params["data"] = data[:200] if isinstance(data, str) else str(data)[:200]  # 小欧 2026-07-06 截断 chart data，防止大字段返回给LLM
    if title:
        _act_params["title"] = title
    if x_label:
        _act_params["x_label"] = x_label
    if y_label:
        _act_params["y_label"] = y_label
    if output_path:
        _act_params["output_path"] = output_path
    _target = output_path or chart_type
    if exec_code == "error":
        return {
            "summary": f"生成图表{_target}，失败: {detail}",
            "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": _act_params},
            "status": {"exec_code": "error", "message": "生成图表失败", "code": ERR_DOC_CHART_GENERATE, "detail": detail, "hint": hint if hint else "请检查数据和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    metrics = {}
    if file_size:
        metrics["file_size"] = {"value": file_size, "text": f"{file_size} bytes"}
    return {
        "summary": f"生成图表{_target}，成功: {chart_type}，已保存为{output_path}",
        "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": _act_params},
        "status": {"exec_code": "success", "message": "图表生成成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": metrics,
    }


def _parse_inline_data(data: Union[str, dict, list]) -> Optional[dict]:
    """尝试将内联JSON解析为{labels,values}格式 — 小欧 2026-07-07 加非string防御"""
    if isinstance(data, dict):
        labels = data.get("labels", [])
        values = data.get("values", [])
        if labels and values and len(labels) == len(values):
            return {"labels": labels, "values": values}
        return None
    if isinstance(data, list):
        return None
    if not isinstance(data, str):
        return None
    data = data.strip()
    if not data.startswith("{"):
        return None
    try:
        import json
        parsed = json.loads(data)
        labels = parsed.get("labels", [])
        values = parsed.get("values", [])
        if labels and values and len(labels) == len(values):
            return {"labels": labels, "values": values}
    except json.JSONDecodeError:
        pass
    return None


def generate_chart(data: Union[str, Dict[str, Any]], chart_type: Literal["bar", "line", "pie", "scatter"] = "bar",
                   title: Optional[str] = None, x_label: Optional[str] = None,
                   y_label: Optional[str] = None, output_path: Optional[str] = None) -> Dict[str, Any]:
    """使用matplotlib生成数据可视化图表 — 小健 2026-06-22 拆分独立文件 — 小欧 2026-07-07 支持内联JSON数据"""
    t0 = _time_mod.perf_counter()
    if output_path:
        # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, warn = validate_path(OpCategory.WRITE, output_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=err, hint="请检查输出路径", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
            return build_error(data={}, llm_data=llm_data)
        if warn:
            logger.warning(f"[generate_chart] {warn}")

    if not _check_module("matplotlib"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="matplotlib库未安装", hint="请安装matplotlib库", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
        return build_error(data={}, llm_data=llm_data)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.font_manager as fm
        import matplotlib.pyplot as plt
        # 注册Windows中文字体，使中文标签正确渲染 — 小欧 2026-07-08
        for _font_path in [
            "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
            "C:/Windows/Fonts/simhei.ttf",
        ]:
            try:
                if os.path.exists(_font_path):
                    fm.fontManager.addfont(_font_path)
            except Exception:
                pass
        import warnings
        # 抑制matplotlib中文字形缺失警告(字体注册失败时的fallback) — 小欧 2026-07-08
        warnings.filterwarnings('ignore', message='Glyph.*missing from font')
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        matplotlib.rcParams['axes.unicode_minus'] = False

        # 支持两种数据输入：内联JSON或文件路径 — 小欧 2026-07-07
        inline = _parse_inline_data(data)
        if inline is not None:
            labels, values = inline["labels"], inline["values"]
        else:
            # 向后兼容：文件路径读取
            path = Path(data)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=f"文件不存在: {data}", hint="请检查数据文件路径", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
                return build_error(data={}, llm_data=llm_data)
            if data.endswith('.xlsx'):
                df = pd.read_excel(data, engine="openpyxl")
            else:
                df = pd.read_csv(data)
            if len(df.columns) < 2:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据至少需要2列(标签列+数值列)", hint="数据文件至少需要2列", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
                return build_error(data={}, llm_data=llm_data)
            labels = df.iloc[:, 0].tolist()
            values = df.iloc[:, 1].tolist()
        chart_data = {"labels": labels, "values": values}

        validation = _validate_chart_data(chart_data)
        if validation["code"] != "SUCCESS" or not validation["data"].get("valid", False):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            err_detail = validation["data"].get("error", "数据格式错误")
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=err_detail, hint="数据验证失败，请检查数据格式", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
            return build_error(data={}, llm_data=llm_data)

        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])

        if not labels or not values:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据格式错误,需要包含labels和values字段", hint="数据需要labels和values字段", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
            return build_error(data={}, llm_data=llm_data)

        if output_path is None:
            timestamp = timestamp_for_filename()
            output_path = os.path.join(get_default_project_root(), f"chart_{timestamp}.png")

        fig, ax = plt.subplots(figsize=(10, 6))
        chart_type_lower = chart_type.lower()

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

        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("success", duration_ms, chart_type_lower, output_path, file_size=file_size,
                                                    data=data, title=title, x_label=x_label, y_label=y_label)
        # =============================================================================
        # 数据设计：output_path 从 data 移除，通过 llm_data.summary 传递给 LLM
        # summary 示例: "成功生成bar图表: D:/chart.png"
        # data 留空 (formatter #21 fallback 展示为空)
        # — 小欧 2026-07-06
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #0 空data
        # trigger: 无 key 可匹配
        # handler: 直接返回 "" (空字符串)
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=str(e), hint="图表生成异常，请检查数据", data=data, title=title, x_label=x_label, y_label=y_label, output_path=output_path)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["generate_chart"]