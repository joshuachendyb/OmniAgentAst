# -*- coding: utf-8 -*-
# DATABASE Schema - Database Tools Pydantic Models
# 最后更新: 2026-05-08 小沈 小健 — 全部description改为中文 + "默认为X"格式

from typing import Optional
from pydantic import BaseModel, Field


class QuerySqlInput(BaseModel):
    """query_sql 工具输入参数 - 执行只读 SQL 查询"""
    sql: str = Field(
        ...,
        description="SQL 查询语句。工具强制只读：仅允许 SELECT/SHOW/DESCRIBE，写入操作返回错误。必填参数"
    )
    limit: int = Field(
        default=50, ge=1, le=10000,
        description="最大返回行数，防止上下文爆炸。Agent 在 SQL 已有 LIMIT 或用户要求全部时自动绕过限制。默认为50"
    )
    timeout: int = Field(
        default=15000, ge=1000, le=120000,
        description="超时毫秒数。超时或超过5秒时 Agent 自动触发 EXPLAIN。默认为15000（15秒）"
    )
    output_format: str = Field(
        default="table",
        description="输出格式。可选值：table（人类可读表格）、json（结构化数据）。Agent 自动切换。默认为table"
    )
    connection_type: str = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite、mysql、postgresql。Agent 从 connection_string 自动检测。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname。可选参数"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db。可选参数"
    )


class ExecuteSqlInput(BaseModel):
    """execute_sql 工具输入参数 - 执行写入 SQL"""
    sql: str = Field(
        ...,
        description="SQL 写入语句。支持 INSERT/UPDATE/DELETE/DDL，仅支持单语句自动提交。必填参数"
    )
    dry_run: bool = Field(
        default=False,
        description="预检模式。True=只检查不执行。当 SQL 含 DROP/TRUNCATE/DELETE 且无 WHERE 时 Agent 强制设为 True。默认为False"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=120000,
        description="超时毫秒数。写入操作严格监控，超时自动回滚。默认为30000（30秒）"
    )
    affected_rows_check: bool = Field(
        default=True,
        description="受影响行数检查。仅当影响行数超过10000且未经用户确认时阻塞。默认为True"
    )
    connection_type: str = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite、mysql、postgresql。Agent 自动检测。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname。可选参数"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db。可选参数"
    )


class GetDbSchemaInput(BaseModel):
    """get_db_schema 工具输入参数 - 获取数据库结构"""
    db_name: Optional[str] = Field(
        default=None,
        description="目标数据库名称。Agent 自动切换。默认为当前连接数据库"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="表名过滤模式，支持 SQL LIKE 语法如 user%。Agent 自动注入 LIKE 过滤。可选参数"
    )
    include_details: bool = Field(
        default=False,
        description="是否包含索引/外键/约束等详细信息。最多返回20张表防上下文爆炸。默认为False"
    )
    output_format: str = Field(
        default="markdown",
        description="输出格式。可选值：markdown、json、sql_ddl。Agent 自动切换。默认为markdown"
    )
    connection_type: str = Field(
        default="sqlite",
        description="数据库类型。可选值：sqlite、mysql、postgresql。Agent 自动检测。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例：user:pass@host:port/dbname。可选参数"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例：D:/data/app.db。可选参数"
    )


__all__ = ["QuerySqlInput", "ExecuteSqlInput", "GetDbSchemaInput"]
