# -*- coding: utf-8 -*-
"""
F1: readtext — 读取文本文件

从file_tools.py拆分而来，按工具分类聚合设计 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import difflib
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import MAX_READ_SIZE
from app.tools.tool_constants import ERR_FILE_READ_FAILED
from app.tools.file_type_checker import check_for_text_tool
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.text_utils import add_line_numbers
from app.utils.logger import logger
from app.tools.file.file_encoding import get_file_encoding
from app.tools.file.file_state import record_read


def _find_similar_files(file_path: str, max_suggestions: int = 3) -> str:
    """文件不存在时，寻找同目录下的近似文件名 — 小欧 2026-07-05 — 小欧 2026-07-05 cutoff 0.5→0.6"""
    path = Path(file_path)
    parent = path.parent
    if not parent.exists():
        return ""
    target = path.name
    candidates = [p.name for p in parent.iterdir() if p.is_file()]
    if not candidates:
        candidates = [p.name for p in parent.iterdir()]
    matches = difflib.get_close_matches(target, candidates, n=max_suggestions, cutoff=0.6)
    if not matches:
        return ""
    return ", ".join(matches)


def _looks_like_mojibake(content: str, file_path: str = "") -> bool:
    """检测内容是否可能是编码错误造成的乱码 — 小欧 2026-06-30
    GBK字节被误读为UTF-8时，内容中CJK字符极少、Latin-1补充字符极多
    北京老陈 2026-06-30: 文件路径或内容中无中文时不检测，避免误判法文/德文"""
    if not content or len(content) < 10:
        return False
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in file_path)
    has_cjk = has_cjk or any('\u4e00' <= c <= '\u9fff' for c in content[:100])
    if not has_cjk:
        return False
    total = len(content)
    cjk = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    latin1_supp = sum(1 for c in content if '\u0080' <= c <= '\u00ff')
    if cjk / total < 0.05 and latin1_supp / total > 0.30:
        return True
    return False


async def _try_read_file_with_encodings(
    path: Path,
    preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取,返回 (content, used_encoding, error) — 小沈 2026-05-25 — 小欧 2026-06-22"""
    try:
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = get_file_encoding(str(path))
            encodings_to_try = ["utf-8", "gbk", "gb2312", "utf-8-sig"]
            if auto and auto.get("data", {}).get("encoding"):
                enc = auto["data"]["encoding"]
                if enc not in encodings_to_try:
                    encodings_to_try.insert(0, enc)

        for enc in encodings_to_try:
            if enc is None:
                continue
            try:
                def _read(e=enc):
                    with open(path, 'r', encoding=e, errors='replace') as f:
                        return f.read()
                content = await asyncio.to_thread(_read)
                
                # 用户指定了编码，直接返回（用户负责）
                if preferred:
                    return content, enc, None
                
                # 自动检测模式：检查是否有编码错误的标志
                # �是替换字符，出现说明有无法解码的字节
                # 但�也是合法Unicode字符，文件可能真的包含它
                # 判断标准：
                # 1. �数量 >= 3 且占比 > 3% → 编码错误
                # 2. 否则 → 接受（可能是合法字符）
                if '\ufffd' in content:
                    replacement_count = content.count('\ufffd')
                    replacement_ratio = replacement_count / max(len(content), 1)
                    # �数量较多且占比高，认为是编码错误
                    if replacement_count >= 3 and replacement_ratio > 0.03:
                        continue  # 编码不对，尝试下一个

                if _looks_like_mojibake(content, str(path)):
                    continue

                return content, enc, None
            except Exception:
                continue
            

        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)


def _select_lines(
    lines: list,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    tail: Optional[int] = None,
    max_line_length: Optional[int] = 2000,
) -> Dict[str, Any]:
    """根据参数选择行并构建 _data 字典 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-24 offset超范围返回warning — 小健 2026-06-25 空文件+offset返回warning — 小欧 2026-06-28 新增tail参数 — 小欧 2026-07-05 新增长行截断
    offset: 起始行号(正数，必须配合limit)
    limit: 读取行数
    tail: 读取尾部N行
    max_line_length: 单行最大字符数，超长截断(默认2000)"""
    total = len(lines)
    params = {}
    warning = None

    if tail is not None:
        if total == 0:
            warning = f"空文件无法使用tail参数(文件共0行)"
            selected = []
            n = 0
            params = {"tail": tail, "start_line": 0, "end_line": 0}
        else:
            start_idx = max(0, total - tail)
            selected = lines[start_idx:]
            n = len(selected)
            params = {
                "tail": tail,
                "start_line": start_idx + 1,
                "end_line": total,
            }
    elif offset is not None:
        if total == 0:
            warning = f"空文件无法使用offset参数(文件共0行)"
            selected = []
            n = 0
            params.update({
                "offset": offset, "limit": limit,
                "start_line": 0,
                "end_line": 0,
            })
        else:
            start_idx = offset - 1
            if start_idx >= total:
                warning = f"offset={offset}超出文件范围(共{total}行),返回空内容"
            selected = lines[start_idx:start_idx + limit]
            n = len(selected)
            params.update({
                "offset": offset, "limit": limit,
                "start_line": start_idx + 1 if n > 0 else 0,
                "end_line": start_idx + n if n > 0 else 0,
            })
    elif limit is not None:
        selected = lines[:limit]
        n = len(selected)
        params = {
            "offset": None,
            "limit": limit,
            "start_line": 1,
            "end_line": n,
        }
    else:
        selected = lines

    # 长行截断 — 小欧 2026-07-05 — 小欧 2026-07-05 保留原行结尾
    truncated_count = 0
    if max_line_length is not None and max_line_length > 0:
        for i, line in enumerate(selected):
            if len(line) > max_line_length:
                suffix = f"... [截断, 原长{len(line)}字符]"
                if line.endswith('\n'):
                    suffix += '\n'
                selected[i] = line[:max_line_length] + suffix
                truncated_count += 1
    if truncated_count:
        result_extra = {"truncated_lines": truncated_count}
    else:
        result_extra = {}

    content = "".join(selected)
    result = {
        "content": content,
        "total_lines": total,
        "line_count": len(selected),
        **params,
        **result_extra,
    }
    if warning:
        result["warning"] = warning
    return result


def _build_read_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", start_line: int = 1, line_count: int = 0,
    total_lines: int = 0, file_size: int = 0, detail: str = "",
    hint: str = "", encoding_name: str = "",
    user_offset: Optional[int] = None, user_limit: Optional[int] = None,
    user_tail: Optional[int] = None, user_encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """read_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-06-24 增加warning — 小沈 2026-07-05 success显示读取行范围"""
    _act_params = {"file_path": file_path}
    if user_offset is not None:
        _act_params["offset"] = user_offset
    if user_limit is not None:
        _act_params["limit"] = user_limit
    if user_tail is not None:
        _act_params["tail"] = user_tail
    if user_encoding:
        _act_params["encoding"] = user_encoding
    if exec_code == "error":
        return {
            "summary": f"读取失败: {file_path}",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "读取失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和参数是否正确"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"读取 {file_path}，{line_count}行，{file_size}字节。注意: {detail}",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
            "status": {"exec_code": "warning", "message": f"读取成功但有警告: {detail}", "code": "", "detail": detail, "hint": hint if hint else "请检查offset参数是否超出文件范围"},
            "duration_ms": duration_ms,
            "metrics": {
                "lines": {"value": line_count, "text": f"{line_count}行"},
                "total_lines": {"value": total_lines, "text": f"{total_lines}行"},
                "bytes": {"value": file_size, "text": f"{file_size}字节"},
            },
        }
    end_line = start_line + line_count - 1
    if line_count == 0:
        msg = f"文件为空" if not encoding_name else f"文件为空,编码:{encoding_name}"
        hint_text = ""
    elif line_count < total_lines:
        enc = f",编码:{encoding_name}" if encoding_name else ""
        msg = f"读取成功:第{start_line}-{end_line}行,共{total_lines}行{enc}"
        hint_text = "可使用offset+limit继续读取后续内容"
    else:
        enc = f",编码:{encoding_name}" if encoding_name else ""
        msg = f"读取成功:第{start_line}-{end_line}行,共{total_lines}行{enc}"
        hint_text = ""
    return {
        "summary": f"读取 {file_path}，{line_count}行，{file_size}字节",
        "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": _act_params},
        "status": {"exec_code": "success", "message": msg, "code": "", "detail": "", "hint": hint_text},
        "duration_ms": duration_ms,
        "metrics": {
            "lines": {"value": line_count, "text": f"{line_count}行"},
            "total_lines": {"value": total_lines, "text": f"{total_lines}行"},
            "bytes": {"value": file_size, "text": f"{file_size}字节"},
        },
    }


async def readtext(
    file_path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    tail: Optional[int] = None,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 增加文件类型前置检查 — 小欧 2026-06-28 新增tail参数替代offset负数
    offset: 起始行号(正数，必须配合limit)
    limit: 读取行数
    tail: 读取尾部N行（不能与offset/limit同时使用）"""
    t0 = _time_mod.perf_counter()
    try:
        # 文件类型前置检查 — 小健 2026-06-24
        is_valid, error_detail, suggested_tool = check_for_text_tool(file_path, check_content=True)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            hint = f"请使用{suggested_tool}工具" if suggested_tool else "文件类型不匹配,请使用其他工具"
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, hint=hint, user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
            return build_error(data={"error_detail": error_detail, "params": {"file_path": file_path}}, llm_data=llm_data)

        if limit is not None and limit < 1:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"limit必须>=1,当前值: {limit}",
                hint="limit参数必须>=1",
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_error(data={"error_detail": f"limit必须>=1", "params": {"limit": limit}}, llm_data=llm_data)

        if tail is not None and tail < 1:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"tail必须>=1,当前值: {tail}",
                hint="tail参数必须>=1",
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_error(data={"error_detail": f"tail必须>=1", "params": {"tail": tail}}, llm_data=llm_data)

        if encoding is not None:
            try:
                "".encode(encoding)
            except LookupError:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail=f"不支持的编码: {encoding}",
                    hint="请使用正确的编码名称,如utf-8/gbk",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={"error_detail": f"不支持的编码: {encoding}", "params": {"encoding": encoding}}, llm_data=llm_data)

        if tail is not None:
            if offset is not None or limit is not None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="tail参数不能与offset/limit同时使用",
                    hint="tail与offset/limit参数互斥,请选择其一",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={"error_detail": "tail不能与offset/limit同时使用", "params": {"tail": tail, "offset": offset, "limit": limit}}, llm_data=llm_data)

        if offset is not None:
            if offset < 1:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="offset必须>=1,行号从1开始",
                    hint="offset行号从1开始",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={"error_detail": "offset必须>=1", "params": {"offset": offset}}, llm_data=llm_data)
            
            if limit is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="offset必须配合limit使用,示例: offset=10,limit=20读取第10-29行",
                    hint="请提供limit参数配合offset",
                    user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
                )
                return build_error(data={"error_detail": "offset必须配合limit使用", "params": {"offset": offset}}, llm_data=llm_data)

        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, file_path)
        if not is_valid:
            suggestion = _find_similar_files(file_path)
            if suggestion:
                err += f"。您是否要找: {suggestion}"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=err, hint="请检查文件路径是否正确", user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
            return build_error(data={"error_detail": err, "params": {"file_path": file_path}}, llm_data=llm_data)

        path = Path(file_path)

        file_size = path.stat().st_size
        if file_size > MAX_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"文件过大({file_size}字节),请使用offset+limit分段读取",
                hint="请用offset+limit分段读取",
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_error(data={"error_detail": "文件过大", "params": {"file_path": file_path, "file_size": file_size}}, llm_data=llm_data)

        content, used_encoding, error = await _try_read_file_with_encodings(path, encoding)
        if error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error, hint=f"文件编码无法识别，请尝试指定 encoding 参数", user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
            return build_error(data={"error_detail": error, "params": {"file_path": file_path}}, llm_data=llm_data)

        lines = content.splitlines(keepends=True)
        _data = _select_lines(lines, offset, limit, tail)
        _data["encoding"] = used_encoding
        _line_count = _data.get("line_count", 0)
        _total_lines = _data.get("total_lines", 0)
        _warning = _data.pop("warning", None)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

        if _warning:
            warning_hint = ""
            if "空文件" in _warning:
                warning_hint = "文件为空,无需使用行选择参数"
            llm_data = _build_read_text_file_llm_data(
                "warning", duration_ms, file_path=file_path,
                line_count=_line_count, total_lines=_total_lines, file_size=file_size, detail=_warning,
                hint=warning_hint,
                user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
            )
            return build_warning(data=_data, llm_data=llm_data)

        line_offset = _data.get("start_line", 1)

        llm_data = _build_read_text_file_llm_data(
            "success", duration_ms, file_path=file_path,
            start_line=line_offset, line_count=_line_count,
            total_lines=_total_lines, file_size=file_size,
            encoding_name=used_encoding or "",
            user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding,
        )
        raw = _data.get("content", "")
        if raw:
            _data["content"] = f"<file>\n{add_line_numbers(raw, offset=line_offset)}\n</file>"

        record_read(file_path, content)

        # ---- observation_formatter route -------------------------------------------
        # branch: #2 raw str
        # trigger: "content" in data and isinstance(data["content"], str)
        # handler: inline — 直接返回 data["content"], OBS_MAX_STRING_LENGTH 截断
        # file:    observation_formatter.py:117-122
        # ------------------------------------------------------------------------------
        return build_success(data=_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"readtext failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint="请检查文件路径和权限", user_offset=offset, user_limit=limit, user_tail=tail, user_encoding=encoding)
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)