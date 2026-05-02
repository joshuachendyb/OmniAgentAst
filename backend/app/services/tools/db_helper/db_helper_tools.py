# -*- coding: utf-8 -*-
"""
数据库辅助工具函数模块

【创建时间】2026-05-02 小沈
【更新时间】2026-05-02 小沈

================================================================================
一、模块性质（双重身份）
================================================================================
本模块的函数具有双重身份：

1. **公共辅助函数** - 可被其他Tool函数内部调用
   - 例如：query_sql内部调用check_db_exists验证数据库存在
   - 例如：http_request内部调用validate_url验证URL格式

2. **LLM可调用Tool** - 可被用户直接调用
   - 用户问"检查数据库是否存在" → LLM调用check_db_exists
   - 用户问"这个URL格式对不对" → LLM调用validate_url

【重要】这些函数不是"没用"，而是作为公共基础设施，供其他Tool和用户共用。

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
# 其他Tool内部调用示例
def query_sql(db_path, sql):
    # 内部调用公共辅助函数
    result = check_db_exists(db_path)
    if not result["data"]["exists"]:
        return {"error": "数据库不存在"}
    # 执行SQL...

# LLM直接调用示例
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

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.db_helper.db_helper_schema import (
    CheckDbExistsInput,
    GetTableSchemaInput,
    ValidateUrlInput,
)

_transaction_lock = threading.Lock()
_active_transactions: Dict[str, sqlite3.Connection] = {}


@register_tool(
    name="check_db_exists",
    description="""检查数据库文件是否存在且可连接。

使用场景：
- 当用户需要确认数据库是否存在时使用
- 当用户在操作数据库前需要验证时使用

参数说明：
- db_path：数据库文件路径

返回数据说明：
- code: 状态码
- data: exists(bool), db_type(str)""",
    category=ToolCategory.DB_HELPER,
    input_model=CheckDbExistsInput,
    examples=[{"db_path": "D:/data/app.db"}]
)
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


@register_tool(
    name="get_table_schema",
    description="""获取数据库表结构信息。

使用场景：
- 当用户需要查看表结构时使用
- 当用户在操作表前需要了解字段信息时使用

参数说明：
- db_path：数据库文件路径
- table_name：表名称

返回数据说明：
- code: 状态码
- data: columns, primary_key等信息""",
    category=ToolCategory.DB_HELPER,
    input_model=GetTableSchemaInput,
    examples=[{"db_path": "D:/data/app.db", "table_name": "users"}]
)
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


@register_tool(
    name="begin_transaction",
    description="""开始数据库事务。

使用场景：
- 当用户需要在数据库操作前开始事务时使用
- 当用户需要保证数据操作的原子性时使用

【重要】返回事务ID，用于后续commit/rollback""",
    category=ToolCategory.DB_HELPER,
    input_model=None,
    input_schema={"type": "object", "properties": {}, "required": []},
    examples=[{}]
)
def begin_transaction() -> Dict[str, Any]:
    """开始事务 - 小沈 2026-05-02"""
    import uuid
    tx_id = str(uuid.uuid4())[:8]
    return {"code": "SUCCESS", "data": {"transaction_id": tx_id}, "message": f"事务已开始: {tx_id}"}


@register_tool(
    name="commit_transaction",
    description="""提交数据库事务。

使用场景：
- 当用户需要提交事务使操作生效时使用

参数说明：
- transaction_id：事务ID""",
    category=ToolCategory.DB_HELPER,
    input_model=None,
    input_schema={"type": "object", "properties": {"transaction_id": {"type": "string", "description": "事务ID"}}, "required": ["transaction_id"]},
    examples=[{"transaction_id": "abc12345"}]
)
def commit_transaction(transaction_id: str) -> Dict[str, Any]:
    """提交事务 - 小沈 2026-05-02"""
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已提交: {transaction_id}"}


@register_tool(
    name="rollback_transaction",
    description="""回滚数据库事务。

使用场景：
- 当用户需要撤销事务中的操作时使用

参数说明：
- transaction_id：事务ID""",
    category=ToolCategory.DB_HELPER,
    input_model=None,
    input_schema={"type": "object", "properties": {"transaction_id": {"type": "string", "description": "事务ID"}}, "required": ["transaction_id"]},
    examples=[{"transaction_id": "abc12345"}]
)
def rollback_transaction(transaction_id: str) -> Dict[str, Any]:
    """回滚事务 - 小沈 2026-05-02"""
    return {"code": "SUCCESS", "data": {"transaction_id": transaction_id}, "message": f"事务已回滚: {transaction_id}"}


@register_tool(
    name="check_network_connectivity",
    description="""检查网络连通性。

使用场景：
- 当用户需要确认网络是否可用时使用
- 当用户在执行网络操作前需要验证连通性时使用

【重要】返回网络是否可用及延迟信息""",
    category=ToolCategory.DB_HELPER,
    input_model=None,
    input_schema={"type": "object", "properties": {}, "required": []},
    examples=[{}]
)
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


@register_tool(
    name="validate_url",
    description="""验证URL格式是否正确。

使用场景：
- 当用户需要确认URL格式是否有效时使用
- 当用户在发送网络请求前需要验证URL时使用

参数说明：
- url：要验证的URL

【重要】返回URL是否有效及解析信息""",
    category=ToolCategory.DB_HELPER,
    input_model=ValidateUrlInput,
    examples=[{"url": "https://example.com"}]
)
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
