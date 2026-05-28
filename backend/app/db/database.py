"""DB SDK - 统一数据库操作接口

管理3个SQLite数据库：
- chat_history.db: 对话会话和消息
- operations.db: 文件操作和任务记录
- tool_observer.db: 工具调用审计（后续实现）

使用方式:
    from app.db import db
    
    with db.get_conn("chat") as conn:
        conn.execute("SELECT ...")

设计原则:
- 统一入口：所有DB操作通过db.get_conn()
- 自动事务：上下文管理器自动commit/rollback/close
- 摒弃裸连接：禁止手动管理连接

Author: 小沈 - 2026-05-28
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator, Dict
from app.utils.logger import logger


class DatabaseManager:
    """统一数据库管理器（SDK核心）"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self._db_dir = Path.home() / ".omniagent"
        self._db_paths = {
            "chat": self._db_dir / "chat_history.db",
            "operations": self._db_dir / "operations.db",
            "observer": self._db_dir / "tool_observer.db",
        }
        self._db_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_conn(self, db_name: str = "chat") -> Iterator[sqlite3.Connection]:
        """获取数据库连接（上下文管理器）
        
        使用方式:
            with db.get_conn("chat") as conn:
                conn.execute("SELECT ...")
        
        自动处理:
            - 正常退出: commit + close
            - 异常退出: rollback + close
            - 无论如何: 都会关闭连接
        
        支持的db_name: chat, operations, observer
        """
        conn = None
        try:
            # 验证数据库名称
            if db_name not in self._db_paths:
                raise ValueError(
                    f"Unknown database: {db_name}. "
                    f"Supported: {list(self._db_paths.keys())}"
                )
            
            # 创建连接
            db_path = self._db_paths[db_name]
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            
            # 配置PRAGMA（解决并发写入问题）
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            
            # yield连接给调用方
            yield conn
            
            # 正常退出：提交事务
            conn.commit()
            
        except Exception as e:
            # 异常退出：回滚事务
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass  # 回滚失败不影响原始异常
            
            # 记录错误
            logger.error(f"DB operation failed [{db_name}]: {e}")
            
            # 重新抛出异常
            raise
            
        finally:
            # 无论如何都要关闭连接
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass  # 关闭失败不影响主流程
    
    def check_fields(self, table: str, fields: list, db_name: str = "chat") -> Dict[str, bool]:
        """检查表中字段是否存在（使用PRAGMA table_info，不用try/except）
        
        使用方式:
            fields = db.check_fields("chat_sessions", ["title_locked", "version"])
        
        Args:
            table: 表名
            fields: 要检查的字段列表
            db_name: 数据库名称，默认chat
            
        Returns:
            dict: {field_name: True/False}
        """
        result = {f: False for f in fields}
        
        try:
            with self.get_conn(db_name) as conn:
                # 使用PRAGMA查询字段信息（不用try/except试探）
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
                
                # 提取所有字段名（标准化处理）
                columns = set()
                for row in rows:
                    field_name = row["name"]
                    if field_name:
                        # 去除空格、引号，转小写
                        field_name = field_name.strip().strip('"').strip("'").lower()
                        columns.add(field_name)
                
                # 检查每个字段是否存在
                for field in fields:
                    result[field] = field.lower() in columns
                    
        except Exception as e:
            logger.error(f"Check fields failed [{table}]: {e}")
            # 失败时返回全False
            result = {f: False for f in fields}
        
        return result
    
    def init(self):
        """初始化所有数据库（应用启动时调用）
        
        调用方式:
            # main.py lifespan
            from app.db import db
            
            @app.on_event("startup")
            async def startup_event():
                db.init()
        """
        logger.info("Initializing all databases...")
        
        self._init_chat_db()
        self._init_operations_db()
        self._migrate_old_tables()
        
        # observer数据库按需初始化（后续实现ToolObserver时调用init_observer）
        logger.info("All databases initialized successfully")
    
    def init_observer(self):
        """初始化observer数据库（后续实现ToolObserver时调用）"""
        # 预留：后续实现tool_observer.py时填充建表逻辑
        logger.info("Observer database initialized (placeholder)")
    
    def _init_chat_db(self):
        """初始化聊天数据库"""
        with self.get_conn("chat") as conn:
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
                
                CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted);
                CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
                CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp);
            ''')
            
            # 添加新字段（如果不存在）
            for field in ["client_os", "browser", "device", "network"]:
                self._ensure_column(conn, "chat_messages", field, "TEXT")
    
    def _init_operations_db(self):
        """初始化操作数据库"""
        with self.get_conn("operations") as conn:
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
    
    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, col_type: str):
        """确保字段存在（使用PRAGMA查询，不用try/except）"""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = {row["name"].lower() for row in rows}
        if column.lower() not in col_names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"Added column {column} to table {table}")
    
    def _migrate_old_tables(self):
        """迁移旧表数据（幂等操作）"""
        try:
            with self.get_conn("operations") as conn:
                # 检查旧表是否存在
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operation_sessions'"
                ).fetchone()
                
                if row is None:
                    return  # 旧表不存在，无需迁移
                
                logger.info("Migrating data from file_operation_sessions to task_operations...")
                
                # 获取旧表结构
                old_columns = [desc[1] for desc in conn.execute("PRAGMA table_info(file_operation_sessions)").fetchall()]
                new_columns = [desc[1] for desc in conn.execute("PRAGMA table_info(task_operations)").fetchall()]
                
                # 找出交集列
                common_columns = [col for col in old_columns if col in new_columns]
                if not common_columns:
                    logger.warning("No common columns found, skipping migration")
                    return
                
                columns_str = ", ".join(common_columns)
                placeholders = ", ".join(["?" for _ in common_columns])
                
                # 获取旧表数据
                rows = conn.execute(f"SELECT {columns_str} FROM file_operation_sessions").fetchall()
                
                # 复制数据到新表（INSERT OR IGNORE保证幂等）
                for row in rows:
                    conn.execute(f"INSERT OR IGNORE INTO task_operations ({columns_str}) VALUES ({placeholders})", row)
                
                logger.info(f"Migrated {len(rows)} rows")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            # 迁移失败不阻止应用启动


# 全局SDK实例（唯一入口）
db = DatabaseManager()
