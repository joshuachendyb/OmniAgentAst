"""DB SDK - 统一数据库操作接口

管理3个SQLite数据库:
- chat_history.db: 对话会话和消息
- operations.db: 文件操作和任务记录
- tool_observer.db: 工具调用审计(后续实现)

使用方式:
    from app.db import db
    
    with db.get_conn("chat") as conn:
        conn.execute("SELECT ...")

设计原则:
- 统一入口:所有DB操作通过db.get_conn()
- 自动事务:上下文管理器自动commit/rollback/close
- 摒弃裸连接:禁止手动管理连接

Author: 小沈 - 2026-05-28
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator
from app.utils.logger import logger


class DatabaseManager:
    """统一数据库管理器(SDK核心)"""
    
    def __init__(self):
        """初始化数据库管理器"""
        self._db_dir = Path.home() / ".omniagent"
        self._db_paths = {
            "chat": self._db_dir / "chat_history.db",
            "operations": self._db_dir / "operations.db",
            "observer": self._db_dir / "tool_observer.db",
            "task_tracker": self._db_dir / "task_tracker.db",
        }
        self._db_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def get_conn(self, db_name: str = "chat") -> Iterator[sqlite3.Connection]:
        """获取数据库连接(上下文管理器)
        
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
            
            # 配置PRAGMA(解决并发写入问题)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            
            # yield连接给调用方
            yield conn
            
            # 正常退出:提交事务
            conn.commit()
            
        except Exception as e:
            # 异常退出:回滚事务
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
    
    def init(self):
        """初始化所有数据库(应用启动时调用)
        
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
        self._init_task_tracker_db()
        self._migrate_old_tables()
        self._migrate_from_old_db()
        self._migrate_tasks_drop_check()
        
        # observer数据库按需初始化(后续实现ToolObserver时调用init_observer)
        logger.info("All databases initialized successfully")
    
    def init_observer(self):
        """初始化observer数据库(后续实现ToolObserver时调用)"""
        # 预留:后续实现tool_observer.py时填充建表逻辑
        logger.info("Observer database initialized (placeholder)")
    
    def _init_chat_db(self):
        """初始化聊天数据库"""
        with self.get_conn("chat") as conn:
            # 第1步: 建表(旧表已存在则跳过)
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
            
            # 第2步: 确保缺失字段存在(旧表迁移)
            self._ensure_column(conn, "chat_sessions", "message_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "chat_sessions", "is_deleted", "BOOLEAN DEFAULT FALSE")
            self._ensure_column(conn, "chat_sessions", "is_valid", "BOOLEAN DEFAULT FALSE")
            self._ensure_column(conn, "chat_sessions", "title_locked", "BOOLEAN DEFAULT FALSE")
            self._ensure_column(conn, "chat_sessions", "title_updated_at", "TIMESTAMP")
            self._ensure_column(conn, "chat_sessions", "version", "INTEGER DEFAULT 1")
            
            # 确保chat_messages旧表字段存在
            self._ensure_column(conn, "chat_messages", "timestamp", "TEXT DEFAULT CURRENT_TIMESTAMP")
            self._ensure_column(conn, "chat_messages", "display_name", "TEXT")
            
            # 添加chat_messages新字段(如果不存在)
            for field in ["client_os", "browser", "device", "network", "reply_to_message_id"]:
                col_type = "INTEGER" if field == "reply_to_message_id" else "TEXT"
                self._ensure_column(conn, "chat_messages", field, col_type)
            
            # 第3步: 建索引(字段已存在,安全)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)")
    
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
        """确保字段存在(P1修复: 添加异常处理,失败不中断init)"""
        try:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = {row["name"].lower() for row in rows}
            if column.lower() not in col_names:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                logger.info(f"Added column {column} to table {table}")
        except Exception as e:
            logger.warning(f"Ensure column failed [{table}.{column}]: {e}")
    
    def _migrate_old_tables(self):
        """迁移旧表数据(幂等操作,P1修复: 修正except缩进+列名安全验证)"""
        try:
            with self.get_conn("operations") as conn:
                row = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='file_operation_sessions'"
                ).fetchone()
                
                if row is None:
                    return
                
                logger.info("Migrating data from file_operation_sessions to task_operations...")
                
                old_columns = [desc[1] for desc in conn.execute("PRAGMA table_info(file_operation_sessions)").fetchall()]
                new_columns = [desc[1] for desc in conn.execute("PRAGMA table_info(task_operations)").fetchall()]
                
                import re
                safe_name = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
                common_columns = [col for col in old_columns if col in new_columns and safe_name.match(col)]
                if not common_columns:
                    logger.warning("No common columns found, skipping migration")
                    return
                
                columns_str = ", ".join(common_columns)
                placeholders = ", ".join(["?" for _ in common_columns])
                
                rows = conn.execute(f"SELECT {columns_str} FROM file_operation_sessions").fetchall()
                
                for row in rows:
                    conn.execute(f"INSERT OR IGNORE INTO task_operations ({columns_str}) VALUES ({placeholders})", row)
                
                logger.info(f"Migrated {len(rows)} rows")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")

    def _init_task_tracker_db(self):
        """初始化 Task 追踪数据库(独立库 task_tracker.db)"""
        with self.get_conn("task_tracker") as conn:
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

    def _migrate_tasks_drop_check(self):
        """迁移tasks表:删除intent列的CHECK约束"""
        try:
            with self.get_conn("task_tracker") as conn:
                row = conn.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name='tasks'"
                ).fetchone()
                if row and 'CHECK' in (row[0] or '').upper():
                    logger.info("Migrating tasks table: dropping intent CHECK constraint...")
                    conn.execute("PRAGMA foreign_keys=OFF")
                    conn.executescript("""
                        CREATE TABLE tasks_new (
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
                        INSERT INTO tasks_new SELECT * FROM tasks;
                        DROP TABLE tasks;
                        ALTER TABLE tasks_new RENAME TO tasks;
                    """)
                    conn.execute("PRAGMA foreign_keys=ON")
                    logger.info("Tasks table migration complete")
        except Exception as e:
            logger.warning(f"Tasks CHECK migration skipped: {e}")

    def _migrate_from_old_db(self):
        """从旧 operations.db 迁移数据到新 task_tracker.db(幂等,失败不阻塞启动)"""
        try:
            with self.get_conn("operations") as old_conn:
                old_ops = old_conn.execute("SELECT * FROM file_operations").fetchall()
                if not old_ops:
                    return
                with self.get_conn("task_tracker") as new_conn:
                    for row in old_ops:
                        new_conn.execute(
                            """INSERT OR IGNORE INTO operations
                               (operation_id, task_id, intent, operation_type, status,
                                source_path, destination_path, backup_path,
                                file_size, file_hash, sequence_number, details, error, created_at)
                               VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (row["operation_id"], row["task_id"], row["operation_type"],
                             row["status"], row["source_path"], row["destination_path"],
                             row["backup_path"], row["file_size"], row["file_hash"],
                             row["sequence_number"], row["metadata"], row["error_message"],
                             row["created_at"])
                        )
                    logger.info(f"Migrated {len(old_ops)} operations from old DB to task_tracker.db")
        except Exception as e:
            logger.warning(f"Migration from old DB skipped (old DB may not exist): {e}")


# 全局SDK实例(唯一入口)
db = DatabaseManager()
