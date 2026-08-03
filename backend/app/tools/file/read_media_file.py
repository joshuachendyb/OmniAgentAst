# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - MAX_MEDIA_READ_SIZE 依3.5改名 READMEDIA_INPUT_MAX_BYTES(readmedia 自有内部常量, 各 tool 独立不公用, INER_ 前缀; 3.4 硬安全网保留, 文件过大拒绝, 不截断)
# 2026-07-26 - 小欧 - OOD: 删 READMEDIA_INPUT_MAX_BYTES 常量+入口检查, OOM自然抛出被except捕获(同dataanalysis模式)
# 2026-07-26 - 小沈 - BugFix #3: path参数不覆盖; #5: hint传完整路径
"""
F3: readmedia — 读媒体文件

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
from typing import Any, Dict

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FILE_READ_FAILED
from app.tools.validate.file_type_checker import check_for_media_tool
from app.tools.validate.file_path_checker import hint_for_read_error  # 统一错误提示 - 小欧 2026-07-12

from app.logger import logger


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
    hint: str = "",
) -> Dict[str, Any]:
    """read_media_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数"""
    if exec_code == "error":
        return {
            "summary": f"读取媒体文件{file_path}，失败",
            "action": {"tool": "readmedia", "tool_zh": "读取媒体", "target": file_path, "params": {"path": file_path}},
            "status": {"exec_code": "error", "message": "读取媒体文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
            "summary": f"读取媒体文件{file_path}，成功:媒体类型: {mime_type}，内容大小:{file_size}字节",
        "action": {"tool": "readmedia", "tool_zh": "读取媒体", "target": file_path, "params": {"path": file_path}},
        "status": {"exec_code": "success", "message": "读取媒体文件成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "file_size": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def readmedia(
    path: str,
) -> Dict[str, Any]:
    """读取媒体文件,返回Base64编码 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 增加文件类型前置检查 — 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量file_path — 小欧 2026-07-11
    file_path = path
    t0 = _time_mod.perf_counter()
    try:
        # 文件类型前置检查 — 小健 2026-06-24 — check_for_media_tool 内含 validate_path 存在性校验 — 小欧 2026-07-29
        is_valid, error_detail, suggested_tool = check_for_media_tool(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if suggested_tool:
                _hint = f"建议使用{suggested_tool}工具"
            elif suggested_tool == "":
                _hint = "请检查文件路径和文件名是否正确"
            else:
                _hint = "请检查文件类型，或使用 readtext/read_document 工具"
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, hint=_hint)
            return build_error(data={}, llm_data=llm_data)

        _p = Path(file_path)
        suffix = _p.suffix.lower()

        mime_type = _MIME_MAP.get(suffix, "application/octet-stream")
        file_size = _p.stat().st_size

        def _read_sync():
            with open(_p, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')

        b64_data = await asyncio.to_thread(_read_sync)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data(
            "success", duration_ms, file_path=file_path,
            file_name=_p.name, mime_type=mime_type, file_size=file_size,
        )
        # ---- observation_formatter route -------------------------------------------
        # branch: #13 readmedia
        # trigger: "base64_data" in data
        # handler: _format_readmedia(data) — 元数据 + base64 摘要
        # file:    observation_formatter.py:188-190
        # ------------------------------------------------------------------------------
        # =============================================================================
        # 数据设计：file_size 从 data 移除，通过 llm_data.metrics 传入 summary
        # summary 示例: "读取媒体文件成功: image.png (image/png)"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        return build_success(
            data={"file_name": _p.name, "mime_type": mime_type, "base64_data": b64_data},
            llm_data=llm_data,
        )
    except Exception as e:
        logger.error(f"readmedia failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint=hint_for_read_error(e, file_path))  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)
