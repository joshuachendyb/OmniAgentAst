# -*- coding: utf-8 -*-
"""
F8: compress_files — 压缩文件

从file_tools.py拆分而来 — 小欧 2026-06-22
内聚: _has_wildcard / _compress_entries / _write_zip_entries / _write_zip / _write_tar
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
from app.tools.tool_constants import ERR_FILE_COMPRESS_FAILED
from app.utils.context_vars import _current_task_id
from app.utils.json_utils import coerce_json
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory, validate_str_param
from app.utils.logger import logger


def _build_compress_files_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
    original_size: int = 0, compressed_size: int = 0, file_count: int = 0,
    fmt: str = "zip", hint: str = "",
    user_destination: str = "", user_format: str = "", user_overwrite: Optional[bool] = None,
    user_exclude_patterns: Optional[str] = None,
) -> Dict[str, Any]:
    """compress_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小健 2026-06-22 重构：关键指标放入metrics — 小健 2026-06-24 hint参数化"""
    _act_params = {"source": source}
    if user_destination:
        _act_params["destination"] = user_destination
    if user_format:
        _act_params["format"] = user_format
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if user_exclude_patterns:
        _act_params["exclude_patterns"] = user_exclude_patterns
    if exec_code == "error":
        return {
            "summary": f"压缩{source}，失败",
            "action": {"tool": "compress", "tool_zh": "压缩", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "压缩失败", "code": ERR_FILE_COMPRESS_FAILED, "detail": detail, "hint": hint if hint else "请检查源路径和目标路径及权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    ratio = 1 - (compressed_size / original_size) if original_size > 0 else 0
    return {
        "summary": f"压缩{source}，成功: {file_count}个文件，{original_size}→{compressed_size}字节，压缩率{ratio:.1%}",
        "action": {"tool": "compress", "tool_zh": "压缩", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "压缩成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "file_count": {"value": file_count, "text": f"{file_count}个文件"},
            "compressed_size": {"value": compressed_size, "text": f"{compressed_size}字节"},
            "ratio": {"value": f"{ratio:.1%}", "text": f"压缩率{ratio:.1%}"},
            "format": {"value": fmt, "text": fmt},
        },
    }


def _has_wildcard(path_str: str) -> bool:
    """检查路径是否包含通配符 — 小欧 2026-06-19"""
    return any(c in path_str for c in ('*', '?', '[', ']'))


def _compress_entries(source: Path, deadline: float,
                      exclude_patterns: Optional[List[str]] = None) -> Generator[Tuple[Path, str], None, bool]:
    """通用文件遍历生成器 — 小健 2026-05-25"""
    import fnmatch
    def _is_excluded(p: Path) -> bool:
        if not exclude_patterns:
            return False
        name = p.name
        return any(fnmatch.fnmatch(name, pat) for pat in exclude_patterns)

    source_str = str(source)
    if _has_wildcard(source_str):
        matched_paths = glob.glob(source_str)
        base_dir = Path(matched_paths[0]).parent if matched_paths else source.parent
        for matched in sorted(matched_paths):
            matched_path = Path(matched)
            if matched_path.is_file():
                if not _is_excluded(matched_path):
                    yield matched_path, matched_path.name
            elif matched_path.is_dir():
                for item in matched_path.rglob("*"):
                    if time.monotonic() > deadline:
                        return True
                    if item.is_file() and not _is_excluded(item):
                        yield item, str(item.relative_to(base_dir))
        return False
    if source.is_file():
        if not _is_excluded(source):
            yield source, source.name
        return False
    for item in source.rglob("*"):
        if time.monotonic() > deadline:
            return True
        if item.is_file() and not _is_excluded(item):
            yield item, str(item.relative_to(source.parent))
    return False


def _write_zip_entries(zf, source: Path, deadline: float, compressed_files: List[str],
                       exclude_patterns: Optional[List[str]] = None) -> bool:
    """写入压缩条目，返回是否超时 — 小欧 2026-06-19 — 小欧 2026-07-07 返回timed_out"""
    timed_out = False
    for file_path, arcname in _compress_entries(source, deadline, exclude_patterns):
        if time.monotonic() > deadline:
            timed_out = True
            break
        zf.write(file_path, arcname)
        compressed_files.append(str(file_path))
    return timed_out


def _write_zip(
    source: Path, destination: Path, compression_level: int,
    password: Optional[str], deadline: float,
    exclude_patterns: Optional[List[str]] = None,
) -> Tuple[List[str], bool]:
    """写入zip压缩包，返回(文件列表, 是否超时) — 小健 2026-05-25 — 小欧 2026-07-07 传播timed_out"""
    compressed_files: List[str] = []
    timed_out = False
    if password:
        from app.tools.tool_fc_helper import _check_module
        if not _check_module("pyzipper"):
            raise ImportError("pyzipper库未安装,无法创建加密ZIP,请先执行: pip install pyzipper")
        import pyzipper
        compression = pyzipper.ZIP_STORED if compression_level == 0 else pyzipper.ZIP_DEFLATED
        with pyzipper.AESZipFile(destination, 'w', compression=compression, compresslevel=compression_level) as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.setencryption(pyzipper.WZ_AES)
            timed_out = _write_zip_entries(zf, source, deadline, compressed_files, exclude_patterns)
    else:
        compression = zipfile.ZIP_STORED if compression_level == 0 else zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(destination, 'w', compression=compression, compresslevel=compression_level) as zf:
            timed_out = _write_zip_entries(zf, source, deadline, compressed_files, exclude_patterns)
    return compressed_files, timed_out


def _write_tar(source: Path, destination: Path, deadline: float,
               mode: str = "w:gz",
               exclude_patterns: Optional[List[str]] = None) -> Tuple[List[str], bool]:
    """写入tar压缩包 — 小健 2026-05-25 — 小健 2026-06-24 重命名并支持多种tar格式"""
    compressed_files: List[str] = []
    timed_out = False
    with tarfile.open(destination, mode) as tf:
        for file_path, arcname in _compress_entries(source, deadline, exclude_patterns):
            if _time_mod.monotonic() > deadline:
                timed_out = True
                break
            tf.add(file_path, arcname)
            compressed_files.append(str(file_path))
    return compressed_files, timed_out


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


async def compress(
    source: str,
    destination: str,
    format: str = "zip",
    password: Optional[str] = None,
    overwrite: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """压缩文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    err = validate_str_param(source, "source")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=err, user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)
    exclude_patterns = coerce_json(exclude_patterns)
    compression_level = 6

    # 工具层校验（目标路径）：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.WRITE, destination)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=err, user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    if not overwrite and os.path.exists(destination):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"目标文件已存在: {destination}", hint="可设置overwrite=true覆盖", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail="没有活跃的任务,请先开始一个任务", hint="请先开始一个任务", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    if format not in ("zip", "tar", "tar.gz", "tar.bz2"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"不支持的压缩格式: {format}", hint="支持zip/tar/tar.gz/tar.bz2", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    src = Path(source)
    dst = Path(destination)

    try:
        if _has_wildcard(source):
            if not glob.glob(source):
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"通配符无匹配: {source}", hint="请检查通配符是否正确", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
                return build_error(data={}, llm_data=llm_data)
        else:
            # 工具层校验（源路径）：非空/保留字符/保留名/系统目录/路径存在 — 小欧 2026-07-04
            # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
            is_valid, err, _ = validate_path(OpCategory.EXISTS, source)
            if not is_valid:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=err, hint="请检查源路径是否存在", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
                return build_error(data={}, llm_data=llm_data)

        dst.parent.mkdir(parents=True, exist_ok=True)

        from app.services.safety.file_safety import record_operation, execute_with_safety
        from app.db.models.operation_enums import OperationType
        from app.tools.tool_constants import TOOL_TIMEOUTS

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.COMPRESS,
            source_path=src, destination_path=dst,
            sequence_number=0,
        )

        _cf_timeout = TOOL_TIMEOUTS.get("compress", TOOL_TIMEOUTS["default"])
        _cf_deadline = time.monotonic() + _cf_timeout - 2
        original_size = _get_total_size_sync(src, _cf_deadline)

        def _compress_sync():
            try:
                _timed_out = False
                if format == "zip":
                    compressed_files, _timed_out = _write_zip(src, dst, compression_level, password, _cf_deadline, exclude_patterns)
                elif format == "tar":
                    compressed_files, _timed_out = _write_tar(src, dst, _cf_deadline, "w", exclude_patterns)
                elif format == "tar.gz":
                    compressed_files, _timed_out = _write_tar(src, dst, _cf_deadline, "w:gz", exclude_patterns)
                elif format == "tar.bz2":
                    compressed_files, _timed_out = _write_tar(src, dst, _cf_deadline, "w:bz2", exclude_patterns)
                compressed_size = dst.stat().st_size
                result = _build_compress_result(
                    str(src), str(dst), format, compression_level,
                    password, original_size, compressed_size, compressed_files)
                result["timed_out"] = _timed_out
                return result
            except Exception:
                if dst.exists():
                    try:
                        dst.unlink()
                    except OSError:
                        pass
                raise

        # execute_with_safety返回bool,先执行操作拿dict再记录safety — 小沈 2026-07-07
        result = await asyncio.to_thread(_compress_sync)
        if operation_id:
            await asyncio.to_thread(execute_with_safety, operation_id=operation_id, operation_func=lambda: result)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if result:
            _timed_out = result.pop("timed_out", False)
            if _timed_out:
                try:
                    dst.unlink()
                except OSError:
                    pass
                _timeout_msg = f"压缩超时({_cf_timeout}秒)，不完整文件已删除"
                llm_data = _build_compress_files_llm_data(
                    "error", duration_ms, source,
                    detail="",
                    user_destination=destination, user_format=format, user_overwrite=overwrite,
                    user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "",
                )
                llm_data["summary"] = f"压缩{source}，失败: {_timeout_msg}"
                llm_data["status"]["hint"] = ""
                return build_error(data={}, llm_data=llm_data)
            llm_data = _build_compress_files_llm_data(
                "success", duration_ms, source,
                original_size=result.get("original_size", 0),
                compressed_size=result.get("compressed_size", 0),
                file_count=result.get("file_count", 0),
                fmt=result.get("format", "zip"),
                user_destination=destination, user_format=format, user_overwrite=overwrite,
                user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "",
            )
            safe_data = {k: v for k, v in result.items() if k not in ("source_path", "destination_path", "format", "compressed_size", "file_count", "compressed_files")}
            # ---- observation_formatter route -------------------------------------------
            # branch: #18 compress
            # trigger: "compression_ratio" in data
            # handler: _format_compress_result(data) — ratio/compression_level/encrypted/files
            # file:    observation_formatter.py:193-194
            # ------------------------------------------------------------------------------
            return build_success(data=safe_data, llm_data=llm_data)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=f"压缩失败,源路径: {source}", hint="请检查源路径和目标路径是否正确", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=str(e), hint="请检查参数是否正确", user_destination=destination, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)
