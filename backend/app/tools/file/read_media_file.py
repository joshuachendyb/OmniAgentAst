# -*- coding: utf-8 -*-
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
from app.tools.tool_constants import MAX_MEDIA_READ_SIZE
from app.tools.tool_constants import ERR_FILE_READ_FAILED
from app.tools.file_type_checker import check_for_media_tool
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger


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
            "action": {"tool": "readmedia", "tool_zh": "读取媒体", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取媒体文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
            "summary": f"读取媒体文件{file_path}，成功:媒体类型: {mime_type}，内容大小:{file_size}字节",
        "action": {"tool": "readmedia", "tool_zh": "读取媒体", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取媒体文件成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "file_size": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def readmedia(
    file_path: str,
) -> Dict[str, Any]:
    """读取媒体文件,返回Base64编码 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 增加文件类型前置检查"""
    t0 = _time_mod.perf_counter()
    try:
        # 文件类型前置检查 — 小健 2026-06-24
        is_valid, error_detail, suggested_tool = check_for_media_tool(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, hint="请检查文件类型，或使用 readtext/read_document 工具")
            return build_error(data={}, llm_data=llm_data)

        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=err, hint="请检查文件路径是否正确")
            return build_error(data={}, llm_data=llm_data)

        path = Path(file_path)

        file_size = path.stat().st_size
        if file_size > MAX_MEDIA_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"媒体文件过大({file_size}字节),超过读取上限{MAX_MEDIA_READ_SIZE // 1024 // 1024}MB",
                hint="文件过大，请使用更小的文件",
            )
            return build_error(data={}, llm_data=llm_data)

        suffix = path.suffix.lower()
        if suffix == '.pdf':
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail="PDF文件请使用read_document工具读取", hint="请使用 read_document 工具读取 PDF 文件")
            return build_error(data={}, llm_data=llm_data)

        _TEXT_EXTENSIONS = {
            '.txt', '.md', '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.c', '.cpp', '.h',
            '.rs', '.rb', '.swift', '.kt', '.scala',
            '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.xml', '.properties',
            '.csv', '.html', '.htm', '.css', '.scss', '.less', '.sql',
            '.sh', '.bat', '.ps1', '.cmd', '.log', '.env',
            '.rtf', '.odt', '.ods', '.odp',
        }
        _DOC_EXTENSIONS = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}
        if suffix in _DOC_EXTENSIONS:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"文件后缀 '{suffix}' 是文档文件，请使用read_document工具读取",
                hint="请使用 read_document 工具读取文档文件",
            )
            return build_error(data={}, llm_data=llm_data)
        if suffix in _TEXT_EXTENSIONS:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"文件后缀 '{suffix}' 是文本文件，请使用readtext工具读取",
                hint="请使用 readtext 工具读取文本文件",
            )
            return build_error(data={}, llm_data=llm_data)

        mime_type = _MIME_MAP.get(suffix, "application/octet-stream")

        def _read_sync():
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')

        b64_data = await asyncio.to_thread(_read_sync)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data(
            "success", duration_ms, file_path=str(path),
            file_name=path.name, mime_type=mime_type, file_size=file_size,
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
            data={"mime_type": mime_type, "base64_data": b64_data},
            llm_data=llm_data,
        )
    except Exception as e:
        logger.error(f"readmedia failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint="请检查文件路径和权限")
        return build_error(data={}, llm_data=llm_data)