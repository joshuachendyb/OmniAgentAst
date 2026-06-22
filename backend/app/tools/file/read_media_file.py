# -*- coding: utf-8 -*-
"""
F3: read_media_file — 读媒体文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import base64
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import MAX_MEDIA_READ_SIZE
from app.constants import ERR_FILE_READ_FAILED
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


_MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".tiff": "image/tiff", ".tif": "image/tiff",
    ".ico": "image/x-icon", ".heic": "image/heic", ".heif": "image/heif",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
    ".m4a": "audio/mp4", ".flac": "audio/flac", ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma", ".mid": "audio/midi", ".midi": "audio/midi",
    ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".webm": "video/webm", ".wmv": "video/x-ms-wmv",
}


def _build_read_media_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", file_name: str = "",
    mime_type: str = "", file_size: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_media_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取媒体文件失败: {detail}",
            "action": {"tool": "read_media_file", "tool_zh": "读取媒体", "target": file_path, "params": {}},
            "status": {"exec_code": "error", "message": "读取媒体文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取媒体文件成功: {file_name} ({mime_type})",
        "action": {"tool": "read_media_file", "tool_zh": "读取媒体", "target": file_path, "params": {}},
        "status": {"exec_code": "success", "message": "读取媒体文件成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "file_size": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def read_media_file(
    file_path: str,
) -> Dict[str, Any]:
    """读取媒体文件,返回Base64编码 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    try:
        is_valid, error_msg = _validate_path(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
            return build_error(data={"error_detail": error_msg, "params": {"file_path": file_path}}, llm_data=llm_data)

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_path": file_path}}, llm_data=llm_data)
        if not path.is_file():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=f"路径不是文件: {file_path}")
            return build_error(data={"error_detail": "路径不是文件", "params": {"file_path": file_path}}, llm_data=llm_data)

        file_size = path.stat().st_size
        if file_size > MAX_MEDIA_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"媒体文件过大({file_size}字节),超过读取上限{MAX_MEDIA_READ_SIZE // 1024 // 1024}MB",
            )
            return build_error(data={"error_detail": "媒体文件过大", "params": {"file_path": file_path, "file_size": file_size}}, llm_data=llm_data)

        suffix = path.suffix.lower()
        if suffix == '.pdf':
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail="PDF文件请使用read_document工具读取")
            return build_error(data={"error_detail": "PDF请使用read_document工具", "params": {"file_path": file_path}}, llm_data=llm_data)

        mime_type = _MIME_MAP.get(suffix, "application/octet-stream")

        def _read_sync():
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')

        b64_data = await asyncio.to_thread(_read_sync)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data(
            "success", duration_ms, file_path=str(path),
            file_name=path.name, mime_type=mime_type, file_size=path.stat().st_size,
        )
        return build_success(
            data={"file_name": path.name, "mime_type": mime_type, "file_size": path.stat().st_size, "base64_data": b64_data},
            llm_data=llm_data,
        )
    except Exception as e:
        logger.error(f"read_media_file failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)