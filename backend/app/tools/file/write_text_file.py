# -*- coding: utf-8 -*-
"""
F2: writetext — 写文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import difflib
import json
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning


def _build_content_preview(content: str) -> str:
    """文首50 + 文末50 预览 — 小沈 2026-07-08"""
    if len(content) <= 100:
        return content
    return f"文首(50字符):{content[:50]}\n...(中间省略)...\n文末(50字符):{content[-50:]}"
from app.tools.tool_constants import ERR_FILE_WRITE_FAILED
from app.utils.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType

from app.tools.validate.file_path_checker import validate_path, OpCategory
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.tools.validate.file_type_checker import check_for_text_tool
from app.tools.validate.file_safety_checker import check_content_safety
from app.utils.logger import logger
from app.tools.file.file_encoding import get_file_encoding
from app.tools.file.file_state import record_write, check_conflict, is_unchanged


def _detect_file_encoding_for_write(file_path: str, append: bool) -> str:
    """统一编码检测 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-30 抽公用"""
    if not append:
        return "utf-8"
    path = Path(file_path)
    if not (path.exists() and path.is_file()):
        return "utf-8"
    try:
        result = get_file_encoding(str(path))
        if result and result.get("data", {}).get("encoding"):
            return result["data"]["encoding"]
    except Exception:
        logger.warning(f"[writetext] 编码检测失败: {file_path}")
    return "utf-8"


def _write_file_atomic(content: str, path: Path, encoding: str,
                        append: bool, create_parents: bool) -> Tuple[bool, str]:
    """原子写入文件 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-24 返回具体错误信息"""
    try:
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        mode = 'a' if append else 'w'
        with open(path, mode, encoding=encoding, newline='') as f:
            f.write(content)
        return True, ""
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        error_msg = f"编码错误: {e}"
        logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
        return False, error_msg
    except LookupError as e:
        error_msg = f"未知编码: {e}"
        logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
        return False, error_msg
    except TypeError as e:
        error_msg = f"内容类型错误: {e}"
        logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
        return False, error_msg
    except OSError as e:
        error_msg = f"文件系统错误: {e}"
        logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
        return False, error_msg
    except Exception as e:
        error_msg = f"写入异常: {e}"
        logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
        return False, error_msg


def _check_write_safety(file_path: str, content: str,
                         encoding: Optional[str] = None,
                         append: bool = False) -> Tuple[Optional[str], str]:
    """写入前安全检查 — 委托到统一函数 check_content_safety
    append时指定encoding会导致编码混乱：
    - 原文件GBK + 追加UTF-8 = 混合编码文件（损坏）
    - 正确做法：append时不指定encoding，自动检测原文件编码
    北京老陈 2026-07-09
    """
    return check_content_safety(content, "text", encoding=encoding, append=append)


def _build_write_text_file_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", bytes_written: int = 0, detail: str = "",
    hint: str = "", mtime_warning: str = "",
    user_encoding: Optional[str] = None, user_append: Optional[bool] = None,
) -> Dict[str, Any]:
    """write_text_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-06-24 增加warning — 小欧 2026-07-05 增加mtime_warning"""
    _act_params = {"file_path": file_path}
    if user_encoding:
        _act_params["encoding"] = user_encoding
    if user_append is not None:
        _act_params["append"] = user_append
    if exec_code == "error":
        return {
            "summary": f"写入文件{file_path}，失败",
            "action": {"tool": "writetext", "tool_zh": "写入", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "写入失败", "code": ERR_FILE_WRITE_FAILED, "detail": detail, "hint": hint if hint else "请检查路径和写入权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning" or bool(mtime_warning):
        if mtime_warning:
            hint = ("；".join([hint, mtime_warning]) if hint else mtime_warning)
        return {
            "summary": f"写入文件{file_path}，成功,提示说明: {detail or mtime_warning}，{bytes_written}字节",
            "action": {"tool": "writetext", "tool_zh": "写入", "target": file_path, "params": _act_params},
            "status": {"exec_code": "warning", "message": f"写入成功但有警告: {detail or mtime_warning}", "code": "", "detail": detail or mtime_warning, "hint": hint or "请确认编码是否正确"},
            "duration_ms": duration_ms,
            "metrics": {
                "bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"},
            },
        }
    return {
        "summary": f"写入文件 {file_path}，成功，共 {bytes_written} 字节",
        "action": {"tool": "writetext", "tool_zh": "写入", "target": file_path, "params": _act_params},
        "status": {"exec_code": "success", "message": "写入成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"},
        },
    }


async def writetext(
    file_path: str,
    content: str,
    encoding: Optional[str] = None,
    append: bool = False,
) -> Dict[str, Any]:
    """写入文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    # content验证+类型转换(dict/list→json)统一在_check_write_safety处理 — 小欧 2026-07-08
    # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.WRITE, file_path, content=content, append=append)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=err, hint="请检查文件路径是否正确", user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)

    create_parents = True

    # 文件类型检查 — 北京老陈 2026-07-09
    ft_valid, ft_detail, ft_tool = check_for_text_tool(file_path, check_content=False, allow_create=True, op_category=OpCategory.WRITE)
    if not ft_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if ft_tool:
            _hint = f"建议使用{ft_tool}工具"
        elif ft_tool == "":
            _hint = "请检查文件路径和文件名是否正确"
        else:
            _hint = "请选择正确的工具类型"
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=ft_detail, hint=_hint, user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)

    error, checked_content = _check_write_safety(file_path, content, encoding, append)
    if error:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error, hint="请检查文件写入安全限制", user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)

    encoding = encoding or _detect_file_encoding_for_write(file_path, append)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail="当前没有活跃任务ID", hint="系统内部错误，请重试", user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)

    path = Path(file_path)

    # mtime 冲突检查 — 小欧 2026-07-05
    conflict_warning = check_conflict(file_path)
    if conflict_warning:
        logger.warning(f"[writetext] {conflict_warning}")

    # 无操作跳过 + 预读旧内容供 diff — 小欧 2026-07-05
    old_content = None
    if not append and path.exists():
        try:
            old_raw = path.read_text(encoding=encoding)
            old_content = old_raw
            if is_unchanged(file_path, checked_content):
                record_write(file_path)  # 更新mtime缓存 — 小欧 2026-07-05
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_write_text_file_llm_data(
                    "success", duration_ms, file_path=str(path),
                    bytes_written=0, detail="内容未变化，跳过写入",
                    mtime_warning=conflict_warning or "",
                    user_encoding=encoding, user_append=append,
                )
                llm_data["metrics"]["diff"] = {"value": "(无变更)", "text": "内容相同，无操作"}
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — skipped path
                # trigger: 无上述20条分支匹配
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data={"content_preview": _build_content_preview(checked_content)}, llm_data=llm_data)
        except Exception:
            old_content = None

    encoding_warning = None
    if append and path.exists() and path.is_file():
        original_encoding = _detect_file_encoding_for_write(file_path, True)
        if encoding != original_encoding:
            encoding_warning = f"文件原始编码为'{original_encoding}',当前使用'{encoding}'写入,可能导致文件编码混乱"

    try:
        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.CREATE,
            destination_path=path,
            sequence_number=0,
        )

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            # 数据库可用，使用execute_with_safety
            def _do_write():
                return execute_with_safety(operation_id, lambda: _write_file_atomic(checked_content, path, encoding, append, create_parents))
            write_result = await asyncio.to_thread(_do_write)
        else:
            # 数据库不可用，直接执行文件操作
            logger.info("Database unavailable, executing file operation without recording")
            def _do_write_direct():
                return _write_file_atomic(checked_content, path, encoding, append, create_parents)
            write_result = await asyncio.to_thread(_do_write_direct)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if isinstance(write_result, tuple):
            success, error_detail = write_result
        else:
            success, error_detail = bool(write_result), ""

        if success:
            # diff 生成 — 小欧 2026-07-05
            diff_text = ""
            if old_content is not None:
                try:
                    new_content = checked_content
                    if old_content != new_content:
                        diff_text = "".join(difflib.unified_diff(
                            old_content.splitlines(keepends=True),
                            new_content.splitlines(keepends=True),
                            fromfile=str(path), tofile=str(path), n=3,
                        ))[:2000]
                except Exception:
                    pass

            record_write(file_path)

            try:
                bytes_written = len(checked_content.encode(encoding))
            except (UnicodeEncodeError, LookupError):
                bytes_written = len(checked_content.encode("utf-8"))
            if encoding_warning:
                llm_data = _build_write_text_file_llm_data("warning", duration_ms, file_path=str(path), bytes_written=bytes_written, detail=encoding_warning, mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append)
                if diff_text:
                    llm_data["metrics"]["diff"] = {"value": diff_text, "text": diff_text}
                return build_warning(
                    data={"content_preview": _build_content_preview(checked_content)},
                    llm_data=llm_data,
                )
            llm_data = _build_write_text_file_llm_data("success", duration_ms, file_path=str(path), bytes_written=bytes_written, mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append)
            if diff_text:
                llm_data["metrics"]["diff"] = {"value": diff_text, "text": diff_text}
            # ---- observation_formatter route -------------------------------------------
            # branch: #21 fallback (key:val)
            # trigger: 无上述20条分支匹配 — operation_id 不命中任何专用分支
            # handler: _format_scalar_data(data) — key | value 单行列表
            # file:    observation_formatter.py:214
            # ------------------------------------------------------------------------------
            return build_success(
                data={"content_preview": _build_content_preview(checked_content)},
                llm_data=llm_data,
            )
            llm_data = _build_write_text_file_llm_data("success", duration_ms, file_path=str(path), bytes_written=bytes_written, mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append)
            if diff_text:
                llm_data["metrics"]["diff"] = {"value": diff_text, "text": diff_text}
            # ---- observation_formatter route -------------------------------------------
            # branch: #21 fallback (key:val)
            # trigger: 无上述20条分支匹配 — operation_id 不命中任何专用分支
            # handler: _format_scalar_data(data) — key | value 单行列表
            # file:    observation_formatter.py:214
            # ------------------------------------------------------------------------------
            return build_success(
                data={"content_preview": _build_content_preview(checked_content)},
                llm_data=llm_data,
            )
        else:
            detail = error_detail or "写入文件失败"
            llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=detail, hint="请检查文件路径和写入权限", user_encoding=encoding, user_append=append)
            return build_error(data={}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint="未知错误，请重试", user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)