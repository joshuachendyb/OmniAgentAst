# -*- coding: utf-8 -*-
"""
F9: extract_archive — 解压文件

从file_tools.py拆分而来 — 小欧 2026-06-22
内聚: _is_safe_path / _resolve_output_dir / _extract_zip_archive / _extract_tar_archive / _extract_archive_impl
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import os
import tarfile
import time as _time_mod
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FILE_EXTRACT

from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger



def _build_extract_archive_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", hint: str = "",
    user_destination: Optional[str] = None, user_overwrite: Optional[bool] = None,
    extracted_files: int = 0, skipped_files: int = 0, fmt: str = "",
) -> Dict[str, Any]:
    """extract_archive的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数+修复error code"""
    _act_params = {"source": source}
    if user_destination:
        _act_params["destination"] = user_destination
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if exec_code == "error":
        return {
            "summary": f"解压文件{source}，失败",
            "action": {"tool": "extract", "tool_zh": "解压文件", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "解压失败", "code": ERR_FILE_EXTRACT, "detail": detail, "hint": hint if hint else "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _m = {}
    if fmt:
        _m["format"] = {"value": fmt, "text": fmt}
    if extracted_files:
        _m["extracted_files"] = {"value": extracted_files, "text": f"解压{extracted_files}个文件"}
    if skipped_files:
        _m["skipped_files"] = {"value": skipped_files, "text": f"跳过{skipped_files}个文件"}
    parts = [f"解压{extracted_files}个文件"]
    if skipped_files:
        parts.append(f"跳过{skipped_files}个文件")
    return {
        "summary": f"解压文件{source}，成功: {'，'.join(parts)}",
        "action": {"tool": "extract", "tool_zh": "解压文件", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "解压成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": _m,
    }


def _is_safe_path(output_dir: str, member_path: str) -> bool:
    """检查解压成员路径是否在output_dir内 — 小沈 2026-05-05"""
    try:
        result = os.path.normpath(os.path.join(output_dir, member_path))
        base = os.path.normpath(output_dir)
        return result.startswith(base + os.sep) or result == base
    except Exception:
        return False


def _resolve_output_dir(archive_path: str, output_dir: Optional[str] = None) -> str:
    """自动推断输出目录 — 小健 2026-05-25"""
    if output_dir:
        return os.path.abspath(output_dir)
    archive_path = os.path.abspath(archive_path)
    base_name = os.path.basename(archive_path)
    for ext in ['.zip', '.tar.gz', '.tar.bz2', '.tbz2', '.tgz', '.tar', '.gz', '.bz2']:
        if base_name.lower().endswith(ext):
            base_name = base_name[:-len(ext)]
            break
    return os.path.join(os.path.dirname(archive_path), base_name)


def _do_zip_extract(zf, output_dir: str, overwrite: bool,
                     password: Optional[str] = None) -> Tuple[int, int, List[str]]:
    """通用ZIP解压逻辑（zipfile/pyzipper共用）— 小欧 2026-07-08"""
    extracted_count, skipped_count = 0, 0
    file_names = []
    if password:
        zf.setpassword(password.encode('utf-8'))
    for name in zf.namelist():
        if not _is_safe_path(output_dir, name):
            logger.warning(f"跳过路径遍历成员: {name}")
            skipped_count += 1
            continue
        target_path = os.path.join(output_dir, name)
        if not overwrite and os.path.exists(target_path):
            skipped_count += 1
            continue
        zf.extract(name, output_dir)
        extracted_count += 1
        if len(file_names) < 20:
            file_names.append(name)
    return extracted_count, skipped_count, file_names


def _extract_zip_archive(archive_path: str, output_dir: str, overwrite: bool,
                         password: Optional[str] = None) -> Dict[str, Any]:
    """解压zip文件 — 小健 2026-05-25 — 小欧 2026-07-08 pyzipper后备(AES-256)"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as zf:
            extracted_count, skipped_count, file_names = _do_zip_extract(zf, output_dir, overwrite, password)
    except (zipfile.BadZipFile, RuntimeError) as e:
        if "compression method" not in str(e):
            raise
        # AES-256加密ZIP，zipfile不支持，尝试pyzipper后备 — 小欧 2026-07-08
        try:
            from app.tools.tool_fc_helper import _check_module
            if not _check_module("pyzipper"):
                raise ImportError("pyzipper")
            import pyzipper
            with pyzipper.AESZipFile(archive_path, 'r') as zf:
                extracted_count, skipped_count, file_names = _do_zip_extract(zf, output_dir, overwrite, password)
        except ImportError:
            raise  # pyzipper不可用，抛出原异常给外层
    return {
        "output_dir": output_dir,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "format": "zip",
        "file_list": file_names,
    }


def _extract_tar_archive(archive_path: str, output_dir: str, overwrite: bool,
                         preserve_permissions: bool, mode: str, fmt: str) -> Dict[str, Any]:
    """解压tar文件 — 小健 2026-05-25"""
    extracted_count, skipped_count = 0, 0
    file_names = []
    with tarfile.open(archive_path, mode) as tf:
        for member in tf.getmembers():
            if not _is_safe_path(output_dir, member.name):
                logger.warning(f"跳过路径遍历成员: {member.name}")
                skipped_count += 1
                continue
            target_path = os.path.join(output_dir, member.name)
            if not overwrite and os.path.exists(target_path):
                skipped_count += 1
                continue
            if member.isfile():
                tf.extract(member, output_dir)
                extracted_count += 1
                if len(file_names) < 20:
                    file_names.append(member.name)
                if preserve_permissions:
                    try:
                        os.chmod(target_path, member.mode)
                    except Exception as e:
                        logger.warning(f"设置权限失败: {e}")
    return {
        "output_dir": output_dir,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "format": fmt,
        "file_list": file_names,
    }


async def extract(
    source: str,
    destination: Optional[str] = None,
    password: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """解压归档包 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()

    # 工具层校验（源路径）：非空/保留字符/保留名/系统目录/源文件存在+是文件 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.READ_FILE, source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=err, user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)

    if destination:
        # 工具层校验（目标路径）：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.WRITE, destination)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=err, user_destination=destination, user_overwrite=overwrite)
            return build_error(data={}, llm_data=llm_data)

    try:

        out_dir = _resolve_output_dir(source, destination)
        os.makedirs(out_dir, exist_ok=True)
        lower_path = source.lower()

        if lower_path.endswith('.zip'):
            result = _extract_zip_archive(source, out_dir, overwrite, password)
        elif lower_path.endswith('.tar.gz') or lower_path.endswith('.tgz'):
            result = _extract_tar_archive(source, out_dir, overwrite, True, 'r:gz', 'tar.gz')
        elif lower_path.endswith('.tar.bz2') or lower_path.endswith('.tbz2'):
            result = _extract_tar_archive(source, out_dir, overwrite, True, 'r:bz2', 'tar.bz2')
        elif lower_path.endswith('.tar'):
            result = _extract_tar_archive(source, out_dir, overwrite, True, 'r', 'tar')
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=f"不支持的压缩格式: {source}", user_destination=destination, user_overwrite=overwrite)
            return build_error(data={}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("success", duration_ms, source, user_destination=destination, user_overwrite=overwrite, extracted_files=result.get("extracted_files", 0), skipped_files=result.get("skipped_files", 0), fmt=result.get("format", ""))
        # =============================================================================
        # 数据设计：extracted_files/skipped_files/format 仍保留在 data 中供 formatter 展示，
        # 同时通过 llm_data.metrics 传入 summary，最终进入 LLM 观察文本
        # summary 示例: "解压成功: /path/file.zip，解压10个文件，跳过2个文件"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — result 含 output_dir/extracted_files/skipped_files/format
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)

    except zipfile.BadZipFile:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail="无效的ZIP文件或密码错误", user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    except tarfile.TarError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=f"TAR文件错误: {str(e)}", user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.error(f"[extract] 解压失败: {e}")
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=str(e), user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
