"""
数据库模块 (Database Module)
提供统一的数据库连接、初始化和数据模型管理

Author: 小沈 - 2026-05-22
"""
from app.db.config import (
    DB_DIR,
    CHAT_DB_PATH,
    OPERATIONS_DB_PATH,
    OBSERVER_DB_PATH,
    ensure_db_dir,
)
from app.db.chat_db import get_connection as get_chat_connection, init_database as init_chat_database

__all__ = [
    # 配置
    "DB_DIR",
    "CHAT_DB_PATH",
    "OPERATIONS_DB_PATH",
    "OBSERVER_DB_PATH",
    "ensure_db_dir",
    # 聊天数据库
    "get_chat_connection",
    "init_chat_database",
]
