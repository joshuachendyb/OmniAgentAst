# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小沈 - grep搜索结果上限改用OBS_MAX_DISPLAY_ITEMS，区分"超时"与"达上限"两种截断
# 2026-07-18 - 小沈 - 灰区后缀跳过逻辑改为内容级探测(复用_detect_binary_content),修复日志轮转文件.log.1/.2被误判二进制跳过
# 2026-07-20 - 小欧 - 去除 grep 输入与输出限制: 删 pattern 长度校验/匹配条数上限(head_limit)/达上限标记, 工具返回全部匹配交显示域行×列; context 仅校验非负; 跳过目录名单改用公用 SKIP_DIRS; 文件读取走默认不限制大小
"""
F7: grep_file_content — 搜索文件内容

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import fnmatch as fnm
import os
import re as re_mod
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import TOOL_TIMEOUTS, ERR_FILE_CONTENT_SEARCH_FAILED, BINARY_EXTENSIONS, SKIP_DIRS

from app.tools.validate.file_path_checker import validate_path, OpCategory, hint_for_read_error  # 统一错误提示 - 小欧 2026-07-12
from app.tools.validate.file_type_checker import TEXT_EXTENSIONS, is_binary_file, _detect_binary_content
from app.tools.file.file_encoding import safe_read_lines
from app.logger import logger




# 模块级 ReDoS 检测常量 — 小沈 2026-07-05
_REDOS_PATTERNS = frozenset({
    r"\([^)]*[+*][^)]*\)[+*]",       # (a+)+ 或 (a*)* 嵌套量词
    r"\([^)]*[+*][^)]*\){[0-9,]+}",  # (a+){2,} 量词嵌套
})


class GrepSyncResult(NamedTuple):
    """_grep_files_sync 返回值 — 小沈 2026-07-05 — 小欧 2026-07-07 加truncated_by_deadline"""
    results: List[Dict]
    total_files: int
    total_matches: int
    truncated: bool
    truncated_by_deadline: bool
    skipped_binaries: List[str]


def _build_grep_file_content_llm_data(
    exec_code: str, duration_ms: int,
    pattern: str = "", path: str = "",
    total_files: int = 0, total_matches: int = 0,
    truncated: bool = False, detail: str = "", hint: str = "",
    user_glob: Optional[str] = None, user_ignore_case: Optional[bool] = None,
    truncated_by_deadline: bool = False,
    user_context: Optional[int] = None,
) -> Dict[str, Any]:
    """grep_file_content的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小健 2026-06-23 添加结果数量限制提示 — 小欧 2026-07-07 超时秒数"""
    _timeout_sec = TOOL_TIMEOUTS.get("grep", TOOL_TIMEOUTS["default"])
    _act_params = {"pattern": pattern, "path": path}
    if user_glob:
        _act_params["glob"] = user_glob
    if user_ignore_case is not None:
        _act_params["ignore_case"] = user_ignore_case
    if user_context:
        _act_params["context"] = user_context

    if exec_code == "error":
        return {
            "summary": f"搜索内容'{pattern}'，失败",
            "action": {"tool": "grep", "tool_zh": "内容搜索", "target": pattern, "params": _act_params},
            "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_CONTENT_SEARCH_FAILED, "detail": detail, "hint": hint if hint else "请检查搜索路径和搜索模式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        if truncated:
            _timeout_suffix = f"，超时({_timeout_sec}秒)" if truncated_by_deadline else ""
            summary_suffix = f"（结果被截断，可能不完整）{_timeout_suffix}"
            warning_message = "结果被截断，可能不完整"
            _detail_parts = []
            if truncated_by_deadline:
                _detail_parts.append(f"搜索超时（{_timeout_sec}秒）")
            warning_detail = ("，".join(_detail_parts) + "，仅返回部分结果") if _detail_parts else "仅返回部分结果"
            if truncated_by_deadline:
                warning_hint = f"搜索超时（{_timeout_sec}秒），可缩小搜索范围或增加超时时间"
            else:
                warning_hint = "可排除二进制文件路径或指定文件后缀过滤"
        else:
            summary_suffix = ""
            warning_message = "跳过了部分二进制文件"
            warning_detail = "跳过了部分二进制文件，无法进行内容搜索"
            warning_hint = "可排除二进制文件路径或指定文件后缀过滤"
        return {
            "summary": f"搜索内容'{pattern}'，成功,提示说明: {total_files}个文件{total_matches}行匹配{summary_suffix}",
            "action": {"tool": "grep", "tool_zh": "内容搜索", "target": pattern, "params": _act_params},
            "status": {"exec_code": "warning", "message": warning_message, "code": "", "detail": warning_detail, "hint": warning_hint},
            "duration_ms": duration_ms,
            "metrics": {
                "total_files": {"value": total_files, "text": f"{total_files}个文件"},
                "total_matches": {"value": total_matches, "text": f"{total_matches}行"},
            },
        }
    return {
        "summary": f"搜索内容'{pattern}'，成功: {total_files}个文件{total_matches}行匹配",
        "action": {"tool": "grep", "tool_zh": "内容搜索", "target": pattern, "params": _act_params},
        "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "total_files": {"value": total_files, "text": f"{total_files}个文件"},
            "total_matches": {"value": total_matches, "text": f"{total_matches}行"},
        },
    }


def _grep_files_sync(
    path: Path,
    regex: re_mod.Pattern,
    glob_filter: Optional[str],
    deadline: float,
    context: int = 0,
) -> GrepSyncResult:
    """同步搜索文件内容 — 小欧 2026-06-22 — 小健 2026-06-24 增加二进制文件检测和提示 — 小沈 2026-07-05 接收已编译regex — 小欧 2026-07-11 支持context上下文行 — 小欧 2026-07-20 去 output_mode/only_files(默认content返回带file路径),支持单文件与目录"""
    results = []
    total_matches = 0
    total_files = 0
    skipped_binary_files = []  # 记录跳过的二进制文件
    _deadline_exceeded = False

    def _search_one_file(fpath: Path) -> None:
        nonlocal total_matches, total_files
        # 检查是否为二进制文件 — 小健 2026-06-24 — 小欧 2026-06-24 扩展名已知直接跳过，未知才读内容
        # — 小欧 2026-07-12 灰区后缀与无后缀二进制也计入skipped_binary_files,消除静默跳过无提示
        suffix = fpath.suffix.lower()
        if suffix in BINARY_EXTENSIONS:
            skipped_binary_files.append(str(fpath))
            return
        # 无后缀或未知后缀:内容探测是否二进制(覆盖Makefile/README等无后缀二进制文件)
        if (not suffix or suffix not in TEXT_EXTENSIONS) and is_binary_file(str(fpath)):
            skipped_binary_files.append(str(fpath))
            return
        # 灰区后缀(未知扩展名):复用_detect_binary_content做内容级探测 — 小沈 2026-07-18
        # (仅判断后缀会误判日志轮转文件如 .log.1 等常见文本)
        if suffix and suffix not in TEXT_EXTENSIONS:
            is_bin, _ = _detect_binary_content(fpath)
            if is_bin:
                skipped_binary_files.append(str(fpath))
                return

        lines = safe_read_lines(fpath)
        if not lines:
            return
        file_matched = False
        for line_no, line in enumerate(lines, 1):
            matches_in_line = list(regex.finditer(line))
            if not matches_in_line:
                continue
            matched_texts = [m.group(0) for m in matches_in_line]
            match_item = {
                "file": str(fpath),
                "line": line_no,
                "matched": matched_texts,
                "content": line.rstrip('\n\r'),
            }
            # context上下文行:前后各context行 — 小欧 2026-07-11
            if context > 0:
                lo = max(0, line_no - 1 - context)
                match_item["before"] = [
                    {"line": i + 1, "text": lines[i].rstrip('\n\r')}
                    for i in range(lo, line_no - 1)
                ]
                hi = min(len(lines), line_no + context)
                match_item["after"] = [
                    {"line": i + 1, "text": lines[i].rstrip('\n\r')}
                    for i in range(line_no, hi)
                ]
            results.append(match_item)
            total_matches += len(matched_texts)
            file_matched = True
        if file_matched:
            total_files += 1

    if path.is_file():
        if _time_mod.monotonic() <= deadline:
            _search_one_file(path)
        else:
            _deadline_exceeded = True
    elif path.is_dir():
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if _time_mod.monotonic() > deadline:
                _deadline_exceeded = True
                break
            for fname in files:
                if _time_mod.monotonic() > deadline:
                    _deadline_exceeded = True
                    break
                fpath = Path(root) / fname
                if glob_filter and not fnm.fnmatch(fname, glob_filter):
                    continue
                _search_one_file(fpath)

    truncated = _deadline_exceeded
    return GrepSyncResult(results, total_files, total_matches, truncated, _deadline_exceeded, skipped_binary_files)


def _sort_grep_results_by_mtime(results: List[Dict]) -> None:
    """按文件修改时间降序排序 grep 结果 — 小欧 2026-07-05"""
    def _mtime(item: Dict) -> float:
        try:
            return Path(item["file"]).stat().st_mtime
        except OSError:
            return -1.0
    results.sort(key=_mtime, reverse=True)


async def grep(
    pattern: str,
    path: str,
    glob: Optional[str] = None,
    ignore_case: bool = True,
    context: int = 0,
) -> Dict[str, Any]:
    """搜索文件内容 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化 — 小欧 2026-07-11 新增context上下文行 — 小欧 2026-07-11 search_dir→path(单一路径参数统一命名path) — 小欧 2026-07-20 去 literal/output_mode,仅留90%场景参数(pattern/path/ignore_case/glob/context)
    
    参数说明:
        pattern: 正则表达式搜索模式(Python re 语法); 搜含 . ( ) [ ] 等特殊字符的纯文本请自行转义(如 foo\\.bar)
        path: 搜索文件或目录（必填）
        glob: 文件名过滤模式（如"*.py"，仅对目录递归搜索生效）
        ignore_case: 是否忽略大小写,默认True(等价于 pattern 前加 (?i))
        context: 返回匹配行前后各N行上下文,默认0(仅校验非负)
    """
    t0 = _time_mod.perf_counter()
    # context 仅校验非负(输入大小/长度限制已去除) — 小欧 2026-07-11 — 小欧 2026-07-20 去掉0-10上限
    if context < 0:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=f"context不能为负数: {context}", hint="context 参数不能为负数", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)
    if not path or not path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail="path不能为空", hint="请指定有效的搜索目录", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)
    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail="搜索模式不能为空", hint="请提供搜索关键词", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)

    # ReDoS 检测 — 小沈 2026-07-05 — 小欧 2026-07-20 pattern 恒为正则,始终检测
    for redos_p in _REDOS_PATTERNS:
        if re_mod.search(redos_p, pattern):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=f"正则表达式包含嵌套量词,可能触发ReDoS: {pattern}", hint="正则表达式包含危险嵌套量词，请简化", user_glob=glob, user_ignore_case=ignore_case)
            return build_error(data={}, llm_data=llm_data)


    # pattern 为正则表达式,直接编译(忽略大小写由 ignore_case 控制)
    effective_pattern = pattern
    try:
        regex = re_mod.compile(effective_pattern, re_mod.IGNORECASE if ignore_case else 0)
    except re_mod.error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=f"正则表达式无效: {e}", hint="正则表达式语法错误，请检查并修正", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)

    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在+类型 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    # path 支持文件与目录：文件用 READ_FILE 校验,目录用 LIST_DIR 校验 — 小欧 2026-07-20
    search_path = Path(os.path.expanduser(path))
    if search_path.is_file():
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, str(search_path))
    elif search_path.is_dir():
        is_valid, err, _ = validate_path(OpCategory.LIST_DIR, str(search_path))
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=f"路径不存在或不是文件/目录: {path}", hint="请提供有效的文件或目录路径", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=err, hint="请检查搜索路径", user_glob=glob, user_ignore_case=ignore_case)
        return build_error(data={}, llm_data=llm_data)

    deadline = _time_mod.monotonic() + TOOL_TIMEOUTS.get("grep", TOOL_TIMEOUTS["default"]) - 2

    try:
        gr = await asyncio.to_thread(
            _grep_files_sync, search_path, regex, glob, deadline, context,
        )
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, path=path, detail=str(e), hint=hint_for_read_error(e, Path(path).name), user_glob=glob, user_ignore_case=ignore_case)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)

    # 按 mtime 降序排序 — 小欧 2026-07-05
    if gr.results:
        _sort_grep_results_by_mtime(gr.results)

    # =============================================================================
    # 数据设计：total_matches/total_files 既留在 data 中（供前端/断言读取），
    # 也通过 llm_data.metrics 传入 summary
    # summary 示例: "搜索完成: 匹配5行, 3个文件"
    # — 小欧 2026-07-06 18:46:13 原始设计移除data；小欧 2026-07-12 修正: 重新加回data(count模式此前返回空data)
    # =============================================================================
    data = {"matches": gr.results, "total_matches": gr.total_matches, "total_files": gr.total_files}

    # 添加跳过的二进制文件信息 — 小健 2026-06-24
    if gr.skipped_binaries:
        data["skipped_binary_files"] = gr.skipped_binaries[:10]  # 最多返回10个
        data["skipped_binary_count"] = len(gr.skipped_binaries)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    # 如果跳过了二进制文件，添加提示 — 小健 2026-06-24
    binary_hint = ""
    if gr.skipped_binaries:
        binary_hint = f"（跳过{len(gr.skipped_binaries)}个二进制文件，如: {Path(gr.skipped_binaries[0]).name}）"

    exec_code = "warning" if (gr.truncated or gr.skipped_binaries) else "success"
    llm_data = _build_grep_file_content_llm_data(
        exec_code, duration_ms, pattern=pattern, path=path,
        total_files=gr.total_files, total_matches=gr.total_matches, truncated=gr.truncated,
        user_glob=glob, user_ignore_case=ignore_case,
        truncated_by_deadline=gr.truncated_by_deadline,
        user_context=context,
    )

    # 修改summary添加二进制文件提示 — 小健 2026-06-24
    if binary_hint:
        llm_data["summary"] = llm_data["summary"] + binary_hint
        llm_data["status"]["detail"] = f"跳过了{len(gr.skipped_binaries)}个二进制文件，这些文件不是文本格式，无法进行内容搜索"

    if exec_code == "warning":
        # ---- observation_formatter route -------------------------------------------
        # branch: #9 matches (grep subtype)
        # trigger: "matches" in data → ms[0] 含 "file" 键
        # handler: _format_matches(ms)
        # file:    observation_formatter.py:152-178
        # ------------------------------------------------------------------------------
        return build_warning(data=data, llm_data=llm_data)
    # ---- observation_formatter route -------------------------------------------
    # branch: #9 matches (grep subtype)
    # trigger: "matches" in data → ms[0] 含 "file" 键
    # handler: _format_matches(ms)
    # file:    observation_formatter.py:152-178
    # ------------------------------------------------------------------------------
    return build_success(data=data, llm_data=llm_data)