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
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import MAX_READ_SIZE
from app.tools.tool_constants import ERR_FILE_READ_FAILED
from app.tools.file_type_checker import check_for_text_tool
from app.utils.logger import logger
from app.tools.file.file_encoding import get_file_encoding


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
            encodings_to_try = []
            if auto and auto.get("data", {}).get("encoding"):
                encodings_to_try.append(auto["data"]["encoding"])
        encodings_to_try.extend(["utf-8", "gbk", "gb2312", "utf-8-sig"])

        do_detect = preferred is None

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
) -> Dict[str, Any]:
    """根据参数选择行并构建 _data 字典 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-24 offset超范围返回warning — 小健 2026-06-25 空文件+offset返回warning — 小欧 2026-06-28 新增tail参数
    offset: 起始行号(正数，必须配合limit)
    limit: 读取行数
    tail: 读取尾部N行"""
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

    content = "".join(selected)
    result = {
        "content": content,
        "total_lines": total,
        "line_count": len(selected),
        **params,
    }
    if warning:
        result["warning"] = warning
    return result


def _build_read_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", line_count: int = 0,
    total_lines: int = 0, file_size: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-06-24 增加warning"""
    if exec_code == "error":
        return {
            "summary": f"读取失败: {detail}",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": f"读取失败: {detail}", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": "请检查文件路径是否正确"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"读取 {file_path}，{line_count}行，{file_size}字节。注意: {detail}",
            "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "warning", "message": f"读取成功但有警告: {detail}", "code": "", "detail": detail, "hint": "请检查offset参数是否超出文件范围"},
            "duration_ms": duration_ms,
            "metrics": {
                "lines": {"value": line_count, "text": f"{line_count}行"},
                "total_lines": {"value": total_lines, "text": f"{total_lines}行"},
            },
        }
    return {
        "summary": f"读取 {file_path}，{line_count}行，{file_size}字节",
        "action": {"tool": "readtext", "tool_zh": "读取", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "lines": {"value": line_count, "text": f"{line_count}行"},
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
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail)
            return build_error(data={"error_detail": error_detail, "params": {"file_path": file_path}}, llm_data=llm_data)

        if limit is not None and limit < 1:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"limit必须>=1,当前值: {limit}",
            )
            return build_error(data={"error_detail": f"limit必须>=1", "params": {"limit": limit}}, llm_data=llm_data)

        if tail is not None and tail < 1:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"tail必须>=1,当前值: {tail}",
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
                )
                return build_error(data={"error_detail": f"不支持的编码: {encoding}", "params": {"encoding": encoding}}, llm_data=llm_data)

        if tail is not None:
            if offset is not None or limit is not None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="tail参数不能与offset/limit同时使用",
                )
                return build_error(data={"error_detail": "tail不能与offset/limit同时使用", "params": {"tail": tail, "offset": offset, "limit": limit}}, llm_data=llm_data)

        if offset is not None:
            if offset < 1:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="offset必须>=1,行号从1开始",
                )
                return build_error(data={"error_detail": "offset必须>=1", "params": {"offset": offset}}, llm_data=llm_data)
            
            if limit is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data(
                    "error", duration_ms, file_path=file_path,
                    detail="offset必须配合limit使用,示例: offset=10,limit=20读取第10-29行",
                )
                return build_error(data={"error_detail": "offset必须配合limit使用", "params": {"offset": offset}}, llm_data=llm_data)

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_path": file_path}}, llm_data=llm_data)

        if not path.is_file():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"路径不是文件: {file_path}")
            return build_error(data={"error_detail": "路径不是文件", "params": {"file_path": file_path}}, llm_data=llm_data)

        file_size = path.stat().st_size
        if file_size > MAX_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data(
                "error", duration_ms, file_path=file_path,
                detail=f"文件过大({file_size}字节),请使用offset+limit分段读取",
            )
            return build_error(data={"error_detail": "文件过大", "params": {"file_path": file_path, "file_size": file_size}}, llm_data=llm_data)

        content, used_encoding, error = await _try_read_file_with_encodings(path, encoding)
        if error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error)
            return build_error(data={"error_detail": error, "params": {"file_path": file_path}}, llm_data=llm_data)

        lines = content.splitlines(keepends=True)
        _data = _select_lines(lines, offset, limit, tail)
        _data["encoding"] = used_encoding
        _line_count = _data.get("line_count", 0)
        _total_lines = _data.get("total_lines", 0)
        _warning = _data.pop("warning", None)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

        if _warning:
            llm_data = _build_read_text_file_llm_data(
                "warning", duration_ms, file_path=file_path,
                line_count=_line_count, total_lines=_total_lines, file_size=file_size, detail=_warning,
            )
            return build_warning(data=_data, llm_data=llm_data)

        llm_data = _build_read_text_file_llm_data(
            "success", duration_ms, file_path=file_path,
            line_count=_line_count, total_lines=_total_lines, file_size=file_size,
        )

        return build_success(data=_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"readtext failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_path": file_path}}, llm_data=llm_data)