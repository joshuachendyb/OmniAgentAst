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

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.constants import ERR_SQL_EXEC


def _get_connection(connection_type: str, connection_string: Optional[str], db_path: Optional[str], timeout: int = 30000):
    """获取数据库连接,返回 (conn, engine_or_none, error_message) — 小健 2026-06-22"""
    try:
        if connection_type == "sqlite":
            if not db_path:
                return None, None, "SQLite必须提供db_path参数,禁止默认连接应用数据库"
            return sqlite3.connect(db_path, timeout=timeout / 1000), None, None
        elif connection_type in ("mysql", "postgresql"):
            if not connection_string:
                return None, None, f"错误:{connection_type} 需要提供 connection_string"
            try:
                from sqlalchemy import create_engine
                engine = create_engine(connection_string, connect_args={"timeout": timeout / 1000} if connection_type == "mysql" else {})
                return engine.connect(), engine, None
            except ImportError:
                return None, None, f"错误:{connection_type} 需要安装 sqlalchemy 和对应驱动"
            except Exception as e:
                return None, None, f"连接失败: {str(e)}"
        else:
            return None, None, f"不支持的数据库类型: {connection_type}"
    except Exception as e:
        return None, None, f"获取连接失败: {str(e)}"


def _close_connection(conn, engine=None):
    """关闭数据库连接 — 小健 2026-06-22"""
    try:
        if engine:
            conn.close()
            engine.dispose()
        elif conn:
            conn.close()
    except Exception as e:
        logger.warning(f"关闭数据库连接时出错: {e}")


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


def _build_query_sql_llm_data(exec_code, duration_ms, sql, row_count, columns):
    """query_sql的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"SQL查询失败: {sql[:80]}",
            "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql[:80], "params": {"sql": sql[:200]}},
            "status": {"exec_code": "error", "message": "查询失败", "code": ERR_SQL_EXEC, "detail": "SQL执行错误", "hint": "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    col_text = ", ".join(columns[:5])
    if len(columns) > 5:
        col_text += "..."
    return {
        "summary": f"查询返回{row_count}行, 列: {col_text}",
        "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql[:80], "params": {"sql": sql[:200]}},
        "status": {"exec_code": "success", "message": "查询成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "columns": {"value": columns[:5], "text": f"列: {col_text}"}},
    }


def query_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
              connection_string: Optional[str] = None, db_path: Optional[str] = None,
              limit: int = 50, timeout: int = 15000) -> Dict[str, Any]:
    """执行只读SQL查询 — 小健 2026-06-22 拆分独立文件"""
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()

    try:
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "WITH", "EXPLAIN")):
            attempted_type = sql.split()[0].upper() if sql.strip() else "未知"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
            return build_error(data={"error_detail": f"只读查询不支持{attempted_type}操作", "params": {"sql": sql[:200], "attempted_type": attempted_type}, "hint": "如需写操作请使用execute_sql工具"}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
            return build_error(data={"error_detail": conn_error, "params": {"sql": sql[:200], "connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)

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

        table_str = _format_table(columns, results)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        data = {"columns": columns, "rows": results, "total": len(results), "table": table_str}
        llm_data = _build_query_sql_llm_data("success", duration_ms, sql, len(results), columns)
        return build_success(data=data, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
        return build_error(data={"error_detail": str(e), "params": {"sql": sql[:200]}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
        return build_error(data={"error_detail": str(e), "params": {"sql": sql[:200]}}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["query_sql"]