# -*- coding: utf-8 -*-
"""
Support Tool Schema - 已废弃的参数模型

【2026-05-18 小沈】所有Schema已废弃，保留空壳以避免import错误。
实际参数模型已迁移到对应分类的schema文件中。

Author: 小沈 - 2026-05-02, 废弃清理 2026-05-18
"""

from pydantic import BaseModel, Field


class CheckDbExistsInput(BaseModel):
    """check_db_exists 输入参数 - 已废弃，请使用 toolhelper.db_helper"""
    db_path: str = Field(..., description="数据库文件路径")


class GetTableSchemaInput(BaseModel):
    """get_table_schema 输入参数 - 已废弃，请使用 database.get_db_schema"""
    db_path: str = Field(..., description="数据库文件路径")
    table_name: str = Field(..., description="要查询的表名称")


class ValidateUrlInput(BaseModel):
    """validate_url 输入参数 - 已废弃，请使用 toolhelper.network_helper"""
    url: str = Field(..., description="要验证的URL")


class BeginTransactionInput(BaseModel):
    """begin_transaction 输入参数 - 已废弃"""
    pass


class CommitTransactionInput(BaseModel):
    """commit_transaction 输入参数 - 已废弃"""
    transaction_id: str = Field(..., description="事务ID")


class RollbackTransactionInput(BaseModel):
    """rollback_transaction 输入参数 - 已废弃"""
    transaction_id: str = Field(..., description="事务ID")


class CheckNetworkConnectivityInput(BaseModel):
    """check_network_connectivity 输入参数 - 已废弃"""
    pass


__all__ = [
    "CheckDbExistsInput",
    "GetTableSchemaInput",
    "ValidateUrlInput",
    "BeginTransactionInput",
    "CommitTransactionInput",
    "RollbackTransactionInput",
    "CheckNetworkConnectivityInput",
]
