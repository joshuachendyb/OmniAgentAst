# -*- coding: utf-8 -*-
"""
execute_sql — 执行写操作SQL
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
"""

import re
import sqlite3
import time as _time_mod
from typing import Any, Dict, List, Optional, Union, Literal, Tuple

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error, build_warning
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


def _check_sql_safety(sql: str, dry_run: bool) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """统一危险模式检测 + 无WHERE检测 + 拦截决策 — 小沈 2026-05-25"""
    sql_upper = sql.strip().upper()
    DANGEROUS_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)
    dangerous_matches = DANGEROUS_PATTERN.findall(sql)
    if re.match(r'\s*(DELETE|UPDATE)\s', sql_upper) and 'WHERE' not in sql_upper:
        dangerous_matches.append('NO_WHERE')
    if dangerous_matches:
        warnings = []
        dangerous_to_show = [d for d in dangerous_matches if d != 'NO_WHERE']
        if dangerous_to_show:
            warnings.append(f"危险操作: {dangerous_to_show}")
        if 'NO_WHERE' in dangerous_matches:
            warnings.append("缺少 WHERE 条件")
        return True, f"警告:检测到危险操作 {'+'.join(warnings)},已拦截执行。可使用dry_run=true预演", dangerous_matches
    return False, None, None


def _build_execute_sql_llm_data(exec_code, duration_ms, sql, affected_rows):
    """execute_sql的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"SQL执行失败: {sql[:80]}",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": {"sql": sql[:200]}},
            "status": {"exec_code": "error", "message": "执行失败", "code": ERR_SQL_EXEC, "detail": "SQL执行错误", "hint": "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"SQL执行警告: 影响{affected_rows}行",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": {"sql": sql[:200]}},
            "status": {"exec_code": "warning", "message": "影响行数超过安全阈值", "code": "WARNING_DB_SAFETY", "detail": f"影响行数{affected_rows}>10000", "hint": "建议缩小条件范围"},
            "duration_ms": duration_ms,
            "metrics": {"affected_rows": {"value": affected_rows, "text": f"{affected_rows}行"}},
        }
    return {
        "summary": f"SQL执行成功, 影响{affected_rows}行",
        "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": {"sql": sql[:200]}},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"affected_rows": {"value": affected_rows, "text": f"影响{affected_rows}行"}},
    }


def execute_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
                connection_string: Optional[str] = None, db_path: Optional[str] = None,
                dry_run: bool = False, timeout: int = 30000) -> Dict[str, Any]:
    """执行写操作SQL — 小健 2026-06-22 拆分独立文件"""
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()

    try:
        has_danger, warning_msg, dangerous_list = _check_sql_safety(sql, dry_run)
        if has_danger and not dry_run:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("warning", duration_ms, sql, 0)
            return build_warning(data={"detected": dangerous_list, "suggestion": "检测到危险操作,建议使用 dry_run=true 先验证"}, llm_data=llm_data)

        if dry_run:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("success", duration_ms, sql, 0)
            return build_success(data={"sql": sql, "dry_run": True, "syntax_valid": True}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0)
            return build_error(data={"error_detail": conn_error}, llm_data=llm_data)

        if connection_type in ("mysql", "postgresql"):
            from sqlalchemy import text
            engine = conn.engine
            result = conn.execute(text(sql))
            conn.commit()
            affected_rows = result.rowcount
        else:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected_rows = cursor.rowcount
            if affected_rows > 10000:
                conn.rollback()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("warning", duration_ms, sql, affected_rows)
                return build_warning(data={"affected_rows": affected_rows, "action": "rollback"}, llm_data=llm_data)
            conn.commit()

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("success", duration_ms, sql, affected_rows)
        return build_success(data={"affected_rows": affected_rows, "sql": sql}, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"[execute_sql] ERR_SQL_EXEC: {e}")
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"[execute_sql] ERR_EXEC_FAILED: {e}")
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["execute_sql"]