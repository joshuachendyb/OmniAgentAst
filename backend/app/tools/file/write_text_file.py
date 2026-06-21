# -*- coding: utf-8 -*-
"""
F2: write_text_file — 写文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import asyncio
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import MAX_READ_SIZE, BINARY_EXTENSIONS
from app.constants import ERR_FILE_WRITE_FAILED
from app.services.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.utils.logger import logger


def _get_file_encoding(file_path: str) -> Dict[str, Any]:
    """内联编码检测，替代已删除的 file_helper.get_file_encoding — 小欧 2026-06-22"""
    import os
    from app.tools.toolhelper.data_format_helper import _detect_encoding
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
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _is_binary_file(file_path: str) -> Tuple[bool, str]:
    """检测文件是否为二进制文件 — 小欧 2026-06-22"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        return True, f"文件后缀 '{suffix}' 属于二进制文件类型"
    return False, ""


def _detect_file_encoding_for_write(file_path: str, append: bool) -> str:
    """统一编码检测,复用 get_file_encoding — 小沈 2026-05-25 — 小欧 2026-06-22"""
    if not append:
        return "utf-8"
    path = Path(file_path)
    if not (path.exists() and path.is_file()):
        return "utf-8"
    try:
        result = _get_file_encoding(str(path))
        if result and result.get("data", {}).get("encoding"):
            return result["data"]["encoding"]
    except Exception:
        pass
    return "utf-8"


def _write_file_atomic(content: str, path: Path, encoding: str,
                        append: bool, create_parents: bool) -> bool:
    """原子写入文件 — 小沈 2026-05-25 — 小欧 2026-06-22"""
    try:
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding=encoding, newline='') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"[_write_file_atomic] 写入失败: {path}, 错误: {e}")
        return False


def _check_write_safety(file_path: str, content: str,
                         encoding: Optional[str] = None) -> Tuple[Optional[str], str]:
    """写入前安全检查 — 小沈 2026-05-25 — 小欧 2026-06-22"""
    if not file_path or not file_path.strip():
        return "file_path不能为空", content
    if content is None:
        return "content不能为None", ""
    is_valid, error_msg = _validate_path(file_path)
    if not is_valid:
        return error_msg, content
    return None, content


def _build_write_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", bytes_written: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """write_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入文件失败: {detail}",
            "action": {"tool": "write_text_file", "tool_zh": "写入文件", "target": file_path, "params": {}},
            "status": {"exec_code": "error", "message": "写入文件失败", "code": ERR_FILE_WRITE_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入文件成功: {file_path} ({bytes_written}字节)",
        "action": {"tool": "write_text_file", "tool_zh": "写入文件", "target": file_path, "params": {}},
        "status": {"exec_code": "success", "message": "写入文件成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"},
        },
    }


async def write_text_file(
    file_path: str,
    content: str,
    encoding: Optional[str] = None,
    append: bool = False,
) -> Dict[str, Any]:
    """写入文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    create_parents = True
    unescape = True
    error, checked_content = _check_write_safety(file_path, content, encoding)
    if error:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error)
        return build_error(data={"error_detail": error, "params": {"file_path": file_path}}, llm_data=llm_data)

    if unescape:
        checked_content = checked_content.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", "\"")

    encoding = encoding or _detect_file_encoding_for_write(file_path, append)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail="当前没有活跃任务ID")
        return build_error(data={"error_detail": "当前没有活跃任务ID", "params": {"file_path": file_path}}, llm_data=llm_data)

    path = Path(file_path)

    try:
        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.CREATE,
            destination_path=path,
            sequence_number=0,
        )

        def _do_write():
            return execute_with_safety(operation_id, lambda: _write_file_atomic(checked_content, path, encoding, append, create_parents))
        success = await asyncio.to_thread(_do_write)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            bytes_written = len(checked_content.encode(encoding))
            llm_data = _build_write_text_file_llm_data("success", duration_ms, file_path=str(path), bytes_written=bytes_written)
            return build_success(
                data={"operation_id": operation_id, "file_path": str(path), "bytes_written": bytes_written},
                llm_data=llm_data,
            )
        else:
            llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail="写入文件失败,safety拦截")
            return build_error(data={"error_detail": "写入文件失败,safety拦截", "params": {"file_path": file_path}}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)