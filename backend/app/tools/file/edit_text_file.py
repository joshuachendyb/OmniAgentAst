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
from app.tools.tool_constants import MAX_READ_SIZE, BINARY_EXTENSIONS
from app.constants import ERR_FILE_EDIT_FAILED, ERR_FILE_REPLACE_FAILED
from app.services.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.utils.logger import logger


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


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _is_binary_file(file_path: str) -> Tuple[bool, str]:
    """检测文件是否为二进制文件 — 小欧 2026-06-22"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        return True, f"文件后缀 '{suffix}' 属于二进制文件类型"
    return False, ""


async def _try_read_file_with_encodings(
    path: Path, preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取 — 小欧 2026-06-22"""
    try:
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = _get_file_encoding(str(path))
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
                if do_detect and '\ufffd' in content:
                    content = None
                    continue
                return content, enc, None
            except Exception:
                continue
        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)


def _apply_replacement(
    content: str, old_string: str, new_string: str,
    ignore_case: bool, replace_all: bool,
) -> Tuple[str, int]:
    """执行替换操作,返回(new_content, count) — 小欧 2026-06-22"""
    count = 0
    if replace_all:
        flags = 0 if not ignore_case else 2  # re.IGNORECASE
        import re as re_mod
        pattern = re_mod.escape(old_string)
        if ignore_case:
            count = len(re_mod.findall(pattern, content, flags))
            content = re_mod.sub(pattern, new_string, content, flags=flags)
        else:
            count = content.count(old_string)
            content = content.replace(old_string, new_string)
    else:
        if ignore_case:
            import re as re_mod
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
    """精确替换文件中的字符串(返回原始dict,不含build3/llm_data) — 小欧 2026-06-22"""
    if not old_string:
        return {"error_detail": "old_string不能为空"}

    task_id = _current_task_id.get(None)
    if not task_id:
        return {"error_detail": "当前没有活跃任务ID"}

    is_binary, reason = _is_binary_file(file_path)
    if is_binary:
        return {"error_detail": reason}

    t0 = _time_mod.perf_counter()
    try:
        is_valid, err = _validate_path(file_path)
        if not is_valid:
            return {"error_detail": err}
        path = Path(file_path)
        if not path.exists():
            return {"error_detail": f"文件不存在: {file_path}"}
        if path.stat().st_size > MAX_READ_SIZE:
            return {"error_detail": f"文件过大({path.stat().st_size}字节)", "file_size": path.stat().st_size}

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
                return False
            with open(path, 'w', encoding=used_enc, newline='') as f:
                f.write(new_content)
            return True

        success = await asyncio.to_thread(
            execute_with_safety, operation_id, operation_func=_replace_sync,
        )

        count = replace_result.get('count', 0)

        if not success or count == 0:
            return {"error_detail": "未找到匹配内容", "old_string": old_string[:50]}

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
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    dry_run = False
    ignore_case = False
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