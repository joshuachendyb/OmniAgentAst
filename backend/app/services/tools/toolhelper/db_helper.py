# -*- coding: utf-8 -*-
"""
数据库辅助函数模块 - 数据库相关的内部辅助函数

【创建时间】2026-05-17 小沈
【说明】从 support_tool/support_tool_tools.py 迁移 check_db_exists 函数

包含函数（1个）：
- check_db_exists: 检查数据库是否存在（公共函数 + LLM Tool）

Author: 小沈 - 2026-05-17
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


class CheckDbExistsInput(BaseModel):
    """check_db_exists 工具的输入参数 - 小沈 2026-05-17"""
    db_path: str = Field(..., description="数据库文件路径。如 D:/data/app.db")


def check_db_exists(db_path: str) -> Dict[str, Any]:
    """检查数据库是否存在 - 小沈 2026-05-17（从 support_tool_tools.py 迁移）"""
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


__all__ = [
    "check_db_exists",
    "CheckDbExistsInput",
]
