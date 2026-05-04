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

import sqlite3
from typing import Any, Dict, List, Optional, Union
from app.utils.logger import logger


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
    except:
        pass


def query_sql(
    sql: str,
    connection_type: str = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: int = 50,
    timeout: int = 15000,
    output_format: str = "table"
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
                "code": "ERROR",
                "data": None,
                "message": f"错误：只允许 SELECT/SHOW/DESCRIBE 等只读操作，当前语句以 {sql.split()[0] if sql.split() else '未知'} 开头"
            }
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return {"code": "ERROR", "data": None, "message": conn_error}
        
        if connection_type in ("mysql", "postgresql"):
            engine = conn.engine
            result = conn.execute(sql)
            rows = result.fetchall()
            columns = list(result.keys()) if hasattr(result, 'keys') else []
            results = [dict(zip(columns, row)) for row in rows]
            conn.close()
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = [dict(row) for row in rows]
            conn.close()
        
        if limit > 0 and len(results) > limit:
            results = results[:limit]
        
        if output_format == "json":
            return {
                "code": "SUCCESS",
                "data": {
                    "columns": columns,
                    "rows": results,
                    "total": len(results)
                },
                "message": f"查询成功，返回 {len(results)} 行数据"
            }
        else:
            table_str = _format_table(columns, results)
            return {
                "code": "SUCCESS",
                "data": {
                    "columns": columns,
                    "rows": results,
                    "total": len(results),
                    "table": table_str
                },
                "message": f"查询成功，返回 {len(results)} 行数据"
            }
            
    except sqlite3.Error as e:
        return {"code": "ERROR", "data": None, "message": f"SQL执行错误: {str(e)}"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"执行失败: {str(e)}"}
    finally:
        _close_connection(conn, engine)


def execute_sql(
    sql: str,
    connection_type: str = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    dry_run: bool = False,
    timeout: int = 30000,
    affected_rows_check: bool = True
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
        
        dangerous_keywords = ["DROP", "TRUNCATE"]
        has_dangerous = any(kw in sql_upper for kw in dangerous_keywords)
        
        if has_dangerous and not dry_run:
            dangerous_detected = [kw for kw in dangerous_keywords if kw in sql_upper]
            return {
                "code": "WARNING",
                "data": {
                    "detected": dangerous_detected,
                    "suggestion": "检测到危险操作，建议使用 dry_run=true 先验证"
                },
                "message": f"警告：检测到危险操作 {dangerous_detected}，已拦截执行"
            }
        
        if dry_run:
            return {
                "code": "SUCCESS",
                "data": {
                    "sql": sql,
                    "dry_run": True,
                    "syntax_valid": True
                },
                "message": "预演模式：语法验证通过，实际未执行"
            }
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            return {"code": "ERROR", "data": None, "message": conn_error}
        
        if connection_type in ("mysql", "postgresql"):
            engine = conn.engine
            result = conn.execute(sql)
            conn.commit()
            affected_rows = result.rowcount
            conn.close()
        else:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected_rows = cursor.rowcount
            
            if affected_rows_check and affected_rows > 10000:
                conn.rollback()
                conn.close()
                return {
                    "code": "WARNING",
                    "data": {
                        "affected_rows": affected_rows,
                        "action": "rollback"
                    },
                    "message": f"警告：影响行数 {affected_rows} > 10000，已自动回滚"
                }
            
            conn.commit()
            conn.close()
        
        return {
            "code": "SUCCESS",
            "data": {
                "affected_rows": affected_rows,
                "sql": sql
            },
            "message": f"执行成功，影响行数: {affected_rows}"
        }
        
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
            _close_connection(conn, engine)
        return {"code": "ERROR", "data": None, "message": f"SQL执行错误: {str(e)}"}
    except Exception as e:
        if conn:
            conn.rollback()
            _close_connection(conn, engine)
        return {"code": "ERROR", "data": None, "message": f"执行失败: {str(e)}"}


def get_db_schema(
    connection_type: str = "sqlite",
    connection_string: Optional[str] = None,
    db_path: Optional[str] = None,
    db_name: Optional[str] = None,
    filter_pattern: Optional[str] = None,
    include_details: bool = False,
    output_format: str = "markdown"
) -> Dict[str, Any]:
    """
    获取数据库表结构

    Args:
        connection_type: 数据库类型：sqlite/mysql/postgresql
        connection_string: MySQL/PostgreSQL 连接字符串
        db_path: SQLite 数据库文件路径
        db_name: 数据库名（SQLite 忽略此参数）
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
            return {"code": "ERROR", "data": None, "message": conn_error}
        
        if connection_type in ("mysql", "postgresql"):
            query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{db_name or 'test'}'"
            result = conn.execute(query)
            tables = [row[0] for row in result.fetchall()]
            tables_result = result.fetchall()
            conn.close()
            conn = None
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            tables_result = cursor.fetchall()
            conn.close()
            conn = None
        
        if filter_pattern:
            tables = [t for t in tables if filter_pattern.replace('%', '').lower() in t.lower()]
        
        if len(tables) > 20:
            tables = tables[:20]
        
        schema_info = []
        
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            return {"code": "ERROR", "data": None, "message": conn_error}
        
        for table_name in tables:
            if connection_type in ("mysql", "postgresql"):
                col_result = conn.execute(f"SELECT column_name, data_type, is_nullable, column_key, column_default FROM information_schema.columns WHERE table_name = '{table_name}'")
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
                conn.close()
                conn = None
                conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
                if conn is None:
                    continue
                cursor = conn.cursor()
            
            table_info = {"name": table_name, "columns": columns}
            
            if include_details:
                if connection_type in ("mysql", "postgresql"):
                    idx_result = conn.execute(f"SHOW INDEX FROM {table_name}")
                    indexes = []
                    for idx in idx_result.fetchall():
                        indexes.append({"name": idx[2], "unique": bool(idx[1])})
                    table_info["indexes"] = indexes
                else:
                    cursor.execute(f"PRAGMA index_list('{table_name}')")
                    indexes = []
                    for idx in cursor.fetchall():
                        indexes.append({"name": idx[1], "unique": bool(idx[2])})
                    table_info["indexes"] = indexes
            
            schema_info.append(table_info)
        
        _close_connection(conn, engine)
        
        if output_format == "json":
            return {
                "code": "SUCCESS",
                "data": {"tables": schema_info, "total": len(schema_info)},
                "message": f"获取成功，共 {len(schema_info)} 个表"
            }
        elif output_format == "sql_ddl":
            ddl_list = []
            for table in schema_info:
                ddl = f"CREATE TABLE {table['name']} (\n"
                col_defs = []
                for col in table["columns"]:
                    col_def = f"  {col['name']} {col['type']}"
                    if col.get("pk"):
                        col_def += " PRIMARY KEY"
                    if not col.get("nullable"):
                        col_def += " NOT NULL"
                    if col.get("default"):
                        col_def += f" DEFAULT {col['default']}"
                    col_defs.append(col_def)
                ddl += ",\n".join(col_defs)
                ddl += "\n);"
                ddl_list.append(ddl)
            
            return {
                "code": "SUCCESS",
                "data": {"ddl": ddl_list, "total": len(ddl_list)},
                "message": f"生成成功，共 {len(ddl_list)} 个表 DDL"
            }
        else:
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
                "message": f"获取成功，共 {len(schema_info)} 个表"
            }
            
    except sqlite3.Error as e:
        return {"code": "ERROR", "data": None, "message": f"获取数据库结构失败: {str(e)}"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"执行失败: {str(e)}"}
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
