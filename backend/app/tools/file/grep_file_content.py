# -*- coding: utf-8 -*-
"""
F7: grep_file_content — 搜索文件内容

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import re as re_mod
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import TOOL_TIMEOUTS, MAX_SEARCH_FILE_SIZE, MAX_SEARCH_RESULTS
from app.constants import ERR_FILE_CONTENT_SEARCH_FAILED
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.tools.file_type_checker import is_binary_file, BINARY_EXTENSIONS, TEXT_EXTENSIONS
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


_ENCODING_PRIORITY = ["utf-8", "gbk", "gb2312", "utf-8-sig", "latin-1", "cp1252", "iso-8859-2", "cp1250"]


def _read_file_safe(file_path: Path) -> List[str]:
    """多编码尝试读取文件行 — 小健 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-25 chardet自动检测"""
    try:
        size = file_path.stat().st_size
        if size > MAX_SEARCH_FILE_SIZE:
            return []
    except OSError:
        return []
    # chardet自动检测编码
    detected_enc = None
    try:
        import chardet as _chardet
        raw = file_path.read_bytes()
        det = _chardet.detect(raw)
        if det and det.get("encoding") and det.get("confidence", 0) > 0.5:
            detected_enc = det["encoding"]
    except Exception:
        pass
    # 构建编码列表：chardet结果优先
    enc_list = []
    if detected_enc:
        enc_list.append(detected_enc)
    for enc in _ENCODING_PRIORITY:
        if enc not in enc_list:
            enc_list.append(enc)
    # 尝试精确解码
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue
    # 所有编码失败，用replace兜底
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc, errors="replace") as f:
                lines = f.readlines()
            total_chars = sum(len(line) for line in lines)
            if total_chars > 0:
                replace_count = sum(line.count("\ufffd") for line in lines)
                if replace_count / total_chars > 0.05:
                    continue
            return lines
        except (UnicodeDecodeError, LookupError):
            continue
    return []


def _build_grep_file_content_llm_data(
    exec_code: str, duration_ms: int,
    pattern: str = "", search_dir: str = "",
    total_files: int = 0, total_matches: int = 0,
    truncated: bool = False, detail: str = "",
) -> Dict[str, Any]:
    """grep_file_content的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小健 2026-06-23 添加结果数量限制提示"""
    if exec_code == "error":
        return {
            "summary": f"内容搜索失败: {detail}",
            "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_CONTENT_SEARCH_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"搜索完成: 匹配{total_matches}行, {total_files}个文件（结果被截断，可能不完整）",
            "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}},
            "status": {"exec_code": "warning", "message": "结果被截断，可能不完整", "code": "", "detail": "搜索超时或结果数量达到上限，仅返回部分结果", "hint": "可缩小搜索范围、使用head_limit参数限制结果数量或增加超时时间"},
            "duration_ms": duration_ms,
            "metrics": {
                "total_files": {"value": total_files, "text": f"{total_files}个文件"},
                "total_matches": {"value": total_matches, "text": f"{total_matches}行"},
            },
        }
    return {
        "summary": f"搜索完成: 匹配{total_matches}行, {total_files}个文件",
        "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "total_files": {"value": total_files, "text": f"{total_files}个文件"},
            "total_matches": {"value": total_matches, "text": f"{total_matches}行"},
        },
    }


def _grep_files_sync(
    search_dir: Path, pattern: str, glob_filter: Optional[str],
    ignore_case: bool, deadline: float,
    output_mode: str,
) -> Tuple[List[Dict], int, int, bool, List[str]]:
    """同步搜索文件内容 — 小欧 2026-06-22 — 小健 2026-06-24 增加二进制文件检测和提示"""
    results = []
    total_matches = 0
    total_files = 0
    skipped_binary_files = []  # 记录跳过的二进制文件
    flags = re_mod.IGNORECASE if ignore_case else 0
    try:
        regex = re_mod.compile(pattern, flags)
    except re_mod.error as e:
        raise ValueError(f"正则表达式无效: {e}") from e

    for root, dirs, files in os.walk(search_dir):
        if _time_mod.monotonic() > deadline:
            break
        if total_matches >= MAX_SEARCH_RESULTS:
            break
        for fname in files:
            if _time_mod.monotonic() > deadline:
                break
            if total_matches >= MAX_SEARCH_RESULTS:
                break
            fpath = Path(root) / fname
            if glob_filter:
                import fnmatch as fnm
                if not fnm.fnmatch(fname, glob_filter):
                    continue
            
            # 检查是否为二进制文件 — 小健 2026-06-24 — 小欧 2026-06-24 扩展名已知直接跳过，未知才读内容
            suffix = fpath.suffix.lower()
            if suffix in BINARY_EXTENSIONS:
                skipped_binary_files.append(str(fpath))
                continue
            if suffix and not suffix in TEXT_EXTENSIONS and is_binary_file(str(fpath)):
                skipped_binary_files.append(str(fpath))
                continue
            
            lines = _read_file_safe(fpath)
            if not lines:
                continue
            file_matches = []
            for line_no, line in enumerate(lines, 1):
                if total_matches >= MAX_SEARCH_RESULTS:
                    break
                m = regex.search(line)
                if m:
                    if output_mode == "files_with_matches":
                        results.append({"file": str(fpath)})
                        total_files += 1
                        break
                    match_item = {
                        "file": str(fpath),
                        "line": line_no,
                        "content": line.rstrip('\n\r'),
                    }
                    file_matches.append(match_item)
                    total_matches += 1
            if file_matches:
                total_files += 1
                results.extend(file_matches)

    truncated = _time_mod.monotonic() > deadline or total_matches >= MAX_SEARCH_RESULTS
    return results, total_files, total_matches, truncated, skipped_binary_files


import os


async def grep_file_content(
    pattern: str,
    search_dir: str,
    glob: Optional[str] = None,
    ignore_case: bool = True,
    output_mode: Literal["content", "count", "files_with_matches"] = "content",
) -> Dict[str, Any]:
    """搜索文件内容 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化
    
    参数说明:
        pattern: 正则表达式搜索模式
        search_dir: 搜索目录（必填）
        glob: 文件名过滤模式（如"*.py"）
        ignore_case: 是否忽略大小写
        output_mode: 输出模式
            - content: 返回匹配内容（默认）
            - count: 只返回匹配数量
            - files_with_matches: 只返回文件名列表
    """
    t0 = _time_mod.perf_counter()
    actual_dir = search_dir
    valid_output_modes = ("content", "count", "files_with_matches")
    if output_mode not in valid_output_modes:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"output_mode无效: {output_mode},可选值: {valid_output_modes}")
        return build_error(data={"error_detail": f"output_mode无效: {output_mode},可选值: {valid_output_modes}", "params": {"output_mode": output_mode}}, llm_data=llm_data)
    if not actual_dir or not actual_dir.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail="search_dir不能为空")
        return build_error(data={"error_detail": "search_dir不能为空", "params": {"search_dir": actual_dir}}, llm_data=llm_data)
    is_valid, error_msg = _validate_path(actual_dir)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail="搜索模式不能为空")
        return build_error(data={"error_detail": "搜索模式不能为空", "params": {"pattern": pattern}}, llm_data=llm_data)

    try:
        regex = re_mod.compile(pattern, re_mod.IGNORECASE if ignore_case else 0)
    except re_mod.error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"正则表达式无效: {e}")
        return build_error(data={"error_detail": f"正则表达式无效: {e}", "params": {"pattern": pattern}}, llm_data=llm_data)

    search_path = Path(os.path.expanduser(actual_dir))
    if not search_path.exists():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"搜索目录不存在: {actual_dir}")
        return build_error(data={"error_detail": "搜索目录不存在", "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    if search_path.is_file():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=f"search_dir是一个文件而非目录: {actual_dir}")
        return build_error(data={"error_detail": f"search_dir是一个文件而非目录: {actual_dir}", "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    deadline = _time_mod.monotonic() + TOOL_TIMEOUTS.get("grep_file_content", TOOL_TIMEOUTS["default"]) - 2

    try:
        results, total_files, total_matches, truncated, skipped_binary_files = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, ignore_case, deadline,
            output_mode,
        )
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=actual_dir, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"search_dir": actual_dir}}, llm_data=llm_data)

    if output_mode == "count":
        data = {"total_matches": total_matches, "total_files": total_files, "pattern": pattern}
    elif output_mode == "files_with_matches":
        data = {"files": results, "total_files": total_files, "pattern": pattern}
    else:
        data = {"matches": results, "total_matches": total_matches, "total_files": total_files, "pattern": pattern}
    
    # 添加跳过的二进制文件信息 — 小健 2026-06-24
    if skipped_binary_files:
        data["skipped_binary_files"] = skipped_binary_files[:10]  # 最多返回10个
        data["skipped_binary_count"] = len(skipped_binary_files)
    
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    
    # 如果跳过了二进制文件，添加提示 — 小健 2026-06-24
    binary_hint = ""
    if skipped_binary_files:
        binary_hint = f"（跳过{len(skipped_binary_files)}个二进制文件，如: {Path(skipped_binary_files[0]).name}）"
    
    exec_code = "warning" if (truncated or skipped_binary_files) else "success"
    llm_data = _build_grep_file_content_llm_data(
        exec_code, duration_ms, pattern=pattern, search_dir=actual_dir,
        total_files=total_files, total_matches=total_matches, truncated=truncated,
    )
    
    # 修改summary添加二进制文件提示 — 小健 2026-06-24
    if binary_hint:
        llm_data["summary"] = llm_data["summary"] + binary_hint
        llm_data["status"]["detail"] = f"跳过了{len(skipped_binary_files)}个二进制文件，这些文件不是文本格式，无法进行内容搜索"
    
    if exec_code == "warning":
        return build_warning(data=data, llm_data=llm_data)
    return build_success(data=data, llm_data=llm_data)