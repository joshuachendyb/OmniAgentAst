# -*- coding: utf-8 -*-
"""
F1: read_text_file — 读取文本文件

从file_tools.py拆分而来，按工具分类聚合设计 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import (
    READ_FILE_DEFAULT_LIMIT,
    MAX_READ_SIZE,
    BINARY_EXTENSIONS,
)
from app.constants import (
    ERR_FILE_READ_FAILED,
    ERR_FILE_READ_BINARY_FILE,
)
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _get_file_encoding(file_path: str) -> Dict[str, Any]:
    """内联编码检测，替代已删除的 file_helper.get_file_encoding — 小欧 2026-06-22"""
    import os
    from app.tools.tool_fc_helper import _detect_encoding
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return {"data": {"encoding": "utf-8", "confidence": 0.5}}
        detected = _detect_encoding(Path(file_path))
        if detected in ("utf-8-sig", "utf-16-le", "utf-16-be", "utf-8"):
            confidence = 1.0 if detected != "utf-8" else 0.95
            return {"data": {"encoding": detected, "confidence": confidence}}
        common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin-1']
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                return {"data": {"encoding": encoding, "confidence": 0.9}}
            except UnicodeDecodeError:
                continue
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}
    except Exception:
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小沈 2026-06-17 委托path_validator — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _is_binary_file(file_path: str) -> Tuple[bool, str]:
    """检测文件是否为二进制文件 — 小沈 2026-05-02 — 小欧 2026-06-22"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        return True, f"文件后缀 '{suffix}' 属于二进制文件类型，禁止使用text工具操作"
    return False, ""


async def _try_read_file_with_encodings(
    path: Path,
    preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取,返回 (content, used_encoding, error) — 小沈 2026-05-25 — 小欧 2026-06-22"""
    try:
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = _get_file_encoding(str(path))
            encodings_to_try = []
            if auto and auto.get("data", {}).get("encoding"):
                encodings_to_try.append(auto["data"]["encoding"])
        encodings_to_try.extend(["utf-8", "gbk", "gb2312", "utf-8-sig"])

        do_detect = preferred is None

        for enc in encodings_to_try:
            if enc is None:
                continue
            try:
                def _read(e=enc):
                    with open(path, 'r', encoding=e, errors='replace') as f:
                        return f.read()
                content = await asyncio.to_thread(_read)
                if do_detect and '\ufffd' in content:
                    content = None
                    continue
                return content, enc, None
            except Exception:
                continue

        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)


def _select_lines(
    lines: list,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """根据参数选择行并构建 _data 字典 — 小沈 2026-05-25 — 小欧 2026-06-22"""
    total = len(lines)
    params = {}

    if head is not None:
        selected = lines[:min(head, total)]
        params["head"] = head
    elif tail is not None:
        start = max(0, total - tail)
        selected = lines[start:]
        params["tail"] = tail
    elif offset is not None:
        start_idx = max(0, offset - 1)
        effective_limit = limit if limit else READ_FILE_DEFAULT_LIMIT
        selected = lines[start_idx:start_idx + effective_limit]
        params.update({
            "offset": offset, "limit": limit,
            "start_line": offset, "end_line": offset + len(selected) - 1,
        })
    else:
        selected = lines

    content = "".join(selected)
    return {
        "content": content,
        "total_lines": total,
        "line_count": len(selected),
        **params,
    }


def _build_read_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", line_count: int = 0,
    total_lines: int = 0, file_size: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取文件失败: {detail}",
            "action": {"tool": "read_text_file", "tool_zh": "读取文件", "target": file_path, "params": {}},
            "status": {"exec_code": "error", "message": "读取文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取文件成功: {file_path} ({line_count}/{total_lines}行)",
        "action": {"tool": "read_text_file", "tool_zh": "读取文件", "target": file_path, "params": {}},
        "status": {"exec_code": "success", "message": "读取文件成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "line_count": {"value": line_count, "text": f"{line_count}行"},
            "file_size": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def read_text_file(
    file_path: str,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"{binary_reason}。请使用read_media_file工具读取媒体文件",
            )
            return build_error(data={"error_detail": binary_reason, "params": {"file_path": file_path}}, llm_data=llm_data)

        for _name, _val in [("head", head), ("tail", tail), ("offset", offset), ("limit", limit)]:
            if _val is not None and _val < 1:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail=f"{_name}必须>=1,当前值: {_val}",
                )
                return build_error(data={"error_detail": f"{_name}必须>=1", "params": {_name: _val}}, llm_data=llm_data)

        if head is not None and tail is not None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path, detail="head和tail不能同时使用",
            )
            return build_error(data={"error_detail": "head和tail不能同时使用", "params": {"head": head, "tail": tail}}, llm_data=llm_data)

        if (head is not None or tail is not None) and (offset is not None or limit is not None):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path, detail="head/tail与offset/limit不能同时使用",
            )
            return build_error(
                data={"error_detail": "head/tail与offset/limit不能同时使用", "params": {"head": head, "tail": tail, "offset": offset, "limit": limit}},
                llm_data=llm_data,
            )

        is_valid, error_msg = _validate_path(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
            return build_error(data={"error_detail": error_msg, "params": {"file_path": file_path}}, llm_data=llm_data)

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_path": file_path}}, llm_data=llm_data)

        if not path.is_file():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"路径不是文件: {file_path}")
            return build_error(data={"error_detail": "路径不是文件", "params": {"file_path": file_path}}, llm_data=llm_data)

        file_size = path.stat().st_size
        if file_size > MAX_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"文件过大({file_size}字节),请使用head/tail分段读取",
            )
            return build_error(data={"error_detail": "文件过大", "params": {"file_path": file_path, "file_size": file_size}}, llm_data=llm_data)

        content, used_encoding, error = await _try_read_file_with_encodings(path, encoding)
        if error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error)
            return build_error(data={"error_detail": error, "params": {"file_path": file_path}}, llm_data=llm_data)

        lines = content.splitlines(keepends=True)
        _data = _select_lines(lines, head, tail, offset, limit)
        _data["encoding"] = used_encoding
        _data["file_size"] = file_size

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data(
            "success", duration_ms, file_path=file_path,
            line_count=_data["line_count"], total_lines=_data["total_lines"], file_size=file_size,
        )

        return build_success(data=_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"read_text_file failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)