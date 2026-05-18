# -*- coding: utf-8 -*-
"""
Support Tool 函数模块 - 向后兼容包装器（已废弃）

【2026-05-18 小沈】所有函数已迁移到 toolhelper/ 或 database/，
本模块仅保留向后兼容包装器，不注册任何LLM工具。

迁移去向：
- check_db_exists → toolhelper/db_helper.py
- get_table_schema → database/database_tools.py (get_db_schema)
- begin/commit/rollback_transaction → 已弃用
- check_network_connectivity → toolhelper/network_helper.py (_check_network)
- validate_url → toolhelper/network_helper.py (_validate_url)

Author: 小沈 - 2026-05-02, 废弃清理 2026-05-18
"""

import warnings
from typing import Dict, Any
from pathlib import Path


def check_db_exists(db_path: str) -> Dict[str, Any]:
    """检查数据库是否存在 - 向后兼容包装器
    【2026-05-18 小沈】实际实现已迁移到 toolhelper/db_helper.py
    """
    from app.services.tools.toolhelper.db_helper import check_db_exists as _impl
    return _impl(db_path)


def get_table_schema(db_path: str, table_name: str) -> Dict[str, Any]:
    """获取表结构 - 向后兼容包装器
    【2026-05-18 小沈】请使用 database_tools.get_db_schema(table_name=...) 代替
    """
    warnings.warn("get_table_schema已弃用，请使用get_db_schema(table_name=...)", DeprecationWarning, stacklevel=2)
    from app.services.tools.database.database_tools import get_db_schema
    return get_db_schema(db_path=db_path, table_name=table_name)


def begin_transaction() -> Dict[str, Any]:
    """开始事务 - 向后兼容包装器
    【2026-05-18 小沈】已弃用，请使用 execute_sql("BEGIN TRANSACTION")
    """
    warnings.warn("begin_transaction已弃用，请使用execute_sql('BEGIN TRANSACTION')", DeprecationWarning, stacklevel=2)
    import uuid
    tx_id = str(uuid.uuid4())[:8]
    return {"code": "SUCCESS", "data": {"transaction_id": tx_id}, "message": f"事务已开始: {tx_id}"}


def commit_transaction(transaction_id: str) -> Dict[str, Any]:
    """提交事务 - 向后兼容包装器
    【2026-05-18 小沈】已弃用，请使用 execute_sql("COMMIT")
    """
    warnings.warn("commit_transaction已弃用，请使用execute_sql('COMMIT')", DeprecationWarning, stacklevel=2)
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已提交: {transaction_id}"}


def rollback_transaction(transaction_id: str) -> Dict[str, Any]:
    """回滚事务 - 向后兼容包装器
    【2026-05-18 小沈】已弃用，请使用 execute_sql("ROLLBACK")
    """
    warnings.warn("rollback_transaction已弃用，请使用execute_sql('ROLLBACK')", DeprecationWarning, stacklevel=2)
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已回滚: {transaction_id}"}


def check_network_connectivity() -> Dict[str, Any]:
    """检查网络连通性 - 向后兼容包装器
    【2026-05-18 小沈】请使用 toolhelper/network_helper.py _check_network() 代替
    """
    from app.services.tools.toolhelper.network_helper import _check_network
    return _check_network()


def validate_url(url: str) -> Dict[str, Any]:
    """验证URL格式 - 向后兼容包装器
    【2026-05-18 小沈】请使用 toolhelper/network_helper.py _validate_url(url) 代替
    """
    from app.services.tools.toolhelper.network_helper import _validate_url
    result = _validate_url(url)
    if isinstance(result, dict) and "valid" in result:
        return {"code": "SUCCESS", "data": result, "message": "URL格式有效" if result["valid"] else "URL格式无效"}
    return result


__all__ = [
    "check_db_exists",
    "get_table_schema",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "check_network_connectivity",
    "validate_url",
]
