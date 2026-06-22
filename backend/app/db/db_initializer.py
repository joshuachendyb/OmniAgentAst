# -*- coding: utf-8 -*-
"""
db_initializer — 数据库初始化

职责: 创建表、确保字段存在
小欧 2026-06-18 从database.py拆分，遵守SRP
"""
import sqlite3
from app.utils.logger import logger


def init_chat_db(get_conn):
    """初始化聊天数据库"""
    with get_conn("chat") as conn:
        conn.executescript('''
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
            );
            
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                execution_steps TEXT,
                display_name TEXT
            );
            
            CREATE TABLE IF NOT EXISTS chat_session_title_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                change_reason TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );
        ''')
        
        _ensure_column(conn, "chat_sessions", "message_count", "INTEGER DEFAULT 0")
        _ensure_column(conn, "chat_sessions", "is_deleted", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "is_valid", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "title_locked", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "title_updated_at", "TIMESTAMP")
        _ensure_column(conn, "chat_sessions", "version", "INTEGER DEFAULT 1")
        
        _ensure_column(conn, "chat_messages", "timestamp", "TEXT DEFAULT CURRENT_TIMESTAMP")
        _ensure_column(conn, "chat_messages", "display_name", "TEXT")
        
        for field in ["client_os", "browser", "device", "network", "reply_to_message_id"]:
            col_type = "INTEGER" if field == "reply_to_message_id" else "TEXT"
            _ensure_column(conn, "chat_messages", field, col_type)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)")


def init_operations_db(get_conn):
    """初始化操作数据库"""
    with get_conn("operations") as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS file_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT UNIQUE NOT NULL,
                task_id TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                source_path TEXT,
                destination_path TEXT,
                backup_path TEXT,
                backup_expires_at TIMESTAMP,
                file_size INTEGER,
                file_hash TEXT,
                is_directory BOOLEAN DEFAULT 0,
                file_extension TEXT,
                duration_ms INTEGER,
                space_impact_bytes INTEGER,
                metadata TEXT DEFAULT '{}',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                executed_at TIMESTAMP,
                rolled_back_at TIMESTAMP,
                sequence_number INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS task_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                agent_id TEXT NOT NULL,
                task_description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_operations INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                rolled_back_count INTEGER DEFAULT 0,
                report_generated BOOLEAN DEFAULT 0,
                report_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_operations_session ON file_operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_operations_created ON file_operations(created_at);
        ''')


def init_task_tracker_db(get_conn):
    """初始化 Task 追踪数据库"""
    with get_conn("task_tracker") as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id          TEXT PRIMARY KEY,
                intent           TEXT NOT NULL DEFAULT '',
                agent_id         TEXT NOT NULL,
                task_description TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'executing',
                total_operations INTEGER DEFAULT 0,
                success_count    INTEGER DEFAULT 0,
                failed_count     INTEGER DEFAULT 0,
                rolled_back_count INTEGER DEFAULT 0,
                report_generated INTEGER DEFAULT 0,
                report_path      TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at     TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

            CREATE TABLE IF NOT EXISTS operations (
                operation_id     TEXT PRIMARY KEY,
                task_id          TEXT NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
                intent           TEXT NOT NULL DEFAULT '',
                operation_type   TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                source_path      TEXT,
                destination_path TEXT,
                backup_path      TEXT,
                file_size        INTEGER DEFAULT 0,
                file_hash        TEXT,
                sequence_number  INTEGER NOT NULL DEFAULT 0,
                details          TEXT,
                error            TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_ops_task ON operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_ops_seq  ON operations(task_id, sequence_number);
        ''')


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str):
    """确保字段存在(P1修复: 添加异常处理,失败不中断init)"""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = {row["name"].lower() for row in rows}
        if column.lower() not in col_names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"Added column {column} to table {table}")
    except Exception as e:
        logger.warning(f"Ensure column failed [{table}.{column}]: {e}")
