# -*- coding: utf-8 -*-
"""
get_db_schema — 获取数据库结构元数据
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import fnmatch
import sqlite3
import time as _time_mod
from typing import Any, Dict, List, Optional, Union, Literal

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error
from app.constants import (
    ERR_DB_CONNECTION,
    ERR_DOC_DB_TABLE_NOT_FOUND,
    ERR_SCHEMA_FAILED,
    ERR_SQL_EXEC,
)


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


def _get_tables(conn, connection_type: str, db_name: Optional[str]) -> List[str]:
    """获取表列表(2路SQL) — 小沈 2026-05-25"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = :db_name"), {"db_name": db_name or "test"})
        return [row[0] for row in result.fetchall()]
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return [row[0] for row in cursor.fetchall()]


def _get_columns(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取列信息(2路SQL) — 小沈 2026-05-25"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT column_name, data_type, is_nullable, column_key, column_default FROM information_schema.columns WHERE table_name=:t"), {"t": table_name})
        return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", "pk": r[3] == "PRI", "default": r[4]} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info('{table_name}')")
    return [{"name": r[1], "type": r[2], "nullable": not r[3], "default": r[4], "pk": bool(r[5])} for r in cursor.fetchall()]


def _get_indexes(conn, connection_type: str, table_name: str) -> List[Dict]:
    """获取索引信息(2路SQL) — 小沈 2026-05-25"""
    if connection_type in ("mysql", "postgresql"):
        from sqlalchemy import text
        result = conn.execute(text("SELECT index_name, non_unique FROM information_schema.statistics WHERE table_name=:t GROUP BY index_name, non_unique"), {"t": table_name})
        return [{"name": r[0], "unique": not bool(r[1])} for r in result]
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list('{table_name}')")
    return [{"name": r[1], "unique": bool(r[2])} for r in cursor.fetchall()]


def _filter_tables(tables: List[str], table_name: Optional[str], filter_pattern: Optional[str]) -> List[str]:
    """表名过滤:精确匹配优先,fnmatch降级,20表截断 — 小沈 2026-05-25"""
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
    """get_db_schema的llm_data构建函数 — 小健 2026-06-22"""
    table_names = table_names or []
    if exec_code == "error":
        return {
            "summary": f"获取数据库结构失败: {detail}" if detail else "获取数据库结构失败",
            "action": {"tool": "get_db_schema", "tool_zh": "获取结构", "target": "database", "params": {}},
            "status": {"exec_code": "error", "message": "获取失败", "code": err_code or ERR_DB_CONNECTION, "detail": detail, "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {},
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
    """获取数据库表结构 — 小健 2026-06-22 拆分独立文件"""
    conn = engine = None
    t0 = _time_mod.perf_counter()
    try:
        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_DB_CONNECTION, detail=conn_error, hint="请检查连接参数")
            return build_error(data={"error_detail": conn_error, "params": {"connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)

        tables = _get_tables(conn, connection_type, db_name)
        tables = _filter_tables(tables, table_name, filter_pattern)
        if table_name and not tables:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_DOC_DB_TABLE_NOT_FOUND, detail=f"表不存在: {table_name}", hint="请确认表名正确")
            return build_error(data={"error_detail": f"表不存在: {table_name}", "params": {"table_name": table_name}}, llm_data=llm_data)

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
        return build_error(data={"error_detail": str(e), "params": {"connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_get_db_schema_llm_data("error", duration_ms, err_code=ERR_SCHEMA_FAILED, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["get_db_schema"]