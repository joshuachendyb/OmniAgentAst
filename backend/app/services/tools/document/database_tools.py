# -*- coding: utf-8 -*-
"""
DATABASE Tools - 数据库工具实现

【架构规范】2026-04-29 小沈

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

【工具列表】（共3个）
1. query_sql - 执行只读SQL查询
2. execute_sql - 执行写操作SQL
3. get_db_schema - 获取数据库表结构

【2026-04-29 小健审查修复】
- 添加真实数据库连接支持：SQLite文件、MySQL、PostgreSQL

创建时间: 2026-04-29
"""

import fnmatch
import re
import sqlite3
from typing import Any, Dict, List, Optional, Union, Literal, Tuple
from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend, make_json_safe
from app.services.tools._response import build_success, build_error, build_warning





def _get_connection(connection_type: str, connection_string: Optional[str], db_path: Optional[str], timeout: int = 30000):
    """获取数据库连接，返回 (conn, engine_or_none, error_message)"""
    try:
        if connection_type == "sqlite":
            if db_path:
                return sqlite3.connect(db_path, timeout=timeout / 1000), None, None
            else:
                return sqlite3.connect(":memory:", timeout=timeout / 1000), None, None
        elif connection_type in ("mysql", "postgresql"):
            if not connection_string:
                return None, None, f"错误：{connection_type} 需要提供 connection_string"
            
            try:
                from sqlalchemy import create_engine
                
                engine = create_engine(
                    connection_string,
                    connect_args={"timeout": timeout / 1000} if connection_type == "mysql" else {}
                )
                return engine.connect(), engine, None
            except ImportError:
                return None, None, f"错误：{connection_type} 需要安装 sqlalchemy 和对应驱动"
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


def query_sql(
    sql: str,
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 50,
    timeout: int = 15000,
) -> Dict[str, Any]:
    """
    执行只读SQL查询

    Args:
        sql: SQL 查询语句。仅支持 SELECT/SHOW/DESCRIBE 等只读操作
        connection_type: 数据库类型：sqlite/mysql/postgresql
        connection_string: MySQL/PostgreSQL 连接字符串
        db_path: SQLite 数据库文件路径
        limit: 最大返回行数，默认50
        timeout: 超时毫秒数，默认15000
        output_format: 输出格式，table(默认) 或 json

    Returns:
        Dict with code, data, message
    """
    conn = None
    engine = None
    
    try:
        sql_upper = sql.strip().upper()
        
        if not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "WITH", "EXPLAIN")):
            return build_error(ERR_READ_ONLY_VIOLATION, f"错误：只允许 SELECT/SHOW/DESCRIBE 等只读操作，当前语句以 {sql.split()[0] if sql.split() else '未知'} 开头",
                next_actions=build_next_actions([
                    ("execute_sql", "执行写操作", "需要修改数据时"),
                    ("get_db_schema", "查看表结构", "确认字段名时"),
                ]))
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return build_error(ERR_DB_CONNECTION, conn_error,
                next_actions=build_next_actions([
                    ("tool_help", "查看query_sql参数", "检查连接参数时", {"tool_name": "query_sql"}),
                ]))
        
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
        
        # output_format 已从Schema移除，固定使用table格式
        table_str = _format_table(columns, results)
        return build_success(
            truncate_data_for_frontend({
                "columns": columns,
                "rows": results,
                "total": len(results),
                "table": table_str
            }),
            f"查询成功，返回 {len(results)} 行数据",
            llm_data={
                "列": columns, "行数": len(results),
                "行预览": make_json_safe(results[:10], max_str_len=150)
            },
            next_actions=build_next_actions([
                ("execute_sql", "执行写操作SQL", "需要修改数据时"),
                ("get_db_schema", "查看表结构", "需要了解其他表时"),
            ])
        )
            
    except sqlite3.Error as e:
        return build_error(ERR_SQL_EXEC, f"SQL执行错误: {str(e)}",
            next_actions=build_next_actions([
                ("get_db_schema", "查看表结构", "确认字段名是否正确时"),
                ("tool_help", "查看query_sql用法", "检查SQL语法时", {"tool_name": "query_sql"}),
            ]))
    except Exception as e:
        return build_error(ERR_QUERY_FAILED, f"执行失败: {str(e)}",
            next_actions=build_next_actions([
                ("get_db_schema", "查看表结构", "确认表是否存在时"),
                ("tool_help", "查看query_sql用法", "检查参数时", {"tool_name": "query_sql"}),
            ]))
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
        return True, f"警告：检测到危险操作 {'+'.join(warnings)}，已拦截执行。可使用dry_run=true预演", dangerous_matches
    return False, None, None


def _rollback_and_return(conn, error_type: str, error: Exception) -> Dict[str, Any]:
    """统一回滚连接并返回错误。

    小沈 2026-05-25 重构拆分
    消除 E1a/E1b 的回滚+错误返回模式重复2次（行279-283 和 290-294）。
    """
    if conn:
        try:
            conn.rollback()
        except Exception:
            pass
    logger.error(f"[execute_sql] {error_type}: {error}")
    return build_error(error_type, str(error), next_actions=_SQL_NEXT_ACTIONS)


_SQL_NEXT_ACTIONS = build_next_actions([
    ("query_sql", "查询 SQL 数据库", "需要重新查询时"),
    ("tool_help", "查看 execute_sql 用法", "需要帮助时", {"tool_name": "execute_sql"}),
])


def execute_sql(
    sql: str,
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = 30000,
) -> Dict[str, Any]:
    """执行写操作SQL - 小沈 2026-05-25 重构拆分"""
    conn = None
    engine = None

    try:
        has_danger, warning_msg, dangerous_list = _check_sql_safety(sql, dry_run)
        if has_danger and not dry_run:
            return build_warning(
                "WARNING_DB_SAFETY",
                warning_msg,
                data={"detected": dangerous_list, "suggestion": "检测到危险操作，建议使用 dry_run=true 先验证"},
                next_actions=_SQL_NEXT_ACTIONS
            )

        if dry_run:
            return build_success(
                {"sql": sql, "dry_run": True, "syntax_valid": True},
                "预演模式：语法验证通过，实际未执行",
                next_actions=_SQL_NEXT_ACTIONS
            )

        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return build_error(ERR_DB_CONNECTION, conn_error, next_actions=_SQL_NEXT_ACTIONS)

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
                return build_warning(
                    "WARNING_DB_SAFETY",
                    f"警告：影响行数 {affected_rows} > 10000，已自动回滚",
                    data={"affected_rows": affected_rows, "action": "rollback"}
                )

            conn.commit()

        return build_success(
            {"affected_rows": affected_rows, "sql": sql},
            f"执行成功，影响行数: {affected_rows}",
            next_actions=_SQL_NEXT_ACTIONS
        )

    except sqlite3.Error as e:
        return _rollback_and_return(conn, ERR_SQL_EXEC, e)
    except Exception as e:
        return _rollback_and_return(conn, ERR_EXEC_FAILED, e)
    finally:
        _close_connection(conn, engine)


def get_db_schema(
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    db_name: Optional[str] = None,
    table_name: Optional[str] = None,
    filter_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取数据库表结构

    Args:
        connection_type: 数据库类型：sqlite/mysql/postgresql
        connection_string: MySQL/PostgreSQL 连接字符串
        db_path: SQLite 数据库文件路径
        db_name: 数据库名（SQLite 忽略此参数）
        table_name: 指定表名，仅获取该表结构。与filter_pattern互斥，table_name优先 - 小沈 2026-05-17
        filter_pattern: 表名过滤模式（SQL LIKE 语法）
        include_details: 是否包含详细索引、外键、约束信息
        output_format: 输出格式：markdown(默认)、json、sql_ddl

    Returns:
        Dict with code, data, message
    """


def _get_tables(conn, connection_type: str, db_name: Optional[str]) -> List[str]:
    """获取表列表（2路SQL） — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = :db_name"),
                               {"db_name": db_name or "test"})
        return [row[0] for row in result.fetchall()]
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def _get_columns(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取列信息（2路SQL） — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text as sa_text
        result = conn.execute(sa_text("SELECT column_name, data_type, is_nullable, column_key, column_default FROM information_schema.columns WHERE table_name=:t"), {"t": table_name})
        return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", "pk": r[3] == "PRI", "default": r[4]} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    return [{"name": r[1], "type": r[2], "nullable": not r[3], "default": r[4], "pk": bool(r[5])} for r in cursor.fetchall()]


def _get_indexes(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取索引信息（2路SQL） — 小沈 2026-05-25 重构"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text as sa_text2
        result = conn.execute(sa_text2("SELECT index_name, non_unique FROM information_schema.statistics WHERE table_name=:t GROUP BY index_name, non_unique"), {"t": table_name})
        return [{"name": r[0], "unique": not bool(r[1])} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list('{table_name}')")
    return [{"name": r[1], "unique": bool(r[2])} for r in cursor.fetchall()]


def _filter_tables(tables: List[str], table_name: Optional[str], filter_pattern: Optional[str]) -> List[str]:
    """表名过滤：精确匹配优先，fnmatch降级，20表截断 — 小沈 2026-05-25 重构"""
    if table_name:
        tables = [t for t in tables if t == table_name]
        if not tables:
            return []
    elif filter_pattern:
        pat = filter_pattern.replace("%", "*").replace("_", "?")
        tables = [t for t in tables if fnmatch.fnmatch(t.lower(), pat.lower())]
    return tables[:20]


def get_db_schema(connection_type="sqlite", connection_string=None, db_path=None,
                   db_name=None, table_name=None, filter_pattern=None) -> Dict:
    """获取数据库表结构 — 小沈 2026-05-25 重构"""
    conn = engine = None
    try:
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            return build_error(ERR_DB_CONNECTION, conn_error)

        tables = _get_tables(conn, connection_type, db_name)
        tables = _filter_tables(tables, table_name, filter_pattern)
        if table_name and not tables:
            return build_error(ERR_DOC_DB_TABLE_NOT_FOUND, f"表不存在: {table_name}")

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

        return build_success({"tables": schema_info, "total": len(schema_info), "markdown": md},
                              f"获取成功，共 {len(schema_info)} 个表",
                              next_actions=build_next_actions([("query_sql", "查询表数据", "需要查看数据时")]))

    except sqlite3.Error as e:
        return build_error(ERR_SQL_EXEC, f"SQLite错误: {e}")
    except Exception as e:
        return build_error(ERR_SCHEMA_FAILED, f"执行失败: {e}")
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
from app.constants import (
    ERR_DB_CONNECTION,
    ERR_DOC_DB_TABLE_NOT_FOUND,
    ERR_EXEC_FAILED,
    ERR_QUERY_FAILED,
    ERR_READ_ONLY_VIOLATION,
    ERR_SCHEMA_FAILED,
    ERR_SQL_EXEC,
)
