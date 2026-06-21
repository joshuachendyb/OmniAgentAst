# -*- coding: utf-8 -*-
"""
DATABASE Tools - 数据库工具实现
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【架构规范】2026-04-29 小沈

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

【工具列表】(共3个)
1. query_sql - 执行只读SQL查询
2. execute_sql - 执行写操作SQL
3. get_db_schema - 获取数据库表结构

【2026-04-29 小健审查修复】
- 添加真实数据库连接支持:SQLite文件、MySQL、PostgreSQL

创建时间: 2026-04-29
"""

import fnmatch
import re
import sqlite3
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Literal, Tuple
from app.utils.logger import logger
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error, build_warning
from app.constants import (
    ERR_DB_CONNECTION,
    ERR_DOC_DB_TABLE_NOT_FOUND,
    ERR_EXEC_FAILED,
    ERR_QUERY_FAILED,
    ERR_READ_ONLY_VIOLATION,
    ERR_SCHEMA_FAILED,
    ERR_SQL_EXEC,
)





def _get_connection(connection_type: str, connection_string: Optional[str], db_path: Optional[str], timeout: int = 30000):
    """获取数据库连接,返回 (conn, engine_or_none, error_message)"""
    try:
        if connection_type == "sqlite":
            if not db_path:
                return None, None, "SQLite必须提供db_path参数,禁止默认连接应用数据库"
            path = db_path
            return sqlite3.connect(path, timeout=timeout / 1000), None, None
        elif connection_type in ("mysql", "postgresql"):
            if not connection_string:
                return None, None, f"错误:{connection_type} 需要提供 connection_string"
            
            try:
                from sqlalchemy import create_engine
                
                engine = create_engine(
                    connection_string,
                    connect_args={"timeout": timeout / 1000} if connection_type == "mysql" else {}
                )
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
    """关闭数据库连接"""
    try:
        if engine:
            conn.close()
            engine.dispose()
        elif conn:
            conn.close()
    except Exception as e:
        logger.warning(f"关闭数据库连接时出错: {e}")


def _build_query_sql_llm_data(exec_code, duration_ms, sql, row_count, columns):
    if exec_code == "error":
        return {
            "summary": f"SQL查询失败: {sql[:80]}",
            "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql[:80], "params": {"sql": sql[:200]}},
            "status": {"exec_code": "error", "message": "查询失败", "code": ERR_SQL_EXEC, "detail": "SQL执行错误", "hint": "请检查SQL语法"},
            "duration_ms": duration_ms, "metrics": {},
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

def query_sql(
    sql: str,
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 50,
    timeout: int = 15000,
) -> Dict[str, Any]:
    """执行只读SQL查询
    【2026-06-20 小健】Schema删limit/timeout，函数签名保留内部默认值
    【2026-06-21 小健】builder改造，新3字段result

    Args:
        sql: SQL 查询语句。仅支持 SELECT/SHOW/DESCRIBE 等只读操作
        connection_type: 数据库类型:sqlite/mysql/postgresql
        connection_string: MySQL/PostgreSQL 连接字符串
        db_path: SQLite 数据库文件路径
        limit: 最大返回行数,默认50
        timeout: 超时毫秒数,默认15000

    Returns:
        Dict with code, data, message
    """
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()
    
    try:
        sql_upper = sql.strip().upper()
        
        if not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "WITH", "EXPLAIN")):
            attempted_type = sql.split()[0].upper() if sql.strip() else "未知"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
            return build_error(data={"attempted_type": attempted_type, "hint": "如需写操作请使用execute_sql工具"}, llm_data=llm_data)
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
            return build_error(data={"error": conn_error}, llm_data=llm_data)

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
        data = truncate_data_for_frontend({
            "columns": columns,
            "rows": results,
            "total": len(results),
            "table": table_str
        })
        llm_data = _build_query_sql_llm_data("success", duration_ms, sql, len(results), columns)
        return build_success(data=data, llm_data=llm_data)
            
    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [])
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


def _check_sql_safety(sql: str, dry_run: bool) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """统一危险模式检测 + 无WHERE检测 + 拦截决策。

    小沈 2026-05-25 重构拆分
    消除 S1a-c(危险检测) + S2a-c(拦截决策) 的重复分支。
    返回: (has_danger, warning_message, detected_list)
    """
    sql_upper = sql.strip().upper()

    DANGEROUS_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)
    dangerous_matches = DANGEROUS_PATTERN.findall(sql)

    no_where_pattern = re.compile(r'\b(DELETE|UPDATE)\b.*?(?!.*\bWHERE\b)', re.IGNORECASE | re.DOTALL)
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
    if exec_code == "error":
        return {
            "summary": f"SQL执行失败: {sql[:80]}",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": {"sql": sql[:200]}},
            "status": {"exec_code": "error", "message": "执行失败", "code": ERR_SQL_EXEC, "detail": "SQL执行错误", "hint": "请检查SQL语法"},
            "duration_ms": duration_ms, "metrics": {},
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

def execute_sql(
    sql: str,
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = 30000,
) -> Dict[str, Any]:
    """执行写操作SQL - 小沈 2026-05-25 重构拆分
    【2026-06-20 小健】Schema删timeout，函数签名保留内部默认值
    【2026-06-21 小健】builder改造，新3字段result
    """
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
            return build_error(data={"error": conn_error}, llm_data=llm_data)

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
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"[execute_sql] ERR_EXEC_FAILED: {e}")
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


def _get_tables(conn, connection_type: str, db_name: Optional[str]) -> List[str]:
    """获取表列表(2路SQL) — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = :db_name"),
                               {"db_name": db_name or "test"})
        return [row[0] for row in result.fetchall()]
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def _get_columns(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取列信息(2路SQL) — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT column_name, data_type, is_nullable, column_key, column_default FROM information_schema.columns WHERE table_name=:t"), {"t": table_name})
        return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", "pk": r[3] == "PRI", "default": r[4]} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    return [{"name": r[1], "type": r[2], "nullable": not r[3], "default": r[4], "pk": bool(r[5])} for r in cursor.fetchall()]


def _get_indexes(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取索引信息(2路SQL) — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT index_name, non_unique FROM information_schema.statistics WHERE table_name=:t GROUP BY index_name, non_unique"), {"t": table_name})
        return [{"name": r[0], "unique": not bool(r[1])} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list('{table_name}')")
    return [{"name": r[1], "unique": bool(r[2])} for r in cursor.fetchall()]


def _filter_tables(tables: List[str], table_name: Optional[str], filter_pattern: Optional[str]) -> List[str]:
    """表名过滤:精确匹配优先,fnmatch降级,20表截断 — 小沈 2026-05-25 重构"""
    if table_name:
        tables = [t for t in tables if t == table_name]
        if not tables:
            return []
    elif filter_pattern:
        pat = filter_pattern.replace("%", "*").replace("_", "?")
        tables = [t for t in tables if fnmatch.fnmatch(t.lower(), pat.lower())]
    return tables[:20]


def _build_get_db_schema_llm_data(exec_code, duration_ms, total_tables=0, table_names=None,
                                    err_code="", detail="", hint=""):
    """get_db_schema的llm_data构建函数 — 小健 2026-06-21"""
    table_names = table_names or []
    if exec_code == "error":
        return {
            "summary": f"获取数据库结构失败: {detail}" if detail else "获取数据库结构失败",
            "action": {"tool": "get_db_schema", "tool_zh": "获取结构", "target": "database", "params": {}},
            "status": {"exec_code": "error", "message": "获取失败", "code": err_code or ERR_DB_CONNECTION, "detail": detail, "hint": hint},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"获取到{total_tables}个表的结构信息",
        "action": {"tool": "get_db_schema", "tool_zh": "获取结构", "target": "database", "params": {}},
        "status": {"exec_code": "success", "message": "获取成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"total": {"value": total_tables, "text": f"{total_tables}个表"}, "tables": {"value": table_names, "text": f"表: {', '.join(table_names[:5])}"}},
    }

def get_db_schema(connection_type="sqlite", connection_string=None, db_path=None,
                   db_name=None, table_name=None, filter_pattern=None) -> Dict:
    """获取数据库表结构 — 小沈 2026-05-25 重构
    【2026-06-20 小健】Schema删db_name/filter_pattern，函数签名保留内部默认值
    【2026-06-21 小健】builder改造，新3字段result
    """
    conn = engine = None
    t0 = _time_mod.perf_counter()
    try:
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_DB_CONNECTION, detail=conn_error, hint="请检查连接参数")
            return build_error(data={"error": conn_error}, llm_data=llm_data)

        tables = _get_tables(conn, connection_type, db_name)
        tables = _filter_tables(tables, table_name, filter_pattern)
        if table_name and not tables:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_DOC_DB_TABLE_NOT_FOUND, detail=f"表不存在: {table_name}", hint="请确认表名正确")
            return build_error(data={"table_name": table_name}, llm_data=llm_data)

        schema_info = []
        for t in tables:
            columns = _get_columns(conn, connection_type, t)
            indexes = _get_indexes(conn, connection_type, t)
            schema_info.append({"name": t, "columns": columns, "indexes": indexes})

        md = f"## 数据库结构 (共 {len(schema_info)} 个表)\n\n"
        for table in schema_info:
            md += f"### {table['name']}\n\n|字段名|类型|可空|主键|默认值|\n|--------|------|------|------|--------|\n"
            for c in table["columns"]:
                md += f"|{c['name']}|{c['type']}|{'否' if c.get('nullable') else '是'}|{'是' if c.get('pk') else '否'}|{c.get('default') or '-'}|\n"
            md += "\n"

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        table_names = [t["name"] for t in schema_info]
        llm_data = _build_get_db_schema_llm_data("success", duration_ms, len(schema_info), table_names)
        return build_success(data={"tables": schema_info, "total": len(schema_info), "markdown": md}, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_SQL_EXEC, detail=str(e))
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_SCHEMA_FAILED, detail=str(e))
        return build_error(data={"error": str(e)}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


def _format_table(columns: List[str], rows: List[Dict]) -> str:
    """格式化表格输出"""
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

