# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-27 - 小沈 - 创建: tool内部路径业务级检查集中管理，散落校验函数归并统一
# 2026-07-04 - 小欧 - 重构统一入口 + 注释说明
# 2026-07-09 - 北京老陈 - 交叉引用注释统一
# 2026-07-26 - 小欧 - hint_for_read_error加MemoryError分支, OOM时提示分批读取
# 2026-07-26 - 小欧 - 迁移: sql_error_hint/hint_for_data_error从tool_constants迁入(file_path_checker同属检查类)
# 2026-07-26 - 小沈 - BugFix #7: sqlite3/pandas函数级import提升模块级; #10: PermissionError冗余分支删(矫正,确认删除); #12: hint_for_read_error入__all__
# 2026-07-29 - 小欧 - ERR_FILE_READ_FAILED 三堂会审: hint_for_read_error 文件不存在提示改为引导用find/listdir确认存在
# 2026-08-02 - 小欧 - 加固validate_not_system_path: 新增磁盘根目录硬阻断(C:\), 修复盘后单级目录漏网(原path_after_drive无前导斜杠导致C:\\Windows不拦, 现用os.path.splitdrive规范化判断)
# 2026-08-09 - 小欧 - task006 P1落地(sql_error_hint): 新增多语句识别分支"one statement at a time" → 精准hint"SQLite仅支持单条语句", 打破LLM多语句SQL低效重试循环
# 2026-08-09 - 小欧 - task006 P3落地(sql_error_hint): 新增 UNIQUE 分支 — "unique constraint"/"is not unique" → 引导查现值再UPDATE/INSERT
#   病根: UNIQUE 约束失败回落"请检查SQL语法", LLM 无法据此自查(日志 `users.id` 重键 253 处), 陷入插重键低效循环
#   方案: 一分支全覆盖 3 个 SQL 工具(execute_sql/query_sql/get_db_schema 共用 sql_error_hint, DRY); 验证不误伤其它6分支
# 2026-08-09 - 小欧 - 三堂会审复审: UNIQUE 匹配词收紧 "unique constraint"→"unique constraint failed" — 原词会误命中
#   "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint"(LLM写错ON CONFLICT子句), 收紧后精准只匹配
#   sqlite 真实报错 "UNIQUE constraint failed: table.column"
"""
validate/file_path_checker.py — tool内部路径业务级检查（集中管理）

工具层（本文件）：非空/保留字符/保留名/系统目录/存在性+类型/业务警告
Safety层（services/safety/tool_safety_checker.py + path_safe_check.py）：
  路径黑名单/白名单/路径穿越/权限校验 — 两层独立运行、互不调用
"""

import logging
import os
import re
import sqlite3
import string
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# pandas可选依赖: 模块级导入(仅一次), hint_for_data_error消费 — 小沈 2026-07-26
try:
    import pandas as _pd
except ImportError:
    _pd = None

__all__ = [
    "validate_path_for_write", "validate_path_for_delete", "validate_path_for_overwrite",
    "validate_path_for_extract", "WINDOWS_SYSTEM_DIRS", "validate_not_system_path",
    "OpCategory", "validate_path", "validate_str_param",
    "permission_error_hint",
    "hint_for_write_error",
    "hint_for_read_error",
    "sql_error_hint",
    "hint_for_data_error",
]

_WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
                     'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
                     'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}


def _has_windows_reserved_name(file_path: str) -> Optional[str]:
    """检查路径是否包含Windows保留名 — 小欧 2026-07-04"""
    try:
        p = Path(file_path)
        for part in p.parts:
            name = part.split('.')[0].upper()
            if name in _WINDOWS_RESERVED:
                return part
    except Exception:
        pass
    return None


def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入操作的路径业务级检查（适用于write_text_file、edit_text_file及所有写入类工具）
    工具层校验：非空/保留字符/保留名（仅警告，不阻断）
    Safety层（path_safe_check.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名", None
    path = Path(file_path)
    try:
        if path.exists() and path.is_file():
            if not append:
                old_size = path.stat().st_size
                if old_size > 1024 * 1024:
                    return True, None, f"覆盖大文件({old_size}字节)，请确认"
            else:
                old_size = path.stat().st_size
                if old_size > 100 * 1024 * 1024:
                    return True, None, f"追加到超大文件({old_size}字节)，请确认"
    except PermissionError:
        return False, f"无权限访问文件: {file_path}", None
    return True, None, None


def validate_path_for_delete(file_path: str, recursive: bool = False, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    删除操作的路径业务级检查（适用于delete_file）
    工具层校验：非空/保留字符/保留名（仅递归/强制警告）
    Safety层（path_safe_check.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名", None
    if recursive and Path(file_path).is_dir():
        return True, None, "递归删除目录，请确认"
    if force:
        return True, None, "永久删除（绕过回收站），请确认"
    return True, None, None


def validate_path_for_overwrite(source: str, destination: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    覆盖操作的路径业务级检查（适用于move_file、copy_file）
    工具层校验：非空（仅覆盖警告）
    Safety层（path_safe_check.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    注意：文件存在检查与实际操作之间存在时间窗口（TOCTOU），
    检查结果仅作为参考，不保证操作时的文件状态一致。
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(source, str) or not source.strip():
        return False, "源路径不能为空", None
    if not isinstance(destination, str) or not destination.strip():
        return False, "目标路径不能为空", None
    if overwrite and Path(destination).exists():
        return True, None, f"覆盖目标文件，请确认"
    return True, None, None


def validate_path_for_extract(output_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    解压操作的路径业务级检查（适用于extract_archive）
    工具层校验：非空（仅系统目录警告）
    Safety层（path_safe_check.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not output_dir:
        return True, None, None
    system_dirs = ["windows", "program files", "program files (x86)"]
    output_lower = output_dir.lower()
    for sd in system_dirs:
        if sd in output_lower:
            return True, None, f"解压到系统目录，请确认"
    return True, None, None


WINDOWS_SYSTEM_DIRS = [
    "/windows/", "/winnt/", "/program files/",
    "/program files (x86)/", "/system32/", "/system/",
]


def validate_not_system_path(file_path: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    检查路径是否涉及Windows系统关键目录（工具层硬阻断）
    Safety层（path_safe_check.py）独立运行：黑名单/白名单/路径穿越/权限

    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    小欧 2026-08-02 加固: 磁盘根目录硬阻断 + 系统目录规范化判断(修复C:\\Windows漏网)
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    # 磁盘根目录(C:\)硬阻断 — 小欧 2026-08-02
    try:
        drive, rest = os.path.splitdrive(file_path)
        if drive and not rest.strip("\\/"):
            return False, f"不允许操作系统根目录: {file_path}", None
    except Exception:
        pass
    path_lower = file_path.lower().replace("\\", "/")
    # 规范化: 去掉盘符前缀, 确保以/开头, 使 /windows/ 等规则可匹配 — 小欧 2026-08-02
    path_after_drive = path_lower.split(":")[-1] if ":" in path_lower else path_lower
    path_after_drive = "/" + path_after_drive.lstrip("/")
    for sd in WINDOWS_SYSTEM_DIRS:
        if path_after_drive == sd.rstrip("/") or path_after_drive.startswith(sd):
            return False, f"不允许操作系统目录下的文件: {file_path}", None
    return True, None, None


from enum import Enum
from typing import Any


class OpCategory(Enum):
    WRITE     = "write"
    READ_FILE = "read_file"
    LIST_DIR  = "list_dir"
    EXISTS    = "exists"


_OP_RULES: Dict[OpCategory, Dict[str, Any]] = {
    OpCategory.WRITE:     {"check_exist": False, "must_be": None},
    OpCategory.READ_FILE: {"check_exist": True,  "must_be": "file"},
    OpCategory.LIST_DIR:  {"check_exist": True,  "must_be": "dir"},
    OpCategory.EXISTS:    {"check_exist": True,  "must_be": None},
}

_WINDOWS_RESERVED_CHARS = '<>:"/\\|?*'


def validate_path(
    op: OpCategory,
    path: str,
    **options: Any,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    统一路径前置校验（编排层，同文件调所有 validate_path_for_*）
    工具层校验：非空/保留字符/保留名/系统目录/存在性+类型/业务警告
    Safety层（path_safe_check.py）后续独立运行：黑名单/白名单/路径穿越/权限校验
    小欧 2026-07-04

    第1层 基础校验（ALL）：非空 + 保留字符 + 保留名 + 盘符存在性
    第2层 系统目录拒绝（ALL）：validate_not_system_path（硬阻断）
    第3层 存在性+类型（WRITE跳过）：exists / is_file / is_dir
    第4层 业务警告：content/append → write；recursive/force → delete；overwrite+source → overwrite；extract_dir → extract

    Returns: (is_valid, error_msg, warning_msg)
    """
    # 第1层
    if not isinstance(path, str) or not path.strip():
        return False, "路径不能为空", None
    # 盘符存在性检查（最先做，最外层的快速否决） — 小欧 2026-07-04
    drive = os.path.splitdrive(path)[0]
    if drive:
        if not os.path.exists(drive + "\\"):
            avail = [f"{l}:" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")]
            return False, f"驱动器: {drive}不存在。可用驱动器: {', '.join(avail)}", None
        # 检测路径中间是否出现多余盘符（如 E:\dir\E:\file）— 小沈 2026-07-08
        _tail = path[len(drive):]
        if re.search(r'[A-Za-z]:', _tail.lstrip("\\/")):
            return False, f"路径: {path}中包含多余的盘符", None
    # 只检查文件名部分（Path(...).name），排除路径分隔符和盘符:号 — 小欧 2026-07-04
    _fname = Path(path).name
    if any(c in _fname for c in _WINDOWS_RESERVED_CHARS):
        return False, f"文件: {_fname}名包含Windows保留字符", None
    reserved = _has_windows_reserved_name(path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名", None

    # 第2层
    is_valid, sys_err, _ = validate_not_system_path(path)
    if not is_valid:
        return False, sys_err, None

    # 第3层
    rule = _OP_RULES[op]
    if rule["check_exist"]:
        p = Path(path)
        if not p.exists():
            # 幂等删除: force=True 时不存在即视为已删除,不报错(delete 专用) — 北京老陈 2026-07-12
            if op == OpCategory.EXISTS and options.get("force"):
                return True, None, None
            logger.warning("[TOCTOU] path=%s op=%s drive_exists=%s parent_exists=%s parent_dir=%s",
                           path, op.value,
                           os.path.exists(os.path.splitdrive(path)[0] + "\\") if os.path.splitdrive(path)[0] else "N/A",
                           p.parent.exists(), str(p.parent))
            return False, "路径不存在: " + path, None
        if rule["must_be"] == "file" and not p.is_file():
            return False, path +"不是文件" , None
        if rule["must_be"] == "dir" and not p.is_dir():
            return False,  path +"不是目录", None

    # 第4层
    warnings = []
    if op == OpCategory.WRITE or "content" in options:
        _, _, w = validate_path_for_write(path, options.get("content", ""), options.get("append", False))
        if w: warnings.append(w)
    if op == OpCategory.EXISTS and (options.get("recursive") or options.get("force")):
        _, _, w = validate_path_for_delete(path, options.get("recursive", False), options.get("force", False))
        if w: warnings.append(w)
    if options.get("overwrite") and "source" in options:
        _, _, w = validate_path_for_overwrite(options["source"], path, True)
        if w: warnings.append(w)
    if "extract_dir" in options:
        _, _, w = validate_path_for_extract(options["extract_dir"])
        if w: warnings.append(w)

    return True, None, "; ".join(warnings) if warnings else None


def validate_str_param(value: Any, param_name: str) -> Optional[str]:
    """字符串参数基础校验 — 小欧 2026-07-05
    None/非str类型/空串(含全空白) → 返回错误信息
    None=通过, str=错误信息
    """
    if value is None:
        return f"参数 {param_name} 不能为 None"
    if not isinstance(value, str):
        return f"参数 {param_name} 必须为字符串, 实际类型为 {type(value).__name__}"
    if not value.strip():
        return f"参数 {param_name} 不能为空字符串"
    return None


def permission_error_hint(file_name: str) -> str:
    """PermissionError 时告知LLM更改文件名或路径 — 小欧 2026-07-08"""
    return f"写入的{file_name}权限不足，更换文件名或路径重试"


def hint_for_write_error(e: Exception, file_name: str) -> str:
    """根据文件写入异常类型返回准确、诚实的 hint — 小欧 2026-07-12 重写

    原则：绝不编造与真实原因无关的提示（如对非磁盘异常谎称“磁盘/权限”）。
    可识别异常给精准提示；未知异常如实报出异常类型，由 detail 承载真实信息。

    覆盖：
    - OSError errno=28 → 磁盘空间不足
    - OSError errno in (36,63) → 文件名过长
    - IndexError → Markdown 表格列数不一致
    - ValueError → 内容/格式异常
    - 其他 → 如实返回异常类型，不编造原因
    """
    if isinstance(e, OSError):
        if e.errno == 28:
            return "磁盘空间不足，请清理磁盘后重试"
        if e.errno in (36, 63):
            return f"文件{file_name}名称过长，请使用更短的文件名或路径"
    if isinstance(e, IndexError):
        return "文档内容的 Markdown 表格列数不一致，请检查表格每行单元格数量是否相同"
    if isinstance(e, ValueError):
        return "文档内容或格式异常，请检查表格或参数后重试"
    return f"写入失败({type(e).__name__})，详见错误明细"


def hint_for_read_error(e: Exception, file_name: str) -> str:
    """根据文件读取异常类型返回准确、诚实的 hint — 小欧 2026-07-12

    原则（与 hint_for_write_error 一致）：绝不编造与真实原因无关的提示。
    前置的 check_for_document_tool 已校验路径与文件类型，故兜底绝不回显
    “文件路径/格式/完整性”等已查项，只如实反映未被识别的异常类型。

    覆盖：
    - FileNotFoundError / OSError errno=2 → 文件不存在
    - PermissionError / OSError errno=13 → 无读取权限
    - IsADirectoryError / OSError errno=21 → 路径指向目录
    - MemoryError → OOM提示分批读取
    - 其他 → 如实返回异常类型，不编造原因
    """
    if isinstance(e, (FileNotFoundError, IsADirectoryError)) or (isinstance(e, OSError) and e.errno in (2, 21)):
        if isinstance(e, IsADirectoryError) or (isinstance(e, OSError) and e.errno == 21):
            return f"{file_name}是目录而非文件，请提供具体的文件路径"
        return f"文件不存在: {file_name}，请先用find或listdir确认文件是否存在"
    if isinstance(e, OSError) and e.errno == 13:
        return f"无读取权限: {file_name}，请检查文件权限"
    if isinstance(e, OSError):
        return f"读取文件失败(OSError)，详见错误明细"
    if isinstance(e, MemoryError):
        return f"文件过大导致内存不足(OOM)，建议使用offset/limit/page等参数分批读取"
    return f"读取失败({type(e).__name__})，详见错误明细"


def sql_error_hint(e: Exception) -> str:
    """根据SQL异常消息生成更精确的hint — 小欧 2026-07-08
       2026-08-09 小欧: 新增多语句识别 — sqlite3.execute仅支持单条, 多语句抛"You can only execute one statement at a time",
       精准提示拆分, 打破LLM多语句SQL低效重试循环(依托sqlite3权威解析器, 不误伤CREATE TRIGGER含分号合法单条)
       2026-08-09 小欧: 新增UNIQUE分支 — "unique constraint failed"/"is not unique" 引导查现值再UPDATE/INSERT"""
    msg = str(e).lower()
    if "no such column" in msg or "has no column" in msg:
        return "请先使用 get_db_schema 查看表结构确认列名是否正确"
    if "no such table" in msg:
        return "请先使用 get_db_schema 查看所有表确认表名是否正确"
    if "unique constraint failed" in msg or "is not unique" in msg:
        return "违反唯一约束(主键/唯一索引冲突)，请先查询该字段现有值，再决定用UPDATE还是INSERT，避免插入重复数据"
    if "one statement at a time" in msg:
        return "SQLite仅支持单条语句执行，请将SQL拆分为单条语句后逐条执行"
    if "syntax error" in msg or "unrecognized token" in msg or "near " in msg:
        return "SQL语法错误，请检查关键字拼写和语句结构"
    if "ambiguous column" in msg:
        return "列名存在歧义，请使用 表名.列名 方式限定"
    if "no such function" in msg:
        return "函数名不存在，请检查SQL函数拼写"
    return "请检查SQL语法"


def hint_for_data_error(e: Exception) -> str:
    """根据数据处理异常类型返回诚实、准确的 hint — 小欧 2026-07-12 — 小沈 2026-07-26 函数级import提升模块级

    原则（与 file_path_checker.hint_for_read/write_error 一致）：
    - 可识别异常给精准提示；
    - 未知异常如实报出异常类型，由 detail 承载真实信息；
    - 绝不编造与真实原因无关的提示（如对权限异常谎称"检查数据"）。
    """
    if isinstance(e, sqlite3.Error):
        return sql_error_hint(e)
    if isinstance(e, OSError) and getattr(e, "errno", None) == 13:
        return "无文件读取/写入权限，请检查文件权限后重试"
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
        return "磁盘空间不足，请清理磁盘后重试"
    if isinstance(e, OSError):
        return f"文件操作失败({e.strerror or type(e).__name__})，详见错误明细"
    # pandas errors (需在ValueError前检查，均继承自ValueError) - 小欧 2026-07-26
    if _pd is not None:
        if isinstance(e, _pd.errors.EmptyDataError):
            return "文件为空，请检查数据文件"
        if isinstance(e, _pd.errors.ParserError):
            return "文件格式解析错误，请检查数据格式(分隔符/编码/列数等)"
        if isinstance(e, _pd.errors.OutOfBoundsDatetime):
            return "数据中的日期时间值超出范围，请检查日期格式"
    if isinstance(e, ValueError):
        return "数据或参数格式异常，请检查输入数据"
    if isinstance(e, (TypeError, KeyError)):
        return "数据结构异常，请检查字段和格式"
    if isinstance(e, ImportError):
        return "所需库未安装，请安装缺失依赖"
    if isinstance(e, MemoryError):
        return "文件数据过大导致内存不足(OOM)，请根据工具或者参数分批处理"
    return f"处理失败({type(e).__name__})，详见错误明细"
