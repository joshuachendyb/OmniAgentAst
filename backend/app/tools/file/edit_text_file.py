# -*- coding: utf-8 -*-
"""
F4: edittext — 编辑文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import difflib
import re as re_mod
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import MAX_READ_SIZE
from app.tools.tool_constants import ERR_FILE_EDIT_FAILED, ERR_FILE_REPLACE_FAILED
from app.utils.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.tools.file_type_checker import check_for_text_tool
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory, validate_str_param
from app.utils.logger import logger
from app.tools.file.file_encoding import get_file_encoding
from app.tools.file.file_state import check_conflict_strict, record_write

# U+FFFD replacement character threshold for encoding detection — 小欧 2026-06-27 — 小欧 2026-07-05 统一为readtext的>=3 && >3%逻辑
_REPLACEMENT_CHAR_MIN_COUNT = 3
_REPLACEMENT_CHAR_RATIO = 0.03


async def _try_read_file_with_encodings(
    path: Path, preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取 — 小欧 2026-06-22"""
    try:
        preferred_failed = False
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = get_file_encoding(str(path))
            encodings_to_try = []
            if auto and auto.get("data", {}).get("encoding"):
                encodings_to_try.append(auto["data"]["encoding"])
        fallbacks = ["utf-8", "gbk", "gb2312", "utf-8-sig"]
        for enc in fallbacks:
            if enc not in encodings_to_try:
                encodings_to_try.append(enc)
        for enc in encodings_to_try:
            if enc is None:
                continue
            try:
                def _read(e=enc):
                    with open(path, 'r', encoding=e, errors='replace') as f:
                        return f.read()
                content = await asyncio.to_thread(_read)
                if '\ufffd' in content:
                    _repl_count = content.count('\ufffd')
                    if _repl_count >= _REPLACEMENT_CHAR_MIN_COUNT and _repl_count > len(content) * _REPLACEMENT_CHAR_RATIO:
                        content = None
                        continue
                if preferred_failed:
                    logger.warning(f"User-specified encoding '{preferred}' failed for {path}, using '{enc}' instead")
                return content, enc, None
            except Exception:
                if preferred and enc == preferred:
                    preferred_failed = True
                continue
        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)


def _apply_replacement(
    content: str, old_string: str, new_string: str,
    ignore_case: bool, replace_all: bool,
) -> Tuple[str, int, int]:
    """执行替换操作,返回(new_content, count, total_matches) — 小欧 2026-06-22 — 小健 2026-06-24 修复硬编码flags=2 — 小欧 2026-07-05 增加total_matches"""
    count = 0
    total_matches = 0
    if replace_all:
        flags = 0 if not ignore_case else re_mod.IGNORECASE
        pattern = re_mod.escape(old_string)
        if ignore_case:
            total_matches = len(re_mod.findall(pattern, content, flags))
            count = total_matches
            content = re_mod.sub(pattern, lambda m: new_string, content, flags=flags)
        else:
            total_matches = content.count(old_string)
            count = total_matches
            content = content.replace(old_string, new_string)
    else:
        if ignore_case:
            pattern = re_mod.escape(old_string)
            total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
            match = re_mod.search(pattern, content, re_mod.IGNORECASE)
            if match:
                content = content[:match.start()] + new_string + content[match.end():]
                count = 1
        else:
            total_matches = content.count(old_string)
            idx = content.find(old_string)
            if idx >= 0:
                content = content[:idx] + new_string + content[idx + len(old_string):]
                count = 1
    return content, count, total_matches


def _build_edit_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", applied: int = 0, total: int = 0, detail: str = "",
    diff: str = "", total_matches: int = 0, mtime_warning: str = "",
    hint: str = "",
) -> Dict[str, Any]:
    """edit_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 增加diff/total_matches/mtime_warning — 小沈 2026-07-05 新增hint参数"""
    if exec_code == "error":
        return {
            "summary": f"文件编辑失败: {detail}",
            "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "编辑失败", "code": ERR_FILE_EDIT_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和编辑参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _hint_parts = []
    if mtime_warning:
        _hint_parts.append(mtime_warning)
    _warning_msg = ""
    if total_matches > applied:
        _remaining = total_matches - applied
        _warning_msg = f"共{total_matches}处匹配，已修改{applied}处，剩余{_remaining}处"
        _hint_parts.append("建议使用 replace_all=True 一次替换所有匹配")
    _hint = "；".join(_hint_parts) if _hint_parts else ""
    _summary = f"编辑完成: {file_path} ({applied}/{total}处)"
    if _warning_msg:
        _summary += f"，注意: {_warning_msg}"
    _exec_code = "warning" if (_warning_msg or mtime_warning) else "success"
    return {
        "summary": _summary,
        "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": _exec_code, "message": "编辑完成", "code": "", "detail": _warning_msg, "hint": _hint},
        "duration_ms": duration_ms,
        "metrics": {
            "applied": {"value": applied, "text": f"{applied}/{total}处"},
            "total_matches": {"value": total_matches, "text": f"共{total_matches}处"},
            "diff": {"value": diff[:2000] if diff else "", "text": diff[:2000] if diff else ""},
        },
    }


async def _precise_replace_in_file(
    file_path: str, old_string: str, new_string: str,
    replace_all: bool = False, ignore_case: bool = False,
    dry_run: bool = False, encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """精确替换文件中的字符串(返回原始dict,不含build3/llm_data) — 小欧 2026-06-22 — 小健 2026-06-24 使用file_type_checker"""
    if not old_string:
        return {"error_detail": "old_string不能为空"}

    task_id = _current_task_id.get(None)
    if not task_id:
        return {"error_detail": "当前没有活跃任务ID"}

    # 文件类型检查 — 小健 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_text_tool(file_path, check_content=True)
    if not is_valid:
        return {"error_detail": error_detail}

    try:
        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, warn = validate_path(OpCategory.READ_FILE, file_path, content=new_string)
        if not is_valid:
            return {"error_detail": err}
        if warn:
            logger.warning(f"[edittext] {warn}")

        path = Path(file_path).resolve()
        if path.stat().st_size > MAX_READ_SIZE:
            return {"error_detail": f"文件过大({path.stat().st_size}字节)", "file_size": path.stat().st_size}

        # B2 fix: detect CRLF from raw bytes — 小欧 2026-06-27
        _has_crlf = False
        try:
            _raw = path.read_bytes()[:8192]
            _has_crlf = b'\r\n' in _raw
        except Exception:
            pass

        content, used_enc, err_msg = await _try_read_file_with_encodings(path, encoding)
        if err_msg:
            raise ValueError(err_msg)

        mtime_warning = ""
        conflict_err = check_conflict_strict(file_path)
        if conflict_err:
            return {"error_detail": conflict_err}

        # 无操作跳过 — 小欧 2026-07-05 — 小沈 2026-07-05 record_operation移后防孤立记录
        if old_string == new_string:
            return {
                "file_path": str(path),
                "applied_edits": 0, "total_edits": 0,
                "total_matches": content.count(old_string) if replace_all else (1 if old_string in content else 0),
                "diff": "", "mtime_warning": mtime_warning, "skipped": True,
            }

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.MODIFY,
            destination_path=path, sequence_number=0,
        )

        replace_result = {}

        def _replace_sync() -> bool:
            new_content, count, total_matches = _apply_replacement(content, old_string, new_string, ignore_case, replace_all)
            replace_result['count'] = count
            replace_result['total_matches'] = total_matches
            replace_result['used_enc'] = used_enc
            if dry_run:
                return True
            if count == 0:
                lines = content.split('\n')
                preview = '\n'.join(lines[:15])
                replace_result['content_preview'] = preview
                replace_result['total_lines'] = len(lines)
                return False
            replace_result['diff'] = ''.join(difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(path), tofile=str(path),
                n=3,
            ))
            write_content = new_content.replace('\n', '\r\n') if _has_crlf else new_content
            with open(path, 'w', encoding=used_enc, newline='') as f:
                f.write(write_content)
            record_write(file_path)
            return True

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            success = await asyncio.to_thread(execute_with_safety, operation_id, operation_func=_replace_sync)
        else:
            logger.info("Database unavailable, executing edit operation without recording")
            success = await asyncio.to_thread(_replace_sync)

        count = replace_result.get('count', 0)

        if not success or count == 0:
            preview = replace_result.get('content_preview', '')
            total_lines = replace_result.get('total_lines', 0)
            if total_lines == 1 and not content.strip():
                return {"error_detail": f"未找到匹配内容: 文件为空", "old_string": old_string[:50]}
            return {
                "error_detail": f"未找到匹配内容: '{old_string[:80]}'。文件共{total_lines}行，前15行:\n{preview}",
                "old_string": old_string[:50],
            }

        return {
            "operation_id": operation_id, "file_path": str(path),
            "applied_edits": count, "total_edits": count,
            "total_matches": replace_result.get("total_matches", count),
            "diff": replace_result.get("diff", ""),
            "mtime_warning": mtime_warning,
        }

    except Exception as e:
        logger.error(f"edittext failed: {file_path}: {e}")
        return {"error_detail": str(e)}


async def edittext(
    file_path: str,
    old_string: str,
    new_string: str = "",
    replace_all: bool = False,
    ignore_case: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加ignore_case参数"""
    t0 = _time_mod.perf_counter()
    if '\x00' in file_path:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="file_path包含空字节")
        return build_error(data={"error_detail": "file_path包含空字节", "params": {"file_path": file_path}}, llm_data=llm_data)
    if old_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为None")
        return build_error(data={"error_detail": "old_string不能为None", "params": {"file_path": file_path}}, llm_data=llm_data)
    if not old_string.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为空字符串")
        return build_error(data={"error_detail": "old_string不能为空字符串", "params": {"file_path": file_path}}, llm_data=llm_data)
    if new_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="new_string不能为None")
        return build_error(data={"error_detail": "new_string不能为None", "params": {"file_path": file_path}}, llm_data=llm_data)
    dry_run = False
    result = await _precise_replace_in_file(
        file_path=file_path, old_string=old_string, new_string=new_string,
        replace_all=replace_all, ignore_case=ignore_case,
        dry_run=dry_run, encoding=encoding,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    error_detail = result.get("error_detail")
    if error_detail:
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail)
        return build_error(
            data={"error_detail": error_detail, "params": {"file_path": file_path}},
            llm_data=llm_data,
        )
    llm_data = _build_edit_text_file_llm_data(
        "success", duration_ms, file_path=file_path,
        applied=result.get("applied_edits", 0), total=result.get("total_edits", 0),
        diff=result.get("diff", ""),
        total_matches=result.get("total_matches", 0),
        mtime_warning=result.get("mtime_warning", "") or "",
    )
    return build_success(data=result, llm_data=llm_data)


# 本地 mtime 缓存已于 2026-07-05 迁移到 file/file_state.py — 小欧