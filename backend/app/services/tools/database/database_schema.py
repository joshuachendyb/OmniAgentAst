# -*- coding: utf-8 -*-
# DATABASE Schema - Database Tools Pydantic Models

from typing import Optional
from pydantic import BaseModel, Field


class QuerySqlInput(BaseModel):
    """query_sql tool input - execute read-only SQL query
    
    Args from doc 7.1.2:
    - sql: SQL query statement (required)
    - limit: result row limit (optional), default 50
    - timeout: timeout ms (optional), default 15000
    - output_format: output format (optional), default table
    - connection_type: database type (optional), default sqlite
    - connection_string: MySQL/PostgreSQL connection string (optional)
    - db_path: SQLite database file path (optional)
    """
    sql: str = Field(
        ...,
        description="SQL query statement (required). Tool enforces read-only: SELECT/SHOW/DESCRIBE. Returns error for write ops."
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=10000,
        description="Max result rows (optional), default 50. Prevents context explosion. Agent bypasses if SQL has LIMIT or LLM says all"
    )
    timeout: int = Field(
        default=15000,
        ge=1000,
        le=120000,
        description="Timeout ms (optional), default 15000. Agent auto-triggers EXPLAIN if timeout or >5s, never blocks"
    )
    output_format: str = Field(
        default="table",
        description="Output format (optional), default table. Values: table (human), json (structured). Agent auto-switches"
    )
    connection_type: str = Field(
        default="sqlite",
        description="Database type (optional). Values: sqlite (default), mysql, postgresql. Agent auto-detects from connection_string"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL connection string (optional). Example: user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite database file path (optional). Example: D:/data/app.db"
    )


class ExecuteSqlInput(BaseModel):
    """execute_sql tool input - execute write SQL
    
    Args from doc 7.1.2:
    - sql: SQL write statement (required)
    - dry_run: dry run mode (optional), default False
    - timeout: timeout ms (optional), default 30000
    - affected_rows_check: check affected rows (optional), default True
    - connection_type: database type (optional), default sqlite
    - connection_string: MySQL/PostgreSQL connection string (optional)
    - db_path: SQLite database file path (optional)
    """
    sql: str = Field(
        ...,
        description="SQL write statement (required). Supports INSERT/UPDATE/DELETE/DDL. Tool only supports single-statement auto-commit"
    )
    dry_run: bool = Field(
        default=False,
        description="Dry run mode (optional), default False. If SQL has DROP/TRUNCATE/DELETE without WHERE, Agent forces True"
    )
    timeout: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Timeout ms (optional), default 30000. Write ops strictly monitored, auto-rollback on timeout"
    )
    affected_rows_check: bool = Field(
        default=True,
        description="Check affected rows (optional), default True. Blocks only when affected >10000 without confirm"
    )
    connection_type: str = Field(
        default="sqlite",
        description="Database type (optional). Values: sqlite (default), mysql, postgresql. Agent auto-detects from connection_string"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL connection string (optional). Example: user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite database file path (optional). Example: D:/data/app.db"
    )


class GetDbSchemaInput(BaseModel):
    """get_db_schema tool input - get database schema
    
    Args from doc 7.1.2:
    - db_name: target database name (optional)
    - filter_pattern: table filter pattern (optional)
    - include_details: include details (optional), default False  
    - output_format: output format (optional), default markdown
    - connection_type: database type (optional), default sqlite
    - connection_string: MySQL/PostgreSQL connection string (optional)
    - db_path: SQLite database file path (optional)
    """
    db_name: Optional[str] = Field(
        default=None,
        description="Target database name (optional). Default None reads current connection. Agent auto-switches if specified"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="Table filter pattern (optional). Supports SQL LIKE syntax like user%. Agent auto-injects LIKE filter"
    )
    include_details: bool = Field(
        default=False,
        description="Include detailed index/foreign key/constraint info (optional), default False"
    )
    output_format: str = Field(
        default="markdown",
        description="Output format (optional), default markdown. Values: markdown, json, sql_ddl. Agent auto-switches"
    )
    connection_type: str = Field(
        default="sqlite",
        description="Database type (optional). Values: sqlite (default), mysql, postgresql. Agent auto-detects from connection_string"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL connection string (optional). Example: user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite database file path (optional). Example: D:/data/app.db"
    )
    dry_run: bool = Field(
        default=False,
        description="Dry run mode (optional), default False. If SQL has DROP/TRUNCATE/DELETE without WHERE, Agent forces True"
    )
    timeout: int = Field(
        default=30000,
        ge=1000,
        le=120000,
        description="Timeout ms (optional), default 30000. Write ops strictly monitored, auto-rollback on timeout"
    )
    affected_rows_check: bool = Field(
        default=True,
        description="Check affected rows (optional), default True. Blocks only when affected >10000 without confirm"
    )


class GetDbSchemaInput(BaseModel):
    """get_db_schema tool input - get database schema
    
    Args from doc 7.1.2:
    - db_name: target database name (optional)
    - filter_pattern: table filter pattern (optional)
    - include_details: include details (optional), default False  
    - output_format: output format (optional), default markdown
    - connection_type: database type (optional), default sqlite
    - connection_string: MySQL/PostgreSQL connection string (optional)
    - db_path: SQLite database file path (optional)
    """
    db_name: Optional[str] = Field(
        default=None,
        description="Target database name (optional). Default None reads current connection. Agent auto-switches if specified"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="Table filter pattern (optional). Supports SQL LIKE syntax like user%. Agent auto-injects LIKE filter"
    )
    include_details: bool = Field(
        default=False,
        description="Include detailed index/foreign key/constraint info (optional), default False. Max 20 tables to prevent context explosion"
    )
    output_format: str = Field(
        default="markdown",
        description="Output format (optional), default markdown. Values: markdown, json, sql_ddl. Agent auto-switches"
    )
    connection_type: str = Field(
        default="sqlite",
        description="Database type (optional). Values: sqlite (default), mysql, postgresql. Agent auto-detects from connection_string"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL connection string (optional). Example: user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite database file path (optional). Example: D:/data/app.db"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="Table filter pattern (optional). Supports SQL LIKE syntax like user%. Agent auto-injects LIKE filter"
    )
    include_details: bool = Field(
        default=False,
        description="Include detailed index/foreign key/constraint info (optional), default False"
    )
    output_format: str = Field(
        default="markdown",
        description="Output format (optional), default markdown. Values: markdown, json, sql_ddl. Agent auto-switches"
    )


__all__ = ["QuerySqlInput", "ExecuteSqlInput", "GetDbSchemaInput"]
