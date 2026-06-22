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
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


_ENCODING_PRIORITY = ["utf-8", "gbk", "gb2312", "utf-8-sig"]


def _read_file_safe(file_path: Path) -> List[str]:
    """多编码尝试读取文件行 — 小健 2026-05-25 — 小欧 2026-06-22"""
    try:
        size = file_path.stat().st_size
        if size > MAX_SEARCH_FILE_SIZE:
            return []
    except OSError:
        return []
    for enc in _ENCODING_PRIORITY:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


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
            "status": {"exec_code": "warning", "message": "结果被截断，可能不完整", "code": "", "detail": "搜索超时或结果数量达到上限，仅返回部分结果", "hint": "可缩小搜索范围、使用head_limit参数或增加超时时间"},
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
    head_limit: Optional[int], output_mode: str,
    context_lines: int,
) -> Tuple[List[Dict], int, int, bool]:
    """同步搜索文件内容 — 小欧 2026-06-22 — 小健 2026-06-23 新增head_limit/output_mode/context_lines"""
    results = []
    total_matches = 0
    total_files = 0
    flags = re_mod.IGNORECASE if ignore_case else 0
    try:
        regex = re_mod.compile(pattern, flags)
    except re_mod.error as e:
        return [], 0, 0, False

    effective_limit = head_limit if head_limit else MAX_SEARCH_RESULTS

    for root, dirs, files in os.walk(search_dir):
        if time.monotonic() > deadline:
            break
        if total_matches >= effective_limit:
            break
        for fname in files:
            if time.monotonic() > deadline:
                break
            if total_matches >= effective_limit:
                break
            fpath = Path(root) / fname
            if glob_filter:
                import fnmatch as fnm
                if not fnm.fnmatch(fname, glob_filter):
                    continue
            lines = _read_file_safe(fpath)
            if not lines:
                continue
            file_matches = []
            for line_no, line in enumerate(lines, 1):
                if total_matches >= effective_limit:
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
                    if context_lines > 0:
                        start = max(0, line_no - context_lines - 1)
                        end = min(len(lines), line_no + context_lines)
                        context = []
                        for i in range(start, end):
                            prefix = ">>>" if i == line_no - 1 else "   "
                            context.append(f"{prefix}{i+1}: {lines[i].rstrip()}")
                        match_item["context"] = "\n".join(context)
                    file_matches.append(match_item)
                    total_matches += 1
            if file_matches:
                total_files += 1
                results.extend(file_matches)

    truncated = time.monotonic() > deadline or total_matches >= effective_limit
    return results, total_files, total_matches, truncated


import os


async def grep_file_content(
    pattern: str,
    search_dir: Optional[str] = None,
    glob: Optional[str] = None,
    ignore_case: bool = True,
    head_limit: Optional[int] = None,
    output_mode: Literal["content", "count", "files_with_matches"] = "content",
    context_lines: int = 0,
) -> Dict[str, Any]:
    """搜索文件内容 — 小欧 2026-06-22 独立文件 — 小健 2026-06-23 新增head_limit/output_mode/context_lines
    
    参数说明:
        pattern: 正则表达式搜索模式
        search_dir: 搜索目录，默认当前目录
        glob: 文件名过滤模式（如"*.py"）
        ignore_case: 是否忽略大小写
        head_limit: 限制返回结果数量，防止结果过多
        output_mode: 输出模式
            - content: 返回匹配内容（默认）
            - count: 只返回匹配数量
            - files_with_matches: 只返回文件名列表
        context_lines: 显示匹配行前后多少行上下文
    """
    t0 = _time_mod.perf_counter()
    actual_dir = search_dir or "."
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

    deadline = time.monotonic() + TOOL_TIMEOUTS.get("grep_file_content", TOOL_TIMEOUTS["default"]) - 2

    try:
        results, total_files, total_matches, truncated = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, ignore_case, deadline,
            head_limit, output_mode, context_lines,
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
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    exec_code = "warning" if truncated else "success"
    llm_data = _build_grep_file_content_llm_data(
        exec_code, duration_ms, pattern=pattern, search_dir=actual_dir,
        total_files=total_files, total_matches=total_matches, truncated=truncated,
    )
    if exec_code == "warning":
        return build_warning(data=data, llm_data=llm_data)
    return build_success(data=data, llm_data=llm_data)