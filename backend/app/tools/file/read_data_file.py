# -*- coding: utf-8 -*-
"""
F14: read_data_file — 读取结构化配置文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import asyncio
import os
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


_EXT_MAP_READ = {
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".xml": "xml", ".properties": "properties",
}


def _build_read_data_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", detected_format: str = "",
    detail: str = "", item_count: int = 0,
) -> Dict[str, Any]:
    """read_data_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取数据文件失败: {detail}",
            "action": {"tool": "read_data_file", "tool_zh": "读取数据", "target": file_path, "params": {}},
            "status": {"exec_code": "error", "message": "读取失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    fmt_text = detected_format.upper() if detected_format else "未知"
    m: Dict[str, Any] = {}
    if item_count:
        m = {"item_count": {"value": item_count, "text": f"{item_count}项"}}
    return {
        "summary": f"已读取{fmt_text}格式文件: {file_path}",
        "action": {"tool": "read_data_file", "tool_zh": "读取数据", "target": file_path, "params": {}},
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": m,
    }


async def read_data_file(
    file_path: str,
    format: Optional[str] = None,
) -> Dict[str, Any]:
    """读取结构化配置文件 — 小欧 2026-06-17 — 小欧 2026-06-22 独立文件"""
    encoding = "utf-8"
    action = "read"
    if not file_path:
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail="file_path是必填参数")
        return build_error(data={"error_detail": "file_path是必填参数", "params": {"file_path": file_path}}, llm_data=llm_data)
    is_valid, err = _validate_path(file_path)
    if not is_valid:
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail=err)
        return build_error(data={"error_detail": err, "params": {"file_path": file_path}}, llm_data=llm_data)
    detected = format
    if not detected:
        ext = os.path.splitext(file_path)[1].lower()
        detected = _EXT_MAP_READ.get(ext)
    if not detected:
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail=f"无法识别文件格式: {file_path},请通过format参数指定")
        return build_error(data={"error_detail": "无法识别文件格式", "params": {"file_path": file_path}}, llm_data=llm_data)

    from app.tools.toolhelper import data_format_helper as df_tools
    dispatch = df_tools.FORMAT_DISPATCH.get(detected)
    if not dispatch:
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail=f"不支持读取{detected}格式")
        return build_error(data={"error_detail": f"不支持读取{detected}格式", "params": {"file_path": file_path, "format": detected}}, llm_data=llm_data)
    func = dispatch.get("read")
    if func is None:
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail=f"{detected}格式不支持读取")
        return build_error(data={"error_detail": f"{detected}格式不支持读取", "params": {"file_path": file_path}}, llm_data=llm_data)

    try:
        kwargs = {"file_path": file_path, "encoding": encoding}
        result = await asyncio.to_thread(func, **kwargs)
        result_data = result.get("data", result) if isinstance(result, dict) else result
        item_count = len(result_data) if isinstance(result_data, (dict, list)) else 0
        llm_data = _build_read_data_file_llm_data("success", 0, file_path=file_path, detected_format=detected, item_count=item_count)
        return build_success(
            data={"data": result_data, "format": detected, "file_path": file_path, "action": action},
            llm_data=llm_data,
        )
    except Exception as e:
        logger.error(f"[read_data_file] 执行失败: {e}")
        llm_data = _build_read_data_file_llm_data("error", 0, file_path=file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)