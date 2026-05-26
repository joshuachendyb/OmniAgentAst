"""
聊天数据库管理模块 (Chat Database Module)
管理 chat_history.db 的连接和初始化

Author: 小沈 - 2026-05-22
"""
import sqlite3
from app.db.config import CHAT_DB_PATH, ensure_db_dir


def get_connection() -> sqlite3.Connection:
    """
    获取聊天数据库连接
    
    Returns:
        sqlite3.Connection: 启用了WAL模式的数据库连接
    """
    ensure_db_dir()
    conn = sqlite3.connect(str(CHAT_DB_PATH))
    conn.row_factory = sqlite3.Row
    # 【M18修复 2026-05-13 小沈】启用WAL模式+忙等待超时，解决并发写入"database is locked"错误
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_database():
    """初始化聊天数据库表"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 创建会话表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            is_deleted BOOLEAN DEFAULT FALSE,
            is_valid BOOLEAN DEFAULT FALSE,
            title_locked BOOLEAN DEFAULT FALSE,
            title_updated_at TIMESTAMP,
            version INTEGER DEFAULT 1
        )
    ''')
    # 注意：现在所有会话都已具有 is_valid 字段，无需额外的检查或更新操作
    
    # 创建消息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            execution_steps TEXT,
            display_name TEXT
        )
    ''')
    
    # 【小沈添加 2026-03-03】添加 display_name 字段（如果不存在）
    try:
        cursor.execute('SELECT display_name FROM chat_messages LIMIT 1')
    except Exception:
        cursor.execute('ALTER TABLE chat_messages ADD COLUMN display_name TEXT')
        conn.commit()
        print("数据库已添加 display_name 字段")
    
    # 【小沈添加 2026-03-24】添加客户端信息字段（如果不存在）
    for field in ['client_os', 'browser', 'device', 'network']:
        try:
            cursor.execute(f'SELECT {field} FROM chat_messages LIMIT 1')
        except Exception:
            cursor.execute(f'ALTER TABLE chat_messages ADD COLUMN {field} TEXT')
            conn.commit()
            print(f"数据库已添加 {field} 字段")
    
    # 创建标题历史表（P2-中优先级）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_session_title_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            change_reason TEXT,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)')
    
    conn.commit()
    conn.close()


# 模块级自动初始化（与原 sessions.py 行为一致）
init_database()
