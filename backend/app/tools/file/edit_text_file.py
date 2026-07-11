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
from app.services.task.task_context import _current_task_id
from app.db.models.operation_models import OperationType
from app.services.safety import record_operation, execute_with_safety
from app.tools.validate.file_type_checker import check_for_text_tool
from app.tools.validate.file_path_checker import validate_path, OpCategory, validate_str_param
from app.logger import logger
from app.tools.file.file_encoding import get_file_encoding
from app.tools.file.file_state import check_conflict_strict, record_write
from app.tools.file.fuzzy_match import fuzzy_find_replace  # 小欧 2026-07-11

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
    ignore_case: bool, mode: str,
) -> Tuple[str, int, int]:
    """执行替换/插入操作,返回(new_content, count, total_matches) — 小欧 2026-06-22 — 小健 2026-06-24 修复硬编码flags=2 — 小欧 2026-07-05 增加total_matches — 小欧 2026-07-11 replace_all→mode,增加before/after"""
    count = 0
    total_matches = 0

    if mode == "before":
        if ignore_case:
            pattern = re_mod.escape(old_string)
            total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
            if total_matches == 1:
                match = re_mod.search(pattern, content, re_mod.IGNORECASE)
                content = content[:match.start()] + new_string + content[match.start():]
                count = 1
        else:
            total_matches = content.count(old_string)
            if total_matches == 1:
                idx = content.find(old_string)
                content = content[:idx] + new_string + content[idx:]
                count = 1
        return content, count, total_matches

    if mode == "after":
        if ignore_case:
            pattern = re_mod.escape(old_string)
            total_matches = len(re_mod.findall(pattern, content, re_mod.IGNORECASE))
            if total_matches == 1:
                match = re_mod.search(pattern, content, re_mod.IGNORECASE)
                content = content[:match.end()] + new_string + content[match.end():]
                count = 1
        else:
            total_matches = content.count(old_string)
            if total_matches == 1:
                idx = content.find(old_string)
                content = content[:idx + len(old_string)] + new_string + content[idx + len(old_string):]
                count = 1
        return content, count, total_matches

    if mode == "all":
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
        return content, count, total_matches

    # mode == "once"
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


def _safety_structure_loss(original: str, new_content: str) -> str:
    """检测替换是否导致函数/类定义丢失 — 小沈 2026-07-08"""
    orig_funcs = set(re_mod.findall(r'^\s*(?:async\s+)?def\s+(\w+)', original, re_mod.MULTILINE))
    new_funcs  = set(re_mod.findall(r'^\s*(?:async\s+)?def\s+(\w+)', new_content, re_mod.MULTILINE))
    parts = []
    if len(new_funcs) < len(orig_funcs):
        lost = orig_funcs - new_funcs
        if lost:
            parts.append(f"函数: {', '.join(sorted(lost))}")
    orig_classes = set(re_mod.findall(r'^\s*class\s+(\w+)', original, re_mod.MULTILINE))
    new_classes  = set(re_mod.findall(r'^\s*class\s+(\w+)', new_content, re_mod.MULTILINE))
    if len(new_classes) < len(orig_classes):
        lost = orig_classes - new_classes
        if lost:
            parts.append(f"类: {', '.join(sorted(lost))}")
    return "替换将删除以下定义: " + "；".join(parts) if parts else ""


def _safety_short_old(old_string: str, mode: str, total_matches: int) -> str:
    """检测过短old_string批量替换风险 — 小沈 2026-07-08 — 小欧 2026-07-11 replace_all→mode"""
    if mode == "all" and len(old_string) <= 2 and total_matches >= 5:
        return f"old_string仅{len(old_string)}字符，all模式匹配{total_matches}处，请确认"
    return ""


def _build_edit_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", applied: int = 0, total: int = 0, detail: str = "",
    diff: str = "", total_matches: int = 0, mtime_warning: str = "",
    hint: str = "", safety_hint: str = "",
    user_old_string: str = "", user_new_string: str = "",
    user_mode: str = "", user_ignore_case: Optional[bool] = None,
    user_encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """edit_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 增加diff/total_matches/mtime_warning — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-06 diff移入other_data — 小欧 2026-07-06 diff移回metrics — 小欧 2026-07-11 replace_all→mode"""
    _act_params = {"file_path": file_path}
    if user_old_string:
        _act_params["old_string"] = user_old_string[:50]  # 小欧 2026-07-06 100→50，减少返回给LLM的冗余参数
    if user_new_string:
        _act_params["new_string"] = user_new_string[:50]  # 小欧 2026-07-06 100→50，减少返回给LLM的冗余参数
    if user_mode and user_mode != "once":
        _act_params["mode"] = user_mode
    if user_ignore_case is not None:
        _act_params["ignore_case"] = user_ignore_case
    if user_encoding:
        _act_params["encoding"] = user_encoding
    if exec_code == "error":
        return {
            "summary": f"编辑文件{file_path}，失败",
            "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "编辑失败", "code": ERR_FILE_EDIT_FAILED, "detail": detail, "hint": hint if hint else "请检查文件路径和编辑参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _hint_parts = []
    if mtime_warning:
        _hint_parts.append(mtime_warning)
    if safety_hint:
        _hint_parts.append(safety_hint)
    _warning_msg = ""
    if total_matches > applied:
        _remaining = total_matches - applied
        _warning_msg = f"剩余{_remaining}处未修改"
        _hint_parts.append("建议使用 mode='all' 一次替换所有匹配")
    _hint = "；".join(_hint_parts) if _hint_parts else ""
    _exec_code = "warning" if (_warning_msg or mtime_warning or safety_hint) else "success"
    if _exec_code == "warning":
        _summary = f"编辑文件{file_path}，成功,提示说明: 替换 {applied}/{total_matches} 处"
        if _warning_msg:
            _summary += f"，注意: {_warning_msg}"
    else:
        _summary = f"编辑文件{file_path}，成功: 替换 {applied}/{total_matches} 处"
    return {
        "summary": _summary,
        "action": {"tool": "edittext", "tool_zh": "编辑文件", "target": file_path, "params": _act_params},
        "status": {"exec_code": _exec_code, "message": "编辑完成", "code": "", "detail": _warning_msg, "hint": _hint},
        "duration_ms": duration_ms,
        "metrics": {
            "applied": {"value": applied, "text": f"{applied}/{total}处"},
            "total_matches": {"value": total_matches, "text": f"共{total_matches}处"},
        },
        "diff": diff[:500],
    }


async def _precise_replace_in_file(
    file_path: str, old_string: str, new_string: str,
    mode: str = "once", ignore_case: bool = False,
    dry_run: bool = False, encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """精确替换文件中的字符串(返回原始dict,不含build3/llm_data) — 小欧 2026-06-22 — 小欧 2026-07-11 replace_all→mode"""
    if not old_string:
        return {"error_detail": "old_string不能为空"}

    task_id = _current_task_id.get(None)
    if not task_id:
        return {"error_detail": "当前没有活跃任务ID"}

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

        # 编码预检移入 _replace_sync：验完整落盘内容(write_content)，
        # 覆盖 new_string + 原文 errors='replace' 残留的 U+FFFD，且在 open('w') 截断前失败 — 小欧 2026-07-11

        mtime_warning = ""
        conflict_err = check_conflict_strict(file_path)
        if conflict_err:
            return {"error_detail": conflict_err}

        # 无操作跳过（仅replace模式，插入模式即使内容相同也改变文件） — 小欧 2026-07-11
        if old_string == new_string and mode in ("once", "all"):
            total_matches = content.count(old_string) if mode == "all" else (1 if old_string in content else 0)
            return {
                "file_path": str(path),
                "applied_edits": 0, "total_edits": 0,
                "total_matches": total_matches,
                "diff": "", "mtime_warning": mtime_warning, "skipped": True,
            }

        # before/after 模式：new_string 不能为空(插入空内容无意义,否则误报成功) — 小欧 2026-07-11
        if mode in ("before", "after") and new_string == "":
            return {"error_detail": f"mode={mode} 需要非空 new_string（插入内容不能为空）", "old_string": old_string[:50]}

        # before/after 模式：校验唯一匹配 — 小欧 2026-07-11
        if mode in ("before", "after"):
            if ignore_case:
                total_matches = len(re_mod.findall(re_mod.escape(old_string), content, re_mod.IGNORECASE))
            else:
                total_matches = content.count(old_string)
            if total_matches == 0:
                return {"error_detail": f"未找到匹配内容: '{old_string[:80]}'（mode={mode}）", "old_string": old_string[:50]}
            if total_matches > 1:
                return {"error_detail": f"before/after模式要求唯一匹配，old_string在文件中出现{total_matches}次，请提供更多上下文以精确定位", "old_string": old_string[:50]}

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.MODIFY,
            destination_path=path, sequence_number=0,
        )

        replace_result = {}

        def _replace_sync() -> bool:
            new_content, count, total_matches = _apply_replacement(content, old_string, new_string, ignore_case, mode)
            # 模糊回退: mode=once精确匹配失败时尝试escape_normalized — 小欧 2026-07-11
            if count == 0 and mode == "once" and not ignore_case:
                fuzzy_content, fuzzy_count, fuzzy_total, fuzzy_err = fuzzy_find_replace(
                    content, old_string, new_string
                )
                if fuzzy_count > 0:
                    new_content, count, total_matches = fuzzy_content, fuzzy_count, fuzzy_total
            replace_result['count'] = count
            replace_result['total_matches'] = total_matches
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
            sl_warn = _safety_structure_loss(content, new_content)
            so_warn = _safety_short_old(old_string, mode, total_matches)
            if sl_warn or so_warn:
                replace_result['safety_hint'] = ("；".join(filter(None, [sl_warn, so_warn])))[:200]
            write_content = new_content.replace('\n', '\r\n') if _has_crlf else new_content
            # 完整编码预检：验落盘全文,含原文残留U+FFFD,赶在open('w')截断前失败 — 小欧 2026-07-11
            try:
                write_content.encode(used_enc)
            except UnicodeEncodeError as e:
                replace_result['encode_error'] = f"替换后内容含编码 {used_enc} 不支持的字符: {e}"
                return False
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

        # 优先处理编码失败(count!=0但写入被拦),避免误判为"未找到匹配" — 小欧 2026-07-11
        if replace_result.get('encode_error'):
            return {"error_detail": replace_result['encode_error']}

        if not success or count == 0:
            preview = replace_result.get('content_preview', '')
            total_lines = replace_result.get('total_lines', 0)
            if total_lines == 1 and not content.strip():
                return {"error_detail": f"未找到匹配内容: 文件为空", "old_string": old_string[:50]}
            _ed = f"未找到匹配内容: '{old_string[:80]}'。文件共{total_lines}行，前15行:\n{preview}"
            if mode == "once" and count == 0 and new_string and new_string in content:
                _ed += "。提示: new_string 在文件中但 old_string 未找到，可能参数填反"
            return {
                "error_detail": _ed,
                "old_string": old_string[:50],
            }

        return {
            "operation_id": operation_id, "file_path": str(path),
            "applied_edits": count, "total_edits": count,
            "total_matches": replace_result.get("total_matches", count),
            "diff": replace_result.get("diff", ""),
            "mtime_warning": mtime_warning,
            "safety_hint": replace_result.get("safety_hint", ""),
        }

    except Exception as e:
        logger.error(f"edittext failed: {file_path}: {e}")
        return {"error_detail": str(e)}


async def edittext(
    file_path: str,
    old_string: str,
    new_string: str = "",
    mode: str = "once",
    ignore_case: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加ignore_case参数 — 小欧 2026-07-11 replace_all→mode"""
    t0 = _time_mod.perf_counter()

    # mode 有效性检查 — 小欧 2026-07-11
    if mode not in ("once", "all", "before", "after"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"无效mode: '{mode}'，可选值: once, all, before, after", user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)

    if '\x00' in file_path:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="file_path包含空字节", user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)
    if old_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为None", user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)
    if not old_string:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="old_string不能为空字符串", user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)
    if new_string is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="new_string不能为None", user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(data={}, llm_data=llm_data)

    # 文件类型检查 — 北京老陈 2026-07-09
    ft_valid, ft_detail, ft_tool = check_for_text_tool(file_path, check_content=True)
    if not ft_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if ft_tool:
            _hint = f"建议使用{ft_tool}工具"
        elif ft_tool == "":
            _hint = "请检查文件路径和文件名是否正确"
        else:
            _hint = "请选择正确的工具类型"
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=ft_detail, hint=_hint, user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
        return build_error(
            data={"error_detail": ft_detail, "params": {"file_path": file_path}},
            llm_data=llm_data,
        )

    dry_run = False
    result = await _precise_replace_in_file(
        file_path=file_path, old_string=old_string, new_string=new_string,
        mode=mode, ignore_case=ignore_case,
        dry_run=dry_run, encoding=encoding,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    error_detail = result.get("error_detail")
    if error_detail:
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_detail, user_old_string=old_string, user_new_string=new_string, user_mode=mode, user_ignore_case=ignore_case, user_encoding=encoding)
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
        safety_hint=result.get("safety_hint", ""),
        user_old_string=old_string, user_new_string=new_string,
        user_mode=mode, user_ignore_case=ignore_case,
        user_encoding=encoding,
    )
    # ---- observation_formatter route -------------------------------------------
    # branch: #21 fallback (key:val)
    # trigger: 无上述20条分支匹配 — result 含 applied_edits/diff，不命中任何专用分支
    # handler: _format_scalar_data(data) — key | value 单行列表
    # file:    observation_formatter.py:214
    # ------------------------------------------------------------------------------
    # =============================================================================
    # 数据设计三档：
    #   完全成功 (applied == total_matches > 0)  → data={}
    #   部分成功 (applied < total_matches, applied>0) → data={"diff": ...}
    #   跳过/无操作 (skipped 或 applied==0)       → data={}
    # — 小欧 2026-07-06 21:00:00
    # =============================================================================
    _applied = llm_data["metrics"]["applied"]["value"]
    _total_matches = llm_data["metrics"]["total_matches"]["value"]
    _skipped = result.get("skipped", False)
    if _skipped or _applied == 0:
        data = {}
    elif _applied >= _total_matches:
        data = {}
    else:
        data = {"diff": result.get("diff", "")}
    return build_success(data=data, llm_data=llm_data)


# 本地 mtime 缓存已于 2026-07-05 迁移到 file/file_state.py — 小欧