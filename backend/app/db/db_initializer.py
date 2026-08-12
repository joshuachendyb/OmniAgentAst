# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 新增chat_message_steps独立步骤表(一行=一步)+idx_steps_message和idx_steps_session索引,支撑运行期逐步落库
# 2026-07-16 - 小欧 - chat_messages 增 thought TEXT 列, 持久化 thought 到主表
# 2026-07-16 - 小欧 - task_tracker迁移幂等修复(operations→task_operations)
#   [原来] 若operations表存在则ALTER RENAME operations→task_operations(不处理半残)
#   [问题] 库处于"旧operations + 已建空task_operations"半残态时, RENAME报"already another table with name task_operations", 后端启动失败
#   [根因] CREATE TABLE IF NOT EXISTS task_operations 与 RENAME 顺序/幂等不完整: 旧库首次启动先CREATE空task_operations, RENAME失败留残表, 再次启动RENAME撞名
#   [改法] 先查_has_ops与_has_task_ops; 两者并存则DROP空task_operations再RENAME; 幂等覆盖半残态
#   [原理] ①半残态task_operations必为空表(IF NOT EXISTS创建后无INSERT), DROP安全不丢数据
#          ②正常旧库(仅operations)直接RENAME保留历史; 新库/已迁移库CREATE跳过
#          ③DROP+RENAME使迁移在任何状态都收敛到唯一task_operations, 幂等自愈
# 2026-07-18 - 小欧 - 所有时间列 TIMESTAMP→TEXT, 去 DEFAULT CURRENT_TIMESTAMP; _ensure_column title_updated_at TEXT; backup_expires_at TEXT
# 2026-08-08 - 小欧 - 全程统一本地时区: 时间列注释 `-- UTC ISO 8601` → `-- 本地ISO无Z` (13处)
"""
db_initializer — 数据库初始化

职责: 创建表、确保字段存在
小欧 2026-06-18 从database.py拆分，遵守SRP
"""
import sqlite3
from app.logger import logger


def init_chat_db(get_conn):
    """初始化聊天数据库"""
    with get_conn("chat") as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT,  -- 本地ISO无Z
                updated_at TEXT,  -- 本地ISO无Z
                message_count INTEGER DEFAULT 0,
                is_deleted BOOLEAN DEFAULT FALSE,
                is_valid BOOLEAN DEFAULT FALSE,
                title_locked BOOLEAN DEFAULT FALSE,
                title_updated_at TEXT,  -- 本地ISO无Z
                version INTEGER DEFAULT 1
            );
            
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT,  -- 本地ISO无Z
                execution_steps TEXT,
                display_name TEXT
            );
            
            CREATE TABLE IF NOT EXISTS chat_session_title_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT,  -- 本地ISO无Z
                updated_by TEXT,
                change_reason TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            -- 独立步骤表 — 小欧 2026-07-14
            CREATE TABLE IF NOT EXISTS chat_message_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_json TEXT NOT NULL,
                created_at TEXT,  -- 本地ISO无Z
                FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
            );
        ''')
        
        _ensure_column(conn, "chat_sessions", "message_count", "INTEGER DEFAULT 0")
        _ensure_column(conn, "chat_sessions", "is_deleted", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "is_valid", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "title_locked", "BOOLEAN DEFAULT FALSE")
        _ensure_column(conn, "chat_sessions", "title_updated_at", "TEXT")
        _ensure_column(conn, "chat_sessions", "version", "INTEGER DEFAULT 1")
        
        _ensure_column(conn, "chat_messages", "timestamp", "TEXT")
        _ensure_column(conn, "chat_messages", "display_name", "TEXT")
        
        for field in ["client_os", "browser", "device", "network", "reply_to_message_id"]:
            col_type = "INTEGER" if field == "reply_to_message_id" else "TEXT"
            _ensure_column(conn, "chat_messages", field, col_type)

        # 小欧 2026-07-13: 终态列(status), 记录一次请求的任务终态, 供前端/迁移直接读取
        _ensure_column(conn, "chat_messages", "status", "TEXT")
        _ensure_column(conn, "chat_messages", "thought", "TEXT")  # 小欧 2026-07-16
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON chat_messages(timestamp)")

        # steps 表索引 — 小欧 2026-07-14
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_message ON chat_message_steps(message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_session ON chat_message_steps(session_id, step_index)")

        # 小欧 2026-07-13: 一次性迁移旧 execution_steps(幂等)
        from app.services.chat.migrate_steps import migrate_execution_steps_status
        migrate_execution_steps_status(get_conn)


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
                backup_expires_at TEXT,  -- 本地ISO无Z
                file_size INTEGER,
                file_hash TEXT,
                is_directory BOOLEAN DEFAULT 0,
                file_extension TEXT,
                duration_ms INTEGER,
                space_impact_bytes INTEGER,
                metadata TEXT DEFAULT '{}',
                error_message TEXT,
                created_at TEXT,  -- 本地ISO无Z
                executed_at TEXT,  -- 本地ISO无Z
                rolled_back_at TEXT,  -- 本地ISO无Z
                sequence_number INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS timers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timer_id TEXT UNIQUE NOT NULL,
                delay REAL NOT NULL,
                callback TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP NOT NULL,
                trigger_at TIMESTAMP NOT NULL,
                triggered_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'active'
            );

            CREATE INDEX IF NOT EXISTS idx_operations_session ON file_operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_operations_created ON file_operations(created_at);
        ''')


def init_task_tracker_db(get_conn):
    """初始化 Task 追踪数据库"""
    with get_conn("task_tracker") as conn:
        # ==========================================================================
        # task_tracker 迁移：旧 operations 表改名为 task_operations（命名正名） — 小欧 2026-07-16
        # 目标：把含糊的 operations 表正名为 task_operations（任务步骤统一记录），与
        #       operations.db 内的 file_operations 区分，消除"双轨/多套 ID"混乱。
        # 为什么需要幂等处理半残状态：
        #   - 旧库首次启动会先 CREATE TABLE IF NOT EXISTS task_operations（空表），
        #     再 ALTER RENAME operations→task_operations 失败 → 留下"operations + 空 task_operations"残表；
        #   - 再次启动时 RENAME 撞名（already another table with name task_operations），后端起不来。
        # 处理逻辑：
        #   [查] 先查 _has_ops / _has_task_ops 两个表是否并存；
        #   [清] 若并存（半残）→ DROP 空 task_operations（半残态必为空表，DROP 安全不丢数据）；
        #   [迁] ALTER operations RENAME TO task_operations（保留旧历史数据）；
        #   [兜底] 末尾 CREATE TABLE IF NOT EXISTS 覆盖新库/已迁移库，幂等自愈。
        # 原理：DROP 空残表 + RENAME 使迁移在任何状态都收敛到唯一 task_operations，不丢历史、不撞名。
        # ==========================================================================
        _has_ops = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='operations'"
        ).fetchone()
        _has_task_ops = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='task_operations'"
        ).fetchone()
        if _has_ops:
            if _has_task_ops:
                conn.execute("DROP TABLE IF EXISTS task_operations")  # 半残: 清掉空/旧的 task_operations, 小欧 2026-07-16
            conn.execute("ALTER TABLE operations RENAME TO task_operations")
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
                created_at       TEXT,  -- 本地ISO无Z
                completed_at     TEXT   -- 本地ISO无Z
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at);

            CREATE TABLE IF NOT EXISTS task_operations (
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
                created_at       TEXT  -- 本地ISO无Z
            );

            CREATE INDEX IF NOT EXISTS idx_ops_task ON task_operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_ops_seq  ON task_operations(task_id, sequence_number);
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
