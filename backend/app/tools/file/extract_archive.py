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
from typing import Any, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.utils.logger import logger


def _build_extract_archive_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
) -> Dict[str, Any]:
    """extract_archive的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"解压文件失败: {detail}",
            "action": {"tool": "extract_archive", "tool_zh": "解压文件", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "解压失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"解压文件成功: {source}",
        "action": {"tool": "extract_archive", "tool_zh": "解压文件", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "解压成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
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


def _extract_zip_archive(archive_path: str, output_dir: str, overwrite: bool,
                         password: Optional[str] = None) -> Dict[str, Any]:
    """解压zip文件 — 小健 2026-05-25"""
    extracted_count, skipped_count = 0, 0
    with zipfile.ZipFile(archive_path, 'r') as zf:
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
    return {
        "output_dir": output_dir,
        "extracted_files": extracted_count,
        "skipped_files": skipped_count,
        "format": "zip",
    }


def _extract_tar_archive(archive_path: str, output_dir: str, overwrite: bool,
                         preserve_permissions: bool, mode: str, fmt: str) -> Dict[str, Any]:
    """解压tar文件 — 小健 2026-05-25"""
    extracted_count, skipped_count = 0, 0
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
    }


async def extract_archive(
    source: str,
    destination: Optional[str] = None,
    password: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """解压归档包 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()

    try:
        if not os.path.exists(source):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=f"压缩文件不存在: {source}")
            return build_error(data={"error_detail": f"压缩文件不存在: {source}", "params": {"source": source}}, llm_data=llm_data)

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
            llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=f"不支持的压缩格式: {source}")
            return build_error(data={"error_detail": f"不支持的压缩格式: {source}", "params": {"source": source}}, llm_data=llm_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("success", duration_ms, source)
        return build_success(data=result, llm_data=llm_data)

    except zipfile.BadZipFile:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail="无效的ZIP文件或密码错误")
        return build_error(data={"error_detail": "无效的ZIP文件或密码错误", "params": {"source": source}}, llm_data=llm_data)
    except tarfile.TarError as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=f"TAR文件错误: {str(e)}")
        return build_error(data={"error_detail": f"TAR文件错误: {str(e)}", "params": {"source": source}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.error(f"[extract_archive] 解压失败: {e}")
        llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"source": source}}, llm_data=llm_data)
