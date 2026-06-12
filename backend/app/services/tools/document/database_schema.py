# -*- coding: utf-8 -*-
# DATABASE Schema - Database Tools Pydantic Models

from typing import Optional, Literal
from pydantic import BaseModel, Field


class QuerySqlInput(BaseModel):
    sql: str = Field(
        ...,
        description="SQL 查询语句。工具强制只读:仅允许 SELECT/SHOW/DESCRIBE,写入操作返回错误。必填参数"
    )
    limit: int = Field(
        default=50, ge=1, le=10000,
        description="最大返回行数,防止上下文爆炸。默认为50"
    )
    timeout: int = Field(
        default=15000, ge=1000, le=120000,
        description="超时毫秒数。默认为15000(15秒)"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例:D:/data/app.db"
    )


class ExecuteSqlInput(BaseModel):
    sql: str = Field(
        ...,
        description="SQL 写入语句。支持 INSERT/UPDATE/DELETE/DDL。必填参数"
    )
    dry_run: bool = Field(
        default=False,
        description="预检模式。True=仅校验语法不执行,返回syntax_valid=True。默认False。注意:检测到危险操作(DROP/TRUNCATE/ALTER/DELETE无WHERE等)时工具自动拦截返回WARNING,与dry_run无关"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=120000,
        description="超时毫秒数。默认为30000(30秒)"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例:D:/data/app.db"
    )


class GetDbSchemaInput(BaseModel):
    db_name: Optional[str] = Field(
        default=None,
        description="目标数据库名称。默认为当前连接数据库"
    )
    table_name: Optional[str] = Field(
        default=None,
        description="指定表名,仅获取该表结构。不传则获取全库所有表结构。与filter_pattern互斥,table_name优先"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="表名过滤模式,支持SQL LIKE语法如user%"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径。示例:D:/data/app.db"
    )


__all__ = ["QuerySqlInput", "ExecuteSqlInput", "GetDbSchemaInput"]
