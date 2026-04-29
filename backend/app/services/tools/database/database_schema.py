# -*- coding: utf-8 -*-
"""
DATABASE Schema - 数据库工具 Pydantic 模型

【架构规范】2026-04-29 小沈

【工具列表】（共3个）
1. query_sql - 执行只读SQL查询
2. execute_sql - 执行写操作SQL
3. get_db_schema - 获取数据库表结构

创建时间: 2026-04-29
"""

from typing import Optional
from pydantic import BaseModel, Field


class QuerySqlInput(BaseModel):
    """query_sql 工具的输入参数 - 执行只读SQL查询"""
    sql: str = Field(
        description="SQL 查询语句。仅支持 SELECT/SHOW/DESCRIBE 等只读操作"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=10000,
        description="最大返回行数，默认50，防上下文爆炸"
    )
    timeout: int = Field(
        default=15000,
        ge=1000,
        le=120000,
        description="超时毫秒数，默认15000"
    )
    output_format: str = Field(
        default="table",
        description="输出格式：table(默认，人类可读)、json(结构化)"
    )


class ExecuteSqlInput(BaseModel):
    """execute_sql 工具的输入参数 - 执行写操作SQL"""
    sql: str = Field(
        description="SQL 写操作语句。支持 INSERT/UPDATE/DELETE/DDL，仅支持单语句自动提交"
    )
    dry_run: bool = Field(
        default=False,
        description="预演模式。若 SQL 含 DROP/TRUNCATE/DELETE 无 WHERE，强制开启仅校验语法"
    )
    timeout: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="超时毫秒数，默认30000。写操作严格监控，超时自动回滚"
    )
    affected_rows_check: bool = Field(
        default=True,
        description="是否校验影响行数。默认 true。仅当影响行数 >10000 时拦截"
    )


class GetDbSchemaInput(BaseModel):
    """get_db_schema 工具的输入参数 - 获取数据库表结构"""
    db_name: Optional[str] = Field(
        default=None,
        description="目标数据库名。默认 null（读取当前连接配置）"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="表名过滤模式（支持 SQL LIKE 语法，如 'user%'）"
    )
    include_details: bool = Field(
        default=False,
        description="是否包含详细索引、外键、约束信息。默认 false"
    )
    output_format: str = Field(
        default="markdown",
        description="输出格式：markdown(默认)、json、sql_ddl"
    )
