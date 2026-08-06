# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 去噪 refactor:
#   safe_data 排除 original_size 和
#   compression_ratio(data/llm_data重复)
# 2026-07-21 - 小欧 - safe_data 恢复 original_size 和 compressed_size 字段(供调用方直接获取)
# 2026-07-26 - 小沈 - execute_with_safety传真实状态(op_ok)替代恒真lambda:result, 如实记录成功/超时
# 2026-07-29 - 小欧 - 新增timeout参数暴露给LLM: 配合ToolRetryEngine保险丝拓宽逻辑, 消除双重叠加超时
#    【病根】_cf_timeout硬编码TOOL_TIMEOUTS["compress"]=300, 保险丝同样300秒, LLM无法调大
#    【解决】compress()函数新增timeout参数(默认300), 走validate_timeout校验后传内部_cf_deadline,
#            ToolRetryEngine自动将保险丝拓宽到min(timeout+30, 630), 保险丝恒晚于内部超时
# 2026-07-29 - 小欧 - 变量名统一: 函数体 source→path / destination→dest (与schema/参数名一致), 消除NameError
# 2026-07-29 - 小欧 - 删除 import time as _time_mod 别名,统一用 time; f-string无插值改为普通字符串
# 2026-07-29 - 小欧 - 清理未使用的import(TOOL_TIMEOUTS/validate_str_param);
#                    简化_compress_sync中冗余的isinstance分支,两个raise合并为一个
# 2026-07-29 - 小欧 - 超时反馈增强:删前从result抢救已压缩文件数/大小,计算进度%,
#                     hint给出3条降级建议(增大timeout/排除大文件/分批压缩),metrics带进度数据
# 2026-08-05 - 小欧 - BUG-1修复: observation_formatter #18 触发字段由"compression_ratio"改为"compression_level"
#    【病根】safe_data 去噪剥掉 compression_ratio(与llm_data ratio重复), 致 #18 分支永不触发, 压缩观测格式化成死代码
#    【解决】仅改触发字段为 data 恒在且 compress 独有的 compression_level, 保持去噪不复原大文件列表/ratio, 分支恢复工作
# 2026-08-06 10:05:21 - 小欧 - 更正"min(timeout+30,630)"旧公式表述(已过时): BUG-2 后现行保险丝为 max(inner, CEILING=600)+BUFFER=30,
#    compress 保险丝恒=630 或 max(LLM值,600)+30, 恒晚于内部 _cf_deadline; 旧行按规范保留为历史记录
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
import fnmatch
import glob
import os
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.tool_constants import ERR_FILE_COMPRESS_FAILED, ERR_PARAMETER_INVALID
from app.services.task.task_context import _current_task_id
from app.utils.json_utils import coerce_json
from app.tools.validate.file_path_checker import validate_path, OpCategory, hint_for_write_error  # 统一错误提示 - 小欧 2026-07-12
from app.tools.validate.timeout_validator import validate_timeout  # 小欧 2026-07-29
from app.logger import logger
from app.services.safety import record_operation, execute_with_safety
from app.db.models.operation_models import OperationType


def _build_compress_files_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
    original_size: int = 0, compressed_size: int = 0, file_count: int = 0,
    fmt: str = "zip", hint: str = "", err_code: str = "",
    user_destination: str = "", user_format: str = "", user_overwrite: Optional[bool] = None,
    user_exclude_patterns: Optional[str] = None,
) -> Dict[str, Any]:
    """compress_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小健 2026-06-22 重构：关键指标放入metrics — 小健 2026-06-24 hint参数化 — 小欧 2026-07-29 err_code参数化"""
    _act_params = {"source": source}
    if user_destination:
        _act_params["destination"] = user_destination
    if user_format:
        _act_params["format"] = user_format
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if user_exclude_patterns:
        _act_params["exclude_patterns"] = user_exclude_patterns
    _code = err_code or ERR_FILE_COMPRESS_FAILED
    if exec_code == "error":
        return {
            "summary": f"压缩{source}，失败",
            "action": {"tool": "compress", "tool_zh": "压缩", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "压缩失败", "code": _code, "detail": detail, "hint": hint if hint else "请检查源路径和目标路径及权限"},
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
            if time.monotonic() > deadline:
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
    path: str,
    dest: str,
    format: str = "zip",
    password: Optional[str] = None,
    overwrite: bool = False,
    exclude_patterns: Optional[List[str]] = None,
    timeout: int = 300,
) -> Dict[str, Any]:
    """压缩文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小欧 2026-07-11 路径参数统一为path/dest — 小欧 2026-07-29 新增timeout参数"""
    t0 = time.perf_counter()
    # timeout校验 — 小欧 2026-07-29
    to_valid, to_err, _ = validate_timeout(timeout, "compress")
    if not to_valid:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        hint = "timeout必须在5-1800秒之间，建议使用300秒"
        llm_data = _build_compress_files_llm_data("error", duration_ms, "", detail="", hint=hint, err_code=ERR_PARAMETER_INVALID)
        return build_error(data={}, llm_data=llm_data)
    exclude_patterns = coerce_json(exclude_patterns)
    compression_level = 6

    # 工具层校验（目标路径）：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.WRITE, dest)
    if not is_valid:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=err, user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    if not overwrite and os.path.exists(dest):
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=f"目标文件已存在: {dest}", hint="可设置overwrite=true覆盖", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail="没有活跃的任务,请先开始一个任务", hint="请先开始一个任务", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    if format not in ("zip", "tar", "tar.gz", "tar.bz2"):
        duration_ms = int((time.perf_counter() - t0) * 1000)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=f"不支持的压缩格式: {format}", hint="支持zip/tar/tar.gz/tar.bz2", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    src = Path(path)
    dst = Path(dest)

    try:
        if _has_wildcard(path):
            if not glob.glob(path):
                duration_ms = int((time.perf_counter() - t0) * 1000)
                llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=f"通配符无匹配: {path}", hint="请检查通配符是否正确", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
                return build_error(data={}, llm_data=llm_data)
        else:
            # 工具层校验（源路径）：非空/保留字符/保留名/系统目录/路径存在 — 小欧 2026-07-04
            # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
            is_valid, err, _ = validate_path(OpCategory.EXISTS, path)
            if not is_valid:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=err, hint="请检查源路径是否存在", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
                return build_error(data={}, llm_data=llm_data)

        dst.parent.mkdir(parents=True, exist_ok=True)

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.COMPRESS,
            source_path=src, destination_path=dst,
            sequence_number=0,
        )

        _cf_timeout = timeout
        _local_start = time.monotonic()
        _local_deadline = _local_start + _cf_timeout - 2
        original_size = _get_total_size_sync(src, _local_deadline)

        def _compress_sync():
            try:
                _timed_out = False
                if format == "zip":
                    compressed_files, _timed_out = _write_zip(src, dst, compression_level, password, _local_deadline, exclude_patterns)
                elif format == "tar":
                    compressed_files, _timed_out = _write_tar(src, dst, _local_deadline, "w", exclude_patterns)
                elif format == "tar.gz":
                    compressed_files, _timed_out = _write_tar(src, dst, _local_deadline, "w:gz", exclude_patterns)
                elif format == "tar.bz2":
                    compressed_files, _timed_out = _write_tar(src, dst, _local_deadline, "w:bz2", exclude_patterns)
                compressed_size = dst.stat().st_size
                result = _build_compress_result(
                    str(src), str(dst), format, compression_level,
                    password, original_size, compressed_size, compressed_files)
                result["timed_out"] = _timed_out
                return result
            except (KeyboardInterrupt, SystemExit):
                # 主动终止: 需要释放资源, 避免孤儿进程
                if dst.exists():
                    try:
                        dst.unlink()
                    except OSError:
                        pass
                raise
            except Exception as e:
                # 非预期异常: 先清理损坏文件,再抛出原始异常
                if dst.exists():
                    try:
                        dst.unlink()
                    except OSError:
                        pass
                raise

        # 先执行操作，再如实记录操作状态 — 小沈 2026-07-07 — 小沈 2026-07-26 operation_func改lambda:op_ok传真实状态
        result = await asyncio.to_thread(_compress_sync)
        if operation_id:
            op_ok = bool(result) and not result.get("timed_out")
            await asyncio.to_thread(execute_with_safety, operation_id=operation_id, operation_func=lambda _ok=op_ok: _ok)

        duration_ms = int((time.perf_counter() - t0) * 1000)
        if result:
            _timed_out = result.pop("timed_out", False)
            if _timed_out:
                # 删前从result抢救数据: 已压缩文件数和大小 — 小欧 2026-07-29
                _done_files = result.get("file_count", 0)
                _done_bytes = result.get("compressed_size", 0)
                _orig_bytes = result.get("original_size", 0)
                _progress = _done_bytes / max(_orig_bytes, 1) if _orig_bytes else 0
                try:
                    dst.unlink()
                except OSError:
                    pass
                _hint = f"已压缩{_done_files}个文件(进度{_progress:.0%})，建议：①增大timeout重试；②排除大文件再试；③将大目录分成多个子目录分批压缩"
                llm_data = _build_compress_files_llm_data(
                    "error", duration_ms, path,
                    detail="",
                    hint=_hint,
                    user_destination=dest, user_format=format, user_overwrite=overwrite,
                    user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "",
                )
                llm_data["summary"] = f"压缩{path}，失败: 压缩超时({timeout}秒)，不完整文件已删除"
                llm_data["status"]["hint"] = _hint
                llm_data["metrics"] = {
                    "file_count": {"value": _done_files, "text": f"{_done_files}个文件"},
                    "compressed_size": {"value": _done_bytes, "text": f"{_done_bytes}字节"},
                    "progress": {"value": f"{_progress:.0%}", "text": f"进度{_progress:.0%}"},
                    "timeout": {"value": timeout, "text": f"{timeout}秒"},
                }
                return build_error(data={}, llm_data=llm_data)
            llm_data = _build_compress_files_llm_data(
                "success", duration_ms, path,
                original_size=result.get("original_size", 0),
                compressed_size=result.get("compressed_size", 0),
                file_count=result.get("file_count", 0),
                fmt=result.get("format", "zip"),
                user_destination=dest, user_format=format, user_overwrite=overwrite,
                user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "",
            )
            safe_data = {k: v for k, v in result.items() if k not in ("source_path", "destination_path", "format", "file_count", "compressed_files", "compression_ratio")}
            # ---- observation_formatter route -------------------------------------------
            # branch: #18 compress
            # trigger: "compression_level" in data — 小欧 2026-08-05 21:13
            #   (原 "compression_ratio" 被 safe_data 去噪剥掉永不成立, 改 data 恒在的 compression_level)
            # handler: _format_compress_result(data) — ratio/compression_level/encrypted/files
            # file:    observation_formatter.py:193-194
            # ------------------------------------------------------------------------------
            return build_success(data=safe_data, llm_data=llm_data)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail=f"压缩失败,源路径: {path}", hint="请检查源路径和目标路径是否正确", user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")
        return build_error(data={}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        hint = hint_for_write_error(e, Path(path).name)
        llm_data = _build_compress_files_llm_data("error", duration_ms, path, detail="", hint=hint, user_destination=dest, user_format=format, user_overwrite=overwrite, user_exclude_patterns=str(exclude_patterns) if exclude_patterns else "")  # 统一错误提示 - 小欧 2026-07-12 — 小欧 2026-07-29 修正:detail=str(e)→detail="" 屏蔽内部异常详情
        return build_error(data={}, llm_data=llm_data)
