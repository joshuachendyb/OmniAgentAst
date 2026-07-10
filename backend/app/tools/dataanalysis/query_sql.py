# -*- coding: utf-8 -*-
"""
query_sql — 执行只读SQL查询
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import sqlite3
import time as _time_mod
from typing import Any, Dict, List, Optional, Union, Literal

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_SQL_EXEC, sql_error_hint
from app.tools.tool_fc_helper import _get_connection, _close_connection


def _format_table(columns: List[str], rows: List[Dict]) -> str:
    """格式化表格输出 — 小健 2026-06-22"""
    if not columns or not rows:
        return "无数据"
    col_widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            value = str(row.get(col, ""))
            col_widths[col] = max(col_widths[col], len(value))
    header = " | ".join(col.ljust(col_widths[col]) for col in columns)
    separator = "-+-".join("-" * col_widths[col] for col in columns)
    lines = [header, separator]
    for row in rows:
        line = " | ".join(str(row.get(col, "")).ljust(col_widths[col]) for col in columns)
        lines.append(line)
    return "\n".join(lines)


def _build_query_sql_llm_data(exec_code, duration_ms, sql, row_count, columns, detail="", hint="",
                               connection_type="", db_path="", limit=0, timeout=0):
    """query_sql的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增detail/hint参数 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-06 sql截断200→50 统一"""
    _act_params = {"sql": sql[:50]}  # 小欧 2026-07-06 200→50 统一截断
    if connection_type:
        _act_params["connection_type"] = connection_type
    if db_path:
        _act_params["db_path"] = db_path
    if limit:
        _act_params["limit"] = limit
    if timeout:
        _act_params["timeout"] = timeout
    _target = db_path or connection_type or "database"
    if exec_code == "error":
        return {
            "summary": f"查询{_target}，失败: {detail}",
            "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql[:80], "params": _act_params},
            "status": {"exec_code": "error", "message": detail if detail else "查询失败", "code": ERR_SQL_EXEC, "detail": detail, "hint": hint if hint else "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    col_text = ", ".join(columns[:5])
    if len(columns) > 5:
        col_text += "..."
    return {
        "summary": f"查询{_target}，成功: {row_count}行, 列: {col_text}",
        "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql[:80], "params": _act_params},
        "status": {"exec_code": "success", "message": "查询成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "columns": {"value": columns[:5], "text": f"列: {col_text}"}},
    }


def query_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
              connection_string: Optional[str] = None, db_path: Optional[str] = None,
              limit: int = 50, timeout: int = 15000) -> Dict[str, Any]:
    """执行只读SQL查询 — 小健 2026-06-22 拆分独立文件
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()

    if not isinstance(sql, str) or not sql.strip():
        duration_ms = 0
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql or "", 0, [], detail="SQL语句不能为空", hint="请提供有效的SQL语句",
                                               connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    try:
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "WITH", "EXPLAIN")):
            attempted_type = sql.split()[0].upper() if sql.strip() else "未知"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [], detail=f"只读查询不支持{attempted_type}操作", hint="如需写操作请使用execute_sql工具",
                                                   connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [], detail=conn_error, hint="请检查数据库连接参数",
                                                   connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        if connection_type in ("mysql", "postgresql"):
            from sqlalchemy import text
            engine = conn.engine
            result = conn.execute(text(sql))
            rows = result.fetchall()
            columns = list(result.keys()) if hasattr(result, 'keys') else []
            results = [dict(zip(columns, row)) for row in rows]
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = [dict(row) for row in rows]

        if limit > 0 and len(results) > limit:
            results = results[:limit]

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"columns": columns, "rows": results}
        llm_data = _build_query_sql_llm_data("success", duration_ms, sql, len(results), columns,
                                               connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
        # =============================================================================
        # 数据设计：total 从 data 移除，行数通过 llm_data.metrics（key:row_count）传入 summary
        # summary 示例: "查询返回10行, 列: id, name"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #5 rows
        # trigger: "rows" in data — rows 是 List[list|dict]
        # handler: _format_rows(data["rows"], data.get("columns"))
        # file:    observation_formatter.py:140-142
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [], detail=str(e), hint=sql_error_hint(e),
                                               connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [], detail=str(e), hint="请检查SQL语句和参数",
                                               connection_type=connection_type, db_path=db_path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["query_sql"]