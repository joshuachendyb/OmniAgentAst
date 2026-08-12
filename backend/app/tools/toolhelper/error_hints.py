# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 创建: A5 职责拆分，从 app/tools/validate/file_path_checker.py 整段复制迁入
#   错误提示函数(permission_error_hint/hint_for_write_error/hint_for_read_error/sql_error_hint/hint_for_data_error)，
#   仅改导入归属(validate → toolhelper)，函数签名与业务逻辑一字不改。
#   依赖随迁: sqlite3、pandas 可选导入(_pd)。原文件仅保留路径/参数校验。
"""
toolhelper/error_hints.py — 工具结果解释层：错误提示函数（内部辅助，不暴露给LLM）

A5 职责拆分（2026-08-13 小欧）：
错误提示本质是"工具结果解释层"，不属于路径校验。从 file_path_checker.py 迁出，
供数据分析(dataanalysis)、文档(document)、文件(file)、网络(network)等分类工具广泛使用。
函数签名/逻辑与迁移前完全一致。
"""

import sqlite3

# pandas可选依赖: 模块级导入(仅一次), hint_for_data_error消费 — 小沈 2026-07-26
try:
    import pandas as _pd
except ImportError:
    _pd = None

__all__ = [
    "permission_error_hint",
    "hint_for_write_error",
    "hint_for_read_error",
    "sql_error_hint",
    "hint_for_data_error",
]


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
