# -*- coding: utf-8 -*-
"""
F8: compress_files — 压缩文件

从file_tools.py拆分而来 — 小欧 2026-06-22
内聚: _has_wildcard / _compress_entries / _write_zip_entries / _write_zip / _write_targz
      _build_compress_result / _get_total_size_sync / compress_files主函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import glob
import os
import tarfile
import time
import time as _time_mod
import zipfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.services.context_vars import _current_task_id
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.json_utils import coerce_json
from app.utils.logger import logger


def _validate_path(file_path: str):
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _build_compress_files_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
) -> Dict[str, Any]:
    """compress_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"压缩文件失败: {detail}",
            "action": {"tool": "compress_files", "tool_zh": "压缩文件", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "压缩失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"压缩文件成功: {source}",
        "action": {"tool": "compress_files", "tool_zh": "压缩文件", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "压缩成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def _has_wildcard(path_str: str) -> bool:
    """检查路径是否包含通配符 — 小欧 2026-06-19"""
    return any(c in path_str for c in ('*', '?', '[', ']'))


def _compress_entries(source: Path, deadline: float) -> Generator[Tuple[Path, str], None, bool]:
    """通用文件遍历生成器 — 小健 2026-05-25"""
    source_str = str(source)
    if _has_wildcard(source_str):
        matched_paths = glob.glob(source_str)
        base_dir = Path(matched_paths[0]).parent if matched_paths else source.parent
        for matched in sorted(matched_paths):
            matched_path = Path(matched)
            if matched_path.is_file():
                yield matched_path, matched_path.name
            elif matched_path.is_dir():
                for item in matched_path.rglob("*"):
                    if time.monotonic() > deadline:
                        return True
                    if item.is_file():
                        yield item, str(item.relative_to(base_dir))
        return False
    if source.is_file():
        yield source, source.name
        return False
    for item in source.rglob("*"):
        if time.monotonic() > deadline:
            return True
        if item.is_file():
            yield item, str(item.relative_to(source.parent))
    return False


def _write_zip_entries(zf, source: Path, deadline: float, compressed_files: List[str]) -> None:
    """写入压缩条目 — 小欧 2026-06-19"""
    for file_path, arcname in _compress_entries(source, deadline):
        zf.write(file_path, arcname)
        compressed_files.append(str(file_path))


def _write_zip(
    source: Path, destination: Path, compression_level: int,
    password: Optional[str], deadline: float,
) -> Tuple[List[str], bool]:
    """写入zip压缩包 — 小健 2026-05-25"""
    compressed_files: List[str] = []
    if password:
        from app.tools.tool_fc_helper import _check_module
        if not _check_module("pyzipper"):
            raise ImportError("pyzipper库未安装,无法创建加密ZIP,请先执行: pip install pyzipper")
        import pyzipper
        compression = pyzipper.ZIP_STORED if compression_level == 0 else pyzipper.ZIP_DEFLATED
        with pyzipper.AESZipFile(destination, 'w', compression=compression, compresslevel=compression_level) as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.setencryption(pyzipper.WZ_AES)
            _write_zip_entries(zf, source, deadline, compressed_files)
    else:
        compression = zipfile.ZIP_STORED if compression_level == 0 else zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(destination, 'w', compression=compression, compresslevel=compression_level) as zf:
            _write_zip_entries(zf, source, deadline, compressed_files)
    return compressed_files, False


def _write_targz(source: Path, destination: Path, deadline: float) -> Tuple[List[str], bool]:
    """写入tar.gz压缩包 — 小健 2026-05-25"""
    compressed_files: List[str] = []
    with tarfile.open(destination, 'w:gz') as tf:
        for file_path, arcname in _compress_entries(source, deadline):
            tf.add(file_path, arcname)
            compressed_files.append(str(file_path))
    return compressed_files, False


def _build_compress_result(
    source: str, destination: str, fmt: str, compression_level: int,
    password: Optional[str], original_size: int, compressed_size: int,
    compressed_files: List[str],
) -> Dict[str, Any]:
    """构建压缩成功结果dict — 小健 2026-05-25"""
    ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0
    return {
        "source_path": source,
        "destination_path": destination,
        "format": fmt,
        "compression_level": compression_level,
        "encrypted": password is not None,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": ratio,
        "compressed_files": compressed_files,
        "file_count": len(compressed_files),
    }


def _get_total_size_sync(path: Path, deadline: float) -> int:
    """同步计算源路径总大小 — 小健 2026-05-25"""
    path_str = str(path)
    if _has_wildcard(path_str):
        total_size = 0
        for matched in glob.glob(path_str):
            matched_path = Path(matched)
            if matched_path.is_file():
                total_size += matched_path.stat().st_size
            elif matched_path.is_dir():
                for file_path in matched_path.rglob("*"):
                    if time.monotonic() > deadline:
                        break
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
        return total_size
    if path.is_file():
        return path.stat().st_size
    total_size = 0
    for file_path in path.rglob("*"):
        if time.monotonic() > deadline:
            break
        if file_path.is_file():
            total_size += file_path.stat().st_size
    return total_size


async def compress_files(
    source: str,
    destination: str,
    format: str = "zip",
    password: Optional[str] = None,
    overwrite: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """压缩文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    exclude_patterns = coerce_json(exclude_patterns)
    compression_level = 6

    is_valid_src, err_src = _validate_path(source)
    if not is_valid_src:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"源路径验证失败: {err_src}")
        return build_error(data={"error_detail": f"源路径验证失败: {err_src}", "params": {"source": source}}, llm_data=llm_data)

    is_valid_dst, err_dst = _validate_path(destination)
    if not is_valid_dst:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"目标路径验证失败: {err_dst}")
        return build_error(data={"error_detail": f"目标路径验证失败: {err_dst}", "params": {"destination": destination}}, llm_data=llm_data)

    if not overwrite and os.path.exists(destination):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"目标文件已存在: {destination}")
        return build_error(data={"error_detail": f"目标文件已存在: {destination},可设置overwrite=true覆盖", "params": {"destination": destination}}, llm_data=llm_data)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail="No active task")
        return build_error(data={"error_detail": "No active task", "params": {}}, llm_data=llm_data)

    if format not in ("zip", "tar.gz"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"不支持的压缩格式: {format}")
        return build_error(data={"error_detail": f"不支持的压缩格式: {format},支持格式: zip, tar.gz", "params": {"format": format}}, llm_data=llm_data)

    src = Path(source)
    dst = Path(destination)

    try:
        if _has_wildcard(source):
            if not glob.glob(source):
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"通配符无匹配: {source}")
                return build_error(data={"error_detail": f"通配符无匹配: {source}", "params": {"source": source}}, llm_data=llm_data)
        elif not src.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"源路径不存在: {source}")
            return build_error(data={"error_detail": f"源路径不存在: {source}", "params": {"source": source}}, llm_data=llm_data)

        dst.parent.mkdir(parents=True, exist_ok=True)

        from app.services.safety.file_safety import record_operation, execute_with_safety
        from app.db.models.operation_enums import OperationType
        from app.tools.tool_constants import TOOL_TIMEOUTS

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.COMPRESS,
            source_path=src, destination_path=dst,
            sequence_number=0,
        )

        _cf_deadline = time.monotonic() + TOOL_TIMEOUTS.get("compress_files", TOOL_TIMEOUTS["default"]) - 2
        original_size = _get_total_size_sync(src, _cf_deadline)

        def _compress_sync():
            try:
                if format == "zip":
                    compressed_files, _ = _write_zip(src, dst, compression_level, password, _cf_deadline)
                else:
                    compressed_files, _ = _write_targz(src, dst, _cf_deadline)
                compressed_size = dst.stat().st_size
                return _build_compress_result(
                    str(src), str(dst), format, compression_level,
                    password, original_size, compressed_size, compressed_files)
            except Exception:
                if dst.exists():
                    try:
                        dst.unlink()
                    except OSError:
                        pass
                raise

        result = await asyncio.to_thread(
            execute_with_safety, operation_id=operation_id, operation_func=_compress_sync)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if result:
            llm_data = _build_compress_files_llm_data("success", duration_ms, source)
            return build_success(data={"operation_id": operation_id, **result}, llm_data=llm_data)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail="压缩失败")
        return build_error(data={"error_detail": "压缩失败", "params": {"source": source}}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=str(e))
        return build_error(data={"error_detail": f"压缩失败: {str(e)}", "params": {"source": source}}, llm_data=llm_data)
