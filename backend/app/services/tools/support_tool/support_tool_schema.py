# -*- coding: utf-8 -*-
"""
DB Helper 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【更新时间】2026-05-02 小沈 - 添加4个工具模型：BeginTransactionInput, CommitTransactionInput, RollbackTransactionInput, CheckNetworkConnectivityInput

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional


class CheckDbExistsInput(BaseModel):
    """check_db_exists 工具的输入参数"""
    db_path: str = Field(..., description="数据库文件路径。如 D:/data/app.db")


class GetTableSchemaInput(BaseModel):
    """get_table_schema 工具的输入参数"""
    db_path: str = Field(..., description="数据库文件路径")
    table_name: str = Field(..., description="要查询的表名称。如 users、orders - 小健 2026-05-06")


class ValidateUrlInput(BaseModel):
    """validate_url 工具的输入参数"""
    url: str = Field(..., description="要验证的URL。如 https://example.com")


class BeginTransactionInput(BaseModel):
    """begin_transaction 工具的输入参数"""
    # 无参数


class CommitTransactionInput(BaseModel):
    """commit_transaction 工具的输入参数"""
    transaction_id: str = Field(..., description="事务ID，由begin_transaction返回")


class RollbackTransactionInput(BaseModel):
    """rollback_transaction 工具的输入参数"""
    transaction_id: str = Field(..., description="事务ID，由begin_transaction返回")


class CheckNetworkConnectivityInput(BaseModel):
    """check_network_connectivity 工具的输入参数"""
    # 无参数


__all__ = [
    "CheckDbExistsInput",
    "GetTableSchemaInput",
    "ValidateUrlInput",
    "BeginTransactionInput",
    "CommitTransactionInput",
    "RollbackTransactionInput",
    "CheckNetworkConnectivityInput",
]
