# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-17 - 小欧 - 早期encoding校验: writetext()中encoding确定后立即用codecs.lookup()校验，替代等open()才报错
# 2026-07-20 - 小欧 - 章14 尝试将 content_preview 改为完整内容(3.7/6.4); 用户裁定 write 工具不需回显全文, 恢复 _build_content_preview 文首50+文末50 Tool 层预览; schema 入参 max_length 仍依3.6去除
# 2026-07-20 - 小欧 - 门限复查: 删 diff 生成处 [:2000] 静默截断(违3.7 Tool零截断); diff 由 llm_data["metrics"]["diff"] 改放 llm_data 顶层 "diff", 交 observation_formatter #544 行×列收口+两态呈现; data 仅留 content_preview(#23), 严禁与 llm_data 段重复显示
# 2026-07-25 - 小欧 - 截断治理: content[:50]/[-50:] → WRITETEXT_INER_PREVIEW_CHARS 命名常量
# 2026-07-29 - 小欧 - hint优化: 语法错误hint从死的"请修复语法错误后重试"改为动态"Python语法错误(行N)，建议:xxxx"; metrics新增error_line+suggestion
# 2026-07-29 - 小欧 - PYEOF容错: Python文件末尾整行PYEOF自动剥离(heredoc泄漏), 前置在validate_syntax之前; metrics新增auto_removed_pyeof
# 2026-07-30 - 小沈 - except:pass补日志: diff生成失败改为logger.debug记录
# 2026-08-06 - 小欧 - 追加补换行: append且原文件非空且末尾非换行符时自动补换行, 避免追加内容与末行合并(仿edit_text_file末行处理)
# 2026-08-07 - 小欧 - BUG-05修复: 编码无法编码(GBK+emoji/ascii+中文)时自动降级utf-8重写/追加, 不再崩溃
#   【病根】append模式下_detect_file_encoding_for_write返回原文件编码(如gbk), user无法指定编码(file_safety_checker:126-127阻止), GBK无法编码emoji → 无fallback → 崩溃(日志09:11:34)
#   【改法】_write_file_atomic 捕获 UnicodeEncodeError/UnicodeDecodeError 后, 非utf-8编码降级以utf-8整写(append先读回原内容防重复); utf-8也失败则返回错误
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1下沉: task_id ContextVar 迁至 app.tools.context, _current_task_id import 由 app.services.task.task_context 改 app.tools.context,
#   消除 tools 层对 app.services 越层依赖(守护测试 tools 禁 app.services 规则), 行为零变化(同一 ContextVar 对象)
# 2026-08-12 - 小欧 - A1后半面(4.1.7定案): 删除 from app.safety import record_operation/execute_with_safety,
#   改为 get_current_hooks() 取安全 hooks, 消除 tools→safety 越层; task_id 仍 _current_task_id.get()
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): get_current_hooks() 改 get_current_hooks_or_noop() 兜底返回 NoOpHooks,
#   消除入口未注入时 _hooks.record_operation() NPE(如测试直接调工具函数), 行为零退化(生产路径已注入不变)
# 2026-08-13 - 小欧 - 三堂会审修复#5: _write_file_atomic 的 open(读尾字节/写/降级重写)/mkdir/stat 全链
#   to_win_long_path 长路径化(仅NT生效), 深嵌套目标不再 WinError 206; 编码降级回退分支同步;
#   主函数/编码探测的 exists/is_file/read_text 探测同步长路径化(超长路径不误判"文件不存在")
# 2026-08-21 - 小欧 - 11.6.1 exemplar: success分支调 with_artifact_file 声明产出物
"""
F2: writetext — 写文本文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import codecs
import difflib
import os
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error, build_warning, with_artifact_file  # 2026-08-21 小欧 11.6.1: 产出物声明
from app.tools.tool_constants import WRITETEXT_INER_PREVIEW_CHARS


def _build_content_preview(content: str) -> str:
    """文首+文末预览 — 小沈 2026-07-08；2026-07-20 用户裁定恢复此 Tool 层预览(write 工具不需回显全文)"""
    _pc = WRITETEXT_INER_PREVIEW_CHARS
    if len(content) <= _pc * 2:
        return content
    return f"文首({_pc}字符):{content[:_pc]}\n...(中间省略)...\n文末({_pc}字符):{content[-_pc:]}"
from app.tools.tool_constants import ERR_FILE_WRITE_FAILED
from app.tools.context import _current_task_id, get_current_hooks_or_noop  # A1: ContextVar hooks — 小欧 2026-08-12; BUG-3修复: 改用 _or_noop 兜底 — 小沈 2026-08-13
from app.db.models.operation_models import OperationType

from app.tools.validate.file_path_checker import validate_path, OpCategory  # 统一错误提示 - 小欧 2026-07-12
from app.tools.toolhelper.error_hints import hint_for_write_error
from app.tools.validate.file_type_checker import check_for_text_tool
from app.tools.validate.file_safety_checker import check_content_safety
from app.logger import logger
from app.utils.path_utils import to_win_long_path  # #5长路径包裹 — 小欧 2026-08-13
from app.tools.file.file_encoding import get_file_encoding
from app.tools.file.file_state import record_write, check_conflict, is_unchanged
from app.tools.toolhelper.syntax_validator import validate_syntax, detect_language  # 小欧 2026-07-21 统一语法检测接入


def _detect_file_encoding_for_write(file_path: str, append: bool) -> str:
    """统一编码检测 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-30 抽公用"""
    if not append:
        return "utf-8"
    path = Path(file_path)
    if not (Path(to_win_long_path(path)).exists() and Path(to_win_long_path(path)).is_file()):  # #5长路径 — 小欧 2026-08-13
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
    """原子写入文件 — 小沈 2026-05-25 — 小欧 2026-06-22 — 小欧 2026-06-24 返回具体错误信息 — 小欧 2026-08-06 追加补换行 — 小欧 2026-08-07 BUG-05修复: 编码无法编码时降级utf-8"""
    try:
        _long = to_win_long_path(path)  # #5长路径: open/mkdir/stat 统一 \\?\ 前缀 — 小欧 2026-08-13
        if create_parents:
            os.makedirs(to_win_long_path(path.parent), exist_ok=True)
        if append:
            # 追加且原文件非空末尾非换行符: 自动补换行, 避免与末行合并 — 小欧 2026-08-06
            if Path(_long).exists() and Path(_long).is_file() and Path(_long).stat().st_size > 0:
                with open(_long, 'rb') as _rf:
                    _rf.seek(-1, 2)
                    _last_byte = _rf.read(1)
                if _last_byte not in (b'\n', b'\r'):
                    content = '\n' + content
        mode = 'a' if append else 'w'
        with open(_long, mode, encoding=encoding, newline='') as f:
            f.write(content)
        return True, ""
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        # BUG-05修复(小欧 2026-08-07): GBK等编码无法编码emoji时, 自动降级以utf-8重写/追加
        #   日志证据: 09:11:34 write_text_file.py:88 'gbk' codec can't encode '\U0001f602'
        #   根因: _detect_file_encoding_for_write 对 append 返回文件原编码(如gbk), GBK无法编码emoji → 直接失败
        #   设计: UTF-8是GBK超集, 追加模式下转utf-8写(仅当原文件内容可无损重读), 不再崩溃
        if encoding and encoding.lower() != "utf-8":
            try:
                _fallback_mode = mode
                if append and Path(_long).exists() and Path(_long).is_file() and Path(_long).stat().st_size > 0:
                    # 追加且原文件非空: 先读回原内容, 再以utf-8整写(避免mode='a'+content重复原文件)
                    with open(_long, 'r', encoding=encoding, newline='') as _rf:
                        _existing = _rf.read()
                    content = _existing + content
                    _fallback_mode = 'w'
                with open(_long, _fallback_mode, encoding="utf-8", newline='') as f:
                    f.write(content)
                logger.warning(f"[_write_file_atomic] 编码{encoding}无法编码,已降级为utf-8写入: {path}")
                return True, ""
            except (UnicodeEncodeError, UnicodeDecodeError) as e2:
                error_msg = f"编码错误(utf-8降级也失败): {e2}"
                logger.error(f"[_write_file_atomic] 写入失败: {path}, {error_msg}")
                return False, error_msg
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
    _act_params = {"path": file_path}
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
    path: str,
    content: str,
    encoding: Optional[str] = None,
    append: bool = False,
) -> Dict[str, Any]:
    """写入文本文件 — 小沈 2026-05-25 重构拆分 — 小欧 2026-06-22 独立文件 — 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量file_path — 小欧 2026-07-11
    file_path = path
    syntax_warn = None  # 追加模式语法警告(写入后仍提示, 不阻断) — 小欧 2026-07-21
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

    # 容错: 自动移除Python文件末尾的heredoc标记PYEOF — 小欧 2026-07-29（防止LLM把heredoc标记复制进文件）
    auto_removed_pyeof = False
    _lang = detect_language(file_path, checked_content)
    if not append and _lang == "python":
        _stripped = checked_content.rstrip()
        if _stripped.endswith("\nPYEOF"):
            checked_content = _stripped[:-5] + "\n"
            auto_removed_pyeof = True
            logger.warning(f"[writetext] 自动移除Python文件末尾的heredoc标记PYEOF: {file_path}")

    # 语法检测 — 整文件代码写阻断; 追加仅警告(片段无法整体校验) — 小欧 2026-07-21 — 小欧 2026-07-29 优化hint带行号+建议
    _syn = validate_syntax(checked_content, _lang, file_path)
    if not _syn.valid:
        _lang_name = {"python": "Python", "json": "JSON", "yaml": "YAML"}.get(_syn.language, _syn.language)
        _line_info = f"(行{_syn.line})" if _syn.line else ""
        _sugg = f"，{_syn.suggestion}" if _syn.suggestion else ""
        _hint = f"{_lang_name}语法错误{_line_info}{_sugg}"
        if not append:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=_syn.error_text(), hint=_hint, user_encoding=encoding, user_append=append)
            if _syn.line:
                llm_data["metrics"]["error_line"] = {"value": _syn.line, "text": f"第{_syn.line}行"}
            if _syn.suggestion:
                llm_data["metrics"]["suggestion"] = {"value": _syn.suggestion, "text": _syn.suggestion}
            return build_error(data={}, llm_data=llm_data)
        logger.warning(f"[writetext] 追加模式语法警告: {_syn.error_text()}")
        syntax_warn = _syn.error_text()

    encoding = encoding or _detect_file_encoding_for_write(file_path, append)

    # 早期encoding校验 — 小欧 2026-07-17
    try:
        codecs.lookup(encoding)
    except LookupError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"无效编码: {encoding}", hint="请使用正确的编码名称", user_encoding=encoding, user_append=append)
        return build_error(data={}, llm_data=llm_data)

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
    if not append and Path(to_win_long_path(path)).exists():  # #5长路径 — 小欧 2026-08-13
        try:
            old_raw = Path(to_win_long_path(path)).read_text(encoding=encoding)
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
                # branch: #23 writetext (content_preview) — 2026-07-20 用户裁定恢复 Tool 层预览
                # trigger: "content_preview" in data
                # handler: 简单拼接 "已写入内容\n" + data["content_preview"]
                # file:    observation_formatter.py
                # ------------------------------------------------------------------------------
                return build_success(data={"content_preview": _build_content_preview(checked_content)}, llm_data=llm_data)
        except Exception:
            old_content = None

    encoding_warning = None
    if append and Path(to_win_long_path(path)).exists() and Path(to_win_long_path(path)).is_file():  # #5长路径 — 小欧 2026-08-13
        original_encoding = _detect_file_encoding_for_write(file_path, True)
        if encoding != original_encoding:
            encoding_warning = f"文件原始编码为'{original_encoding}',当前使用'{encoding}'写入,可能导致文件编码混乱"

    try:
        _hooks = get_current_hooks_or_noop()  # A1: ContextVar 取安全 hooks(BUG-3修复: _or_noop 兜底防 NPE) — 小沈 2026-08-13
        operation_id = _hooks.record_operation(
            task_id=task_id,
            operation_type=OperationType.CREATE,
            destination_path=path,
            sequence_number=0,
        )

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            # 数据库可用，使用execute_with_safety
            def _do_write():
                return _hooks.execute_with_safety(operation_id, lambda: _write_file_atomic(checked_content, path, encoding, append, create_parents))
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
                        ))
                except Exception as e:
                    logger.debug(f"diff生成失败: {e}")

            record_write(file_path)

            try:
                bytes_written = len(checked_content.encode(encoding))
            except (UnicodeEncodeError, LookupError):
                bytes_written = len(checked_content.encode("utf-8"))
            if syntax_warn:
                # 追加模式: 文件已写入, 但语法有问题需提示 LLM/用户 — 小欧 2026-07-21
                llm_data = _build_write_text_file_llm_data(
                    "warning", duration_ms, file_path=str(path),
                    bytes_written=bytes_written, detail=syntax_warn,
                    mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append,
                )
                if diff_text:
                    llm_data["diff"] = diff_text
                return build_warning(
                    data={"content_preview": _build_content_preview(checked_content)},
                    llm_data=llm_data,
                )
            if encoding_warning:
                llm_data = _build_write_text_file_llm_data("warning", duration_ms, file_path=str(path), bytes_written=bytes_written, detail=encoding_warning, mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append)
                if diff_text:
                    llm_data["diff"] = diff_text
                return build_warning(
                    data={"content_preview": _build_content_preview(checked_content)},
                    llm_data=llm_data,
                )
            llm_data = _build_write_text_file_llm_data("success", duration_ms, file_path=str(path), bytes_written=bytes_written, mtime_warning=conflict_warning or "", user_encoding=encoding, user_append=append)
            with_artifact_file(llm_data, file_path)
            if auto_removed_pyeof:
                llm_data["summary"] += "（已自动移除末尾PYEOF标记）"
                llm_data["metrics"]["auto_removed_pyeof"] = {"value": True, "text": "已自动移除文件末尾的heredoc标记PYEOF"}
            if diff_text:
                llm_data["diff"] = diff_text
            # ---- observation_formatter route -------------------------------------------
            # branch: #23 writetext (content_preview) — 2026-07-20 用户裁定恢复 Tool 层预览
            # trigger: "content_preview" in data
            # handler: 简单拼接 "已写入内容\n" + data["content_preview"]
            # file:    observation_formatter.py
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
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e), hint=hint_for_write_error(e, Path(file_path).name), user_encoding=encoding, user_append=append)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)
