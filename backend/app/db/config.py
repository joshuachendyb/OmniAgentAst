"""
数据库配置模块 (Database Configuration Module)
统一定义所有数据库路径，避免重复定义

Author: 小沈 - 2026-05-22
"""
from pathlib import Path

# 数据库根目录
DB_DIR = Path.home() / ".omniagent"

# 各数据库文件路径（统一管理）
CHAT_DB_PATH = DB_DIR / "chat_history.db"
OPERATIONS_DB_PATH = DB_DIR / "operations.db"
OBSERVER_DB_PATH = DB_DIR / "tool_observer.db"


def ensure_db_dir():
    """确保数据库目录存在"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
