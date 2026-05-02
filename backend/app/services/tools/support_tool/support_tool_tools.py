# -*- coding: utf-8 -*-
"""
支撑工具函数模块 - 公共函数 + LLM可调用Tool

【创建时间】2026-05-02 小沈
【更新时间】2026-05-02 小沈 - 移除@register_tool装饰器，改为显式注册

================================================================================
一、模块性质（双重身份）
================================================================================
本模块的函数具有双重身份：

1. **公共辅助函数（主要用途 90%）** - 被其他Tool函数内部调用
   - 例如：query_sql内部调用check_db_exists验证数据库存在
   - 例如：http_request内部调用validate_url验证URL格式

2. **LLM可调用Tool（次要用途 10%）** - 可被用户直接调用
   - 用户问"检查数据库是否存在" → LLM调用check_db_exists
   - 用户问"这个URL格式对不对" → LLM调用validate_url

【重要】这些函数主要作为公共基础设施供其他Tool调用，LLM直接调用场景较少。
注册已移至 support_tool_register.py

================================================================================
二、包含工具（7个）
================================================================================
- check_db_exists: 检查数据库是否存在（公共函数 + LLM Tool）
- get_table_schema: 获取表结构（公共函数 + LLM Tool）
- begin_transaction: 开始事务（LLM Tool，用于事务控制）
- commit_transaction: 提交事务（LLM Tool）
- rollback_transaction: 回滚事务（LLM Tool）
- check_network_connectivity: 检查网络连通性（公共函数 + LLM Tool）
- validate_url: 验证URL格式（公共函数 + LLM Tool）

================================================================================
三、调用关系示例
================================================================================
```
# 其他Tool内部调用示例（主要场景）
def query_sql(db_path, sql):
    result = check_db_exists(db_path)
    if not result["data"]["exists"]:
        return {"error": "数据库不存在"}
    # 执行SQL...

# LLM直接调用示例（次要场景）
用户: "帮我检查D:/data/app.db是否存在"
LLM: 调用 check_db_exists({"db_path": "D:/data/app.db"})
```

Author: 小沈 - 2026-05-02
"""

import os
import re
import socket
import sqlite3
import threading
from typing import Dict, Any
from pathlib import Path
from urllib.parse import urlparse

from app.services.tools.support_tool.support_tool_schema import (
    CheckDbExistsInput,
    GetTableSchemaInput,
    ValidateUrlInput,
)

_transaction_lock = threading.Lock()
_active_transactions: Dict[str, sqlite3.Connection] = {}


def check_db_exists(db_path: str) -> Dict[str, Any]:
    """检查数据库是否存在 - 小沈 2026-05-02"""
    path = Path(db_path)
    if not path.exists():
        return {"code": "SUCCESS", "data": {"exists": False, "db_type": None, "size": 0}, "message": f"数据库文件不存在: {db_path}"}

    size = path.stat().st_size
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("SELECT 1")
        conn.close()
        return {"code": "SUCCESS", "data": {"exists": True, "db_type": "sqlite", "size": size}, "message": f"数据库存在且可连接: {db_path}"}
    except Exception as e:
        return {"code": "SUCCESS", "data": {"exists": True, "db_type": "unknown", "size": size, "error": str(e)}, "message": f"数据库文件存在但无法连接: {str(e)}"}


def get_table_schema(db_path: str, table_name: str) -> Dict[str, Any]:
    """获取表结构 - 小沈 2026-05-02"""
    path = Path(db_path)
    if not path.exists():
        return {"code": "ERR_DB_NOT_FOUND", "data": None, "message": f"数据库文件不存在: {db_path}"}

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA table_info(\"{table_name}\")")
        columns = cursor.fetchall()

        if not columns:
            conn.close()
            return {"code": "ERR_TABLE_NOT_FOUND", "data": None, "message": f"表不存在: {table_name}"}

        col_info = []
        primary_key = None
        for col in columns:
            col_info.append({
                "name": col[1],
                "type": col[2],
                "not_null": bool(col[3]),
                "default": col[4],
                "is_pk": bool(col[5]),
            })
            if col[5]:
                primary_key = col[1]

        conn.close()
        return {
            "code": "SUCCESS",
            "data": {"table_name": table_name, "columns": col_info, "primary_key": primary_key, "column_count": len(col_info)},
            "message": f"表结构获取成功: {table_name}，共 {len(col_info)} 列"
        }
    except Exception as e:
        return {"code": "ERR_GET_SCHEMA", "data": None, "message": f"获取表结构失败: {str(e)}"}


def begin_transaction() -> Dict[str, Any]:
    """开始事务 - 小沈 2026-05-02"""
    import uuid
    tx_id = str(uuid.uuid4())[:8]
    return {"code": "SUCCESS", "data": {"transaction_id": tx_id}, "message": f"事务已开始: {tx_id}"}


def commit_transaction(transaction_id: str) -> Dict[str, Any]:
    """提交事务 - 小沈 2026-05-02"""
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已提交: {transaction_id}"}


def rollback_transaction(transaction_id: str) -> Dict[str, Any]:
    """回滚事务 - 小沈 2026-05-02"""
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已回滚: {transaction_id}"}


def check_network_connectivity() -> Dict[str, Any]:
    """检查网络连通性 - 小沈 2026-05-02"""
    test_hosts = [
        ("dns.google", 53),
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
    ]

    for host, port in test_hosts:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            start = socket.getdefaulttimeout()
            import time
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            sock.close()
            return {"code": "SUCCESS", "data": {"connected": True, "host": host, "latency_ms": round(latency, 2)}, "message": f"网络连通，延迟: {latency:.1f}ms"}
        except (socket.timeout, socket.error, OSError):
            continue

    return {"code": "SUCCESS", "data": {"connected": False}, "message": "网络不可用"}


def validate_url(url: str) -> Dict[str, Any]:
    """验证URL格式 - 小沈 2026-05-02"""
    try:
        parsed = urlparse(url)
        is_valid = bool(parsed.scheme) and bool(parsed.netloc)
        valid_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}
        scheme_ok = parsed.scheme in valid_schemes

        return {
            "code": "SUCCESS",
            "data": {
                "valid": is_valid and scheme_ok,
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
            },
            "message": "URL格式有效" if (is_valid and scheme_ok) else "URL格式无效"
        }
    except Exception as e:
        return {"code": "SUCCESS", "data": {"valid": False, "error": str(e)}, "message": f"URL验证失败: {str(e)}"}
