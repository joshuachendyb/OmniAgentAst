"""
操作数据库管理模块 (Operations Database Module)
管理 operations.db 的连接和初始化

Author: 小沈 - 2026-05-22
"""
import sqlite3
from app.db.config import OPERATIONS_DB_PATH, create_connection
from app.utils.logger import logger


def get_connection() -> sqlite3.Connection:
    """
    获取操作数据库连接
    
    Returns:
        sqlite3.Connection: 启用了WAL模式的数据库连接
    """
    return create_connection(OPERATIONS_DB_PATH, row_factory=sqlite3.Row)


def init_database():
    """初始化操作数据库表"""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 创建操作记录表
        cursor.execute('''
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
            )
        ''')
        
        # 创建会话记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_operation_sessions (
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
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_operations_session 
            ON file_operations(task_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_operations_created 
            ON file_operations(created_at)
        ''')
        
        conn.commit()
        logger.info("File operation database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        # 【修复问题8：数据库连接未关闭】
        # 确保连接总是被关闭，即使在异常情况下
        if conn:
            conn.close()


# 模块级自动初始化
init_database()
