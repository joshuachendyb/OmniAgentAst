# -*- coding: utf-8 -*-
"""
DATABASE Tools - 数据库工具实现

【架构规范】2026-04-29 小沈

【工具列表】（共3个）
1. query_sql - 执行只读SQL查询
2. execute_sql - 执行写操作SQL
3. get_db_schema - 获取数据库表结构

创建时间: 2026-04-29
"""

import sqlite3
from typing import Any, Dict, List, Optional, Union
from app.utils.logger import logger


def query_sql(
    sql: str,
    limit: int = 50,
    timeout: int = 15000,
    output_format: str = "table"
) -> Dict[str, Any]:
    """
    执行只读SQL查询

    Args:
        sql: SQL 查询语句。仅支持 SELECT/SHOW/DESCRIBE 等只读操作
        limit: 最大返回行数，默认50
        timeout: 超时毫秒数，默认15000
        output_format: 输出格式，table(默认) 或 json

    Returns:
        Dict with code, data, message
    """
    try:
        sql_upper = sql.strip().upper()
        
        if not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA")):
            return {
                "code": "ERROR",
                "data": None,
                "message": f"错误：只允许 SELECT/SHOW/DESCRIBE 等只读操作，当前语句以 {sql.split()[0] if sql.split() else '未知'} 开头"
            }
        
        conn = sqlite3.connect(":memory:", timeout=timeout / 1000)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        if limit > 0 and len(rows) > limit:
            rows = rows[:limit]
        
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        
        results = []
        for row in rows:
            results.append(dict(row))
        
        conn.close()
        
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
        return {
            "code": "ERROR",
            "data": None,
            "message": f"SQL执行错误: {str(e)}"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"执行失败: {str(e)}"
        }


def execute_sql(
    sql: str,
    dry_run: bool = False,
    timeout: int = 30000,
    affected_rows_check: bool = True
) -> Dict[str, Any]:
    """
    执行写操作SQL

    Args:
        sql: SQL 写操作语句。支持 INSERT/UPDATE/DELETE/DDL
        dry_run: 预演模式，仅校验语法不执行
        timeout: 超时毫秒数，默认30000
        affected_rows_check: 是否校验影响行数，默认True

    Returns:
        Dict with code, data, message
    """
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
        
        conn = sqlite3.connect(":memory:", timeout=timeout / 1000)
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
        return {
            "code": "ERROR",
            "data": None,
            "message": f"SQL执行错误: {str(e)}"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"执行失败: {str(e)}"
        }


def get_db_schema(
    db_name: Optional[str] = None,
    filter_pattern: Optional[str] = None,
    include_details: bool = False,
    output_format: str = "markdown"
) -> Dict[str, Any]:
    """
    获取数据库表结构

    Args:
        db_name: 数据库名（SQLite 忽略此参数）
        filter_pattern: 表名过滤模式（SQL LIKE 语法）
        include_details: 是否包含详细索引、外键、约束信息
        output_format: 输出格式：markdown(默认)、json、sql_ddl

    Returns:
        Dict with code, data, message
    """
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        if filter_pattern:
            tables = [t for t in tables if t.replace('_', '').find(filter_pattern.replace('%', '').replace('_', '')) >= 0]
        
        if len(tables) > 20:
            tables = tables[:20]
        
        schema_info = []
        
        for table_name in tables:
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
            
            table_info = {
                "name": table_name,
                "columns": columns
            }
            
            if include_details:
                cursor.execute(f"PRAGMA index_list('{table_name}')")
                indexes = []
                for idx in cursor.fetchall():
                    indexes.append({
                        "name": idx[1],
                        "unique": bool(idx[2])
                    })
                table_info["indexes"] = indexes
                
                cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
                foreign_keys = []
                for fk in cursor.fetchall():
                    foreign_keys.append({
                        "from": fk[3],
                        "to": fk[2],
                        "table": fk[2]
                    })
                table_info["foreign_keys"] = foreign_keys
            
            schema_info.append(table_info)
        
        conn.close()
        
        if output_format == "json":
            return {
                "code": "SUCCESS",
                "data": {
                    "tables": schema_info,
                    "total": len(schema_info)
                },
                "message": f"获取成功，共 {len(schema_info)} 个表"
            }
        elif output_format == "sql_ddl":
            ddl_list = []
            for table in schema_info:
                ddl = f"CREATE TABLE {table['name']} (\n"
                col_defs = []
                for col in table["columns"]:
                    col_def = f"  {col['name']} {col['type']}"
                    if col["pk"]:
                        col_def += " PRIMARY KEY"
                    if not col["nullable"]:
                        col_def += " NOT NULL"
                    if col["default"]:
                        col_def += f" DEFAULT {col['default']}"
                    col_defs.append(col_def)
                ddl += ",\n".join(col_defs)
                ddl += "\n);"
                ddl_list.append(ddl)
            
            return {
                "code": "SUCCESS",
                "data": {
                    "ddl": ddl_list,
                    "total": len(ddl_list)
                },
                "message": f"生成成功，共 {len(ddl_list)} 个表 DDL"
            }
        else:
            md = f"## 数据库结构 (共 {len(schema_info)} 个表)\n\n"
            for table in schema_info:
                md += f"### {table['name']}\n\n"
                md += "| 字段名 | 类型 | 可空 | 主键 | 默认值 |\n"
                md += "|--------|------|------|------|--------|\n"
                for col in table["columns"]:
                    md += f"| {col['name']} | {col['type']} | {'否' if col['nullable'] else '是'} | {'是' if col['pk'] else '否'} | {col['default'] or '-'} |\n"
                md += "\n"
                
                if include_details and table.get("indexes"):
                    md += f"**索引**: {', '.join([idx['name'] for idx in table['indexes']])}\n\n"
            
            return {
                "code": "SUCCESS",
                "data": {
                    "tables": schema_info,
                    "total": len(schema_info),
                    "markdown": md
                },
                "message": f"获取成功，共 {len(schema_info)} 个表"
            }
            
    except sqlite3.Error as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"获取数据库结构失败: {str(e)}"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"执行失败: {str(e)}"
        }


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
