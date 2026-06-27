# -*- coding: utf-8 -*-
"""
F4: edit_text_file — 编辑文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import MAX_READ_SIZE
from app.constants import ERR_FILE_EDIT_FAILED, ERR_FILE_REPLACE_FAILED
from app.services.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.tools.file_type_checker import check_for_text_tool
from app.tools.validate.tools_file_path_checker import validate_path_for_write
from app.utils.logger import logger

# U+FFFD replacement character threshold for encoding detection — 小欧 2026-06-27
_REPLACEMENT_CHAR_THRESHOLD = 0.05


def _get_file_encoding(file_path: str) -> Dict[str, Any]:
    """内联编码检测，替代已删除的 file_helper.get_file_encoding — 小欧 2026-06-22"""
    import os
    from app.tools.tool_fc_helper import _detect_encoding
    try:
        file_path = os.path.abspath(file_path)
        if not os.path.exists(file_path):
            return {"data": {"encoding": "utf-8", "confidence": 0.5}}
        detected = _detect_encoding(Path(file_path))
        if detected in ("utf-8-sig", "utf-16-le", "utf-16-be", "utf-8"):
            confidence = 1.0 if detected != "utf-8" else 0.95
            return {"data": {"encoding": detected, "confidence": confidence}}
        common_encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'latin-1']
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
        for encoding in common_encodings:
            try:
                raw_data.decode(encoding)
                return {"data": {"encoding": encoding, "confidence": 0.9}}
            except UnicodeDecodeError:
                continue
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}
    except Exception:
        return {"data": {"encoding": "utf-8", "confidence": 0.5}}



async def _try_read_file_with_encodings(
    path: Path, preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取 — 小欧 2026-06-22"""
    try:
        preferred_failed = False
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = _get_file_encoding(str(path))
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
                if '\ufffd' in content and content.count('\ufffd') > len(content) * _REPLACEMENT_CHAR_THRESHOLD:
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
) -> Tuple[str, int]:
    """执行替换操作,返回(new_content, count) — 小欧 2026-06-22 — 小健 2026-06-24 修复硬编码flags=2"""
    count = 0
    import re as re_mod
    if replace_all:
        flags = 0 if not ignore_case else re_mod.IGNORECASE
        pattern = re_mod.escape(old_string)
        if ignore_case:
            count = len(re_mod.findall(pattern, content, flags))
            content = re_mod.sub(pattern, lambda m: new_string, content, flags=flags)
        else:
            count = content.count(old_string)
            content = content.replace(old_string, new_string)
    else:
        if ignore_case:
            pattern = re_mod.escape(old_string)
            match = re_mod.search(pattern, content, re_mod.IGNORECASE)
            if match:
                content = content[:match.start()] + new_string + content[match.end():]
                count = 1
        else:
            idx = content.find(old_string)
            if idx >= 0:
                content = content[:idx] + new_string + content[idx + len(old_string):]
                count = 1
    return content, count


def _build_edit_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", applied: int = 0, total: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """edit_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"文件编辑失败: {detail}",
            "action": {"tool": "edit_text_file", "tool_zh": "编辑文件", "target": file_path, "params": {}},
            "status": {"exec_code": "error", "message": "编辑失败", "code": ERR_FILE_EDIT_FAILED, "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"编辑完成: {file_path} ({applied}/{total}处)",
        "action": {"tool": "edit_text_file", "tool_zh": "编辑文件", "target": file_path, "params": {}},
        "status": {"exec_code": "success", "message": "编辑完成", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "applied": {"value": applied, "text": f"{applied}/{total}处"},
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
        path = Path(file_path).resolve()
        if not path.exists():
            return {"error_detail": f"文件不存在: {file_path}"}
        if path.stat().st_size > MAX_READ_SIZE:
            return {"error_detail": f"文件过大({path.stat().st_size}字节)", "file_size": path.stat().st_size}

        # B2 fix: detect CRLF from raw bytes — 小欧 2026-06-27
        _has_crlf = False
        try:
            _raw = path.read_bytes()[:8192]
            _has_crlf = b'\r\n' in _raw
        except Exception:
            pass

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.MODIFY,
            destination_path=path, sequence_number=0,
        )

        content, used_enc, err_msg = await _try_read_file_with_encodings(path, encoding)
        if err_msg:
            raise ValueError(err_msg)

        replace_result = {}

        def _replace_sync() -> bool:
            new_content, count = _apply_replacement(content, old_string, new_string, ignore_case, replace_all)
            replace_result['count'] = count
            replace_result['used_enc'] = used_enc
            if dry_run:
                return True
            if count == 0:
                lines = content.split('\n')
                preview = '\n'.join(lines[:15])
                replace_result['content_preview'] = preview
                replace_result['total_lines'] = len(lines)
                return False
            write_content = new_content.replace('\n', '\r\n') if _has_crlf else new_content
            with open(path, 'w', encoding=used_enc, newline='') as f:
                f.write(write_content)
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
        }

    except Exception as e:
        logger.error(f"edit_text_file failed: {file_path}: {e}")
        return {"error_detail": str(e)}


async def edit_text_file(
    file_path: str,
    old_string: str,
    new_string: str = "",
    replace_all: bool = False,
    ignore_case: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加ignore_case参数"""
    t0 = _time_mod.perf_counter()
    is_valid, error_msg, warning_msg = validate_path_for_write(file_path, new_string, False)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"file_path": file_path}}, llm_data=llm_data)
    if warning_msg:
        logger.warning(warning_msg)

    if not file_path or not file_path.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=str(file_path), detail="file_path不能为空")
        return build_error(data={"error_detail": "file_path不能为空", "params": {"file_path": file_path}}, llm_data=llm_data)
    if '\x00' in file_path:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="file_path包含空字节")
        return build_error(data={"error_detail": "file_path包含空字节", "params": {"file_path": file_path}}, llm_data=llm_data)
    if old_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为None")
        return build_error(data={"error_detail": "old_string不能为None", "params": {"file_path": file_path}}, llm_data=llm_data)
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
    )
    return build_success(data=result, llm_data=llm_data)