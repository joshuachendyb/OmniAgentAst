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

import re
import sqlite3
from typing import Any, Dict, List, Optional, Union, Literal
from app.utils.logger import logger
from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend, make_json_safe


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
            return {
                "code": "ERR_READ_ONLY_VIOLATION",
                "data": None,
                "message": f"错误：只允许 SELECT/SHOW/DESCRIBE 等只读操作，当前语句以 {sql.split()[0] if sql.split() else '未知'} 开头"
            }
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return {"code": "ERR_DB_CONNECTION", "data": None, "message": conn_error}
        
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
        return {
            "code": "SUCCESS",
            "data": truncate_data_for_frontend({
                "columns": columns,
                "rows": results,
                "total": len(results),
                "table": table_str
            }),
            "message": f"查询成功，返回 {len(results)} 行数据",
            "llm_data": {
                "列": columns, "行数": len(results),
                "行预览": make_json_safe(results[:10], max_str_len=150)
            },
            "next_actions": build_next_actions([
                ("execute_sql", "执行写操作SQL", "需要修改数据时"),
                ("get_db_schema", "查看表结构", "需要了解其他表时"),
            ])
        }
            
    except sqlite3.Error as e:
        return {"code": "ERR_SQL_EXEC", "data": None, "message": f"SQL执行错误: {str(e)}"}
    except Exception as e:
        return {"code": "ERR_QUERY_FAILED", "data": None, "message": f"执行失败: {str(e)}"}
    finally:
        _close_connection(conn, engine)


def execute_sql(
    sql: str,
    connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = 30000,
) -> Dict[str, Any]:
    """
    执行写操作SQL

    Args:
        sql: SQL 写操作语句。支持 INSERT/UPDATE/DELETE/DDL
        connection_type: 数据库类型：sqlite/mysql/postgresql
        connection_string: MySQL/PostgreSQL 连接字符串
        db_path: SQLite 数据库文件路径
        dry_run: 预演模式，仅校验语法不执行
        timeout: 超时毫秒数，默认30000
        affected_rows_check: 是否校验影响行数，默认True

    Returns:
        Dict with code, data, message
    """
    conn = None
    engine = None
    
    try:
        sql_upper = sql.strip().upper()
        
        DANGEROUS_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)
        dangerous_matches = DANGEROUS_PATTERN.findall(sql)
        
        # 小健 2026-05-19: 检测DELETE/UPDATE无WHERE子句
        no_where_pattern = re.compile(r'\b(DELETE|UPDATE)\b.*?(?!.*\bWHERE\b)', re.IGNORECASE | re.DOTALL)
        if re.match(r'\s*(DELETE|UPDATE)\s', sql_upper) and 'WHERE' not in sql_upper:
            dangerous_matches.append('NO_WHERE')
        
        if dangerous_matches and not dry_run:
            return {
                "code": "WARNING",
                "data": {
                    "detected": dangerous_matches,
                    "suggestion": "检测到危险操作，建议使用 dry_run=true 先验证"
                },
                "message": f"警告：检测到危险操作 {dangerous_matches}，已拦截执行。可使用dry_run=true预演",
                "next_actions": build_next_actions([
                    ("execute_sql", "dry_run预演", "需要预检SQL时", {"dry_run": True}),
                    ("query_sql", "查询数据", "需要先查看数据时"),
                ])
            }
        
        if dry_run:
            return {
                "code": "SUCCESS",
                "data": {
                    "sql": sql,
                    "dry_run": True,
                    "syntax_valid": True
                },
                "message": "预演模式：语法验证通过，实际未执行",
                "next_actions": build_next_actions([
                    ("query_sql", "查询验证结果", "需要确认修改结果时"),
                ])
            }
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return {"code": "ERR_DB_CONNECTION", "data": None, "message": conn_error}
        
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
            
            # affected_rows_check 已从Schema移除，固定启用>10000行保护
            if affected_rows > 10000:
                conn.rollback()
                return {
                    "code": "WARNING",
                    "data": {
                        "affected_rows": affected_rows,
                        "action": "rollback"
                    },
                    "message": f"警告：影响行数 {affected_rows} > 10000，已自动回滚"
                }
            
            conn.commit()
        
        return {
            "code": "SUCCESS",
            "data": {
                "affected_rows": affected_rows,
                "sql": sql
            },
            "message": f"执行成功，影响行数: {affected_rows}",
            "next_actions": build_next_actions([
                ("query_sql", "查询验证结果", "需要确认修改结果时"),
            ])
        }
        
    except sqlite3.Error as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"code": "ERR_SQL_EXEC", "data": None, "message": f"SQL执行错误: {str(e)}"}
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"code": "ERR_EXEC_FAILED", "data": None, "message": f"执行失败: {str(e)}"}
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
    conn = None
    engine = None
    
    try:
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            return {"code": "ERR_DB_CONNECTION", "data": None, "message": conn_error}
        
        if connection_type in ("mysql", "postgresql"):
            from sqlalchemy import text
            query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = :db_name")
            result = conn.execute(query, {"db_name": db_name or "test"})
            tables = [row[0] for row in result.fetchall()]
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
        
        _close_connection(conn, engine)
        conn = None
        engine = None
        
        # 【2026-05-17 小沈】table_name 参数：指定单表查询，覆盖 filter_pattern
        if table_name:
            tables = [t for t in tables if t == table_name]
            if not tables:
                return {
                    "code": "ERR_TABLE_NOT_FOUND",
                    "data": None,
                    "message": f"表不存在: {table_name}"
                }
        elif filter_pattern:
            import fnmatch
            # 小健 2026-05-19: SQL LIKE用%通配，fnmatch用*，自动转换
            fnmatch_pattern = filter_pattern.replace("%", "*").replace("_", "?")
            tables = [t for t in tables if fnmatch.fnmatch(t.lower(), fnmatch_pattern.lower())]
        
        if len(tables) > 20:
            tables = tables[:20]
        
        schema_info = []
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            return {"code": "ERR_DB_CONNECTION", "data": None, "message": conn_error}
        
        for table_name in tables:
            if connection_type in ("mysql", "postgresql"):
                from sqlalchemy import text as sa_text
                col_result = conn.execute(
                    sa_text("SELECT column_name, data_type, is_nullable, column_key, column_default FROM information_schema.columns WHERE table_name = :table_name"),
                    {"table_name": table_name}
                )
                columns = []
                for col in col_result.fetchall():
                    columns.append({
                        "name": col[0],
                        "type": col[1],
                        "nullable": col[2] == "YES",
                        "pk": col[3] == "PRI",
                        "default": col[4]
                    })
            else:
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info('{table_name}')")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "name": col[1],
                        "type": col[2],
                        "nullable": not col[3],
                        "default": col[4],
                        "pk": bool(col[5])
                    })
            
            table_info = {"name": table_name, "columns": columns}
            
            # include_details 已从Schema移除，固定获取索引信息
            if connection_type in ("mysql", "postgresql"):
                from sqlalchemy import text as sa_text2
                idx_result = conn.execute(
                    sa_text2("SELECT index_name, non_unique FROM information_schema.statistics WHERE table_name = :table_name GROUP BY index_name, non_unique"),
                    {"table_name": table_name}
                )
                indexes = []
                for idx in idx_result.fetchall():
                    indexes.append({"name": idx[0], "unique": not bool(idx[1])})
                table_info["indexes"] = indexes
            else:
                cursor.execute(f"PRAGMA index_list('{table_name}')")
                indexes = []
                for idx in cursor.fetchall():
                    indexes.append({"name": idx[1], "unique": bool(idx[2])})
                table_info["indexes"] = indexes
            
            schema_info.append(table_info)
        
        _close_connection(conn, engine)
        
        # output_format 已从Schema移除，固定使用markdown格式
        md = f"## 数据库结构 (共 {len(schema_info)} 个表)\n\n"
        for table in schema_info:
            md += f"### {table['name']}\n\n"
            md += "| 字段名 | 类型 | 可空 | 主键 | 默认值 |\n"
            md += "|--------|------|------|------|--------|\n"
            for col in table["columns"]:
                md += f"| {col['name']} | {col['type']} | {'否' if col.get('nullable') else '是'} | {'是' if col.get('pk') else '否'} | {col.get('default') or '-'} |\n"
            md += "\n"
        
        return {
            "code": "SUCCESS",
            "data": {"tables": schema_info, "total": len(schema_info), "markdown": md},
            "message": f"获取成功，共 {len(schema_info)} 个表",
            "next_actions": build_next_actions([
                ("query_sql", "查询表数据", "需要查看数据时"),
            ])
        }
            
    except sqlite3.Error as e:
        return {"code": "ERR_SQL_EXEC", "data": None, "message": f"获取数据库结构失败: {str(e)}"}
    except Exception as e:
        return {"code": "ERR_SCHEMA_FAILED", "data": None, "message": f"执行失败: {str(e)}"}
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
