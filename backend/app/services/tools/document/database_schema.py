# -*- coding: utf-8 -*-
# DATABASE Schema - Database Tools Pydantic Models
# 最后更新: 2026-05-08 小沈 小健 — 全部description改为中文 + "默认为X"格式
# 【2026-05-19 小沈】参数精简：QuerySqlInput 7→6(砍output_format)，ExecuteSqlInput 7→6(砍affected_rows_check)，GetDbSchemaInput 8→6(砍output_format+include_details)

from typing import Optional, Literal
from pydantic import BaseModel, Field


class QuerySqlInput(BaseModel):
    """query_sql 工具输入参数 - 小沈 2026-05-19 参数精简7→6(砍output_format)"""
    sql: str = Field(
        ...,
        description="SQL 查询语句。工具强制只读：仅允许 SELECT/SHOW/DESCRIBE，写入操作返回错误。必填参数"
    )
    limit: int = Field(
        default=50, ge=1, le=10000,
        description="最大返回行数，防止上下文爆炸。默认为50"
    )
    timeout: int = Field(
        default=15000, ge=1000, le=120000,
        description="超时毫秒数。默认为15000（15秒）"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db"
    )


class ExecuteSqlInput(BaseModel):
    """execute_sql 工具输入参数 - 小沈 2026-05-19 参数精简7→6(砍affected_rows_check)"""
    sql: str = Field(
        ...,
        description="SQL 写入语句。支持 INSERT/UPDATE/DELETE/DDL。必填参数"
    )
    dry_run: bool = Field(
        default=False,
        description="预检模式。True=只检查不执行。当SQL含DROP/TRUNCATE/DELETE且无WHERE时Agent强制设True。默认False"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=120000,
        description="超时毫秒数。默认为30000（30秒）"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db"
    )


class GetDbSchemaInput(BaseModel):
    """get_db_schema 工具输入参数 - 小沈 2026-05-19 参数精简8→6(砍output_format+include_details)"""
    db_name: Optional[str] = Field(
        default=None,
        description="目标数据库名称。默认为当前连接数据库"
    )
    table_name: Optional[str] = Field(
        default=None,
        description="指定表名，仅获取该表结构。不传则获取全库所有表结构。与filter_pattern互斥，table_name优先"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="表名过滤模式，支持SQL LIKE语法如user%"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db"
    )


__all__ = ["QuerySqlInput", "ExecuteSqlInput", "GetDbSchemaInput"]
