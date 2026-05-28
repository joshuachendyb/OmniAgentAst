"""
数据库配置模块 (Database Configuration Module)
统一定义所有数据库路径，避免重复定义

Author: 小沈 - 2026-05-22
"""
import sqlite3
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


def create_connection(db_path, row_factory=sqlite3.Row):
    """
    创建数据库连接（统一工厂函数）
    
    Args:
        db_path: 数据库文件路径
        row_factory: row_factory设置，默认为sqlite3.Row
        
    Returns:
        sqlite3.Connection: 启用了WAL模式的数据库连接
    """
    ensure_db_dir()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = row_factory
    # 【M18修复 2026-05-13 小沈】启用WAL模式+忙等待超时，解决并发写入"database is locked"错误
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
