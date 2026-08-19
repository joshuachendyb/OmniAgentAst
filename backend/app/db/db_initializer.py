# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 新增chat_task_steps独立步骤表(一行=一步)+idx_steps_message和idx_steps_session索引,支撑运行期逐步落库
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
# 2026-08-16 - 小欧 - S0 表结构先行(10.1.7①-a, 北京老陈 2026-08-16 定案, 幂等 DDL):
#   ①chat_tasks 新建(B1, 含 context_link_mode/context_root_task_id 链列) ②chat_messages/chat_task_steps 补 task_id、
#   chat_messages 补 metadata、chat_sessions 补 metadata/model_override 五列(_ensure_column 只 ADD 缺列) ③token_usage 新建(B2)+五索引
#   ④chat_session_trust 新建(B3) ⑤索引: idx_tasks_session/idx_steps_task/idx_msg_task/idx_msg_timestamp/idx_trust_session;
#   与 10.1.9 迁移章节对齐(现网老库幂等补建不丢数据)
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.1→9.5→9.7): chat_message_steps→chat_task_steps全局改名
#   (message_id→ai_message_id)、删chat_messages.execution_steps列、删chat_session_title_history DDL、
#   删migrate_steps调用、reply_to_message_id→user_message_id ensure(改动7)、删metadata×2+冗余索引、
#   chat_tasks加ai_message_id(改动9)、新建chat_user_message表(改动1)
# 2026-08-19 - 小欧 - 恢复 migrate_v2_chat_restructure 调用(必须在建 idx_steps_message 索引之前):
#   现网库处于 v2.0 中间态(chat_task_steps 旧结构空表重名), init_chat_db 在 executescript 建表后
#   CREATE INDEX idx_steps_message ON chat_task_steps(ai_message_id) 必报 no such column,
#   故将结构迁移前移到建索引之前执行, 幂等收敛到新结构后再建索引
# 2026-08-19 - 小欧 - 迁移调用位置修正: 从 executescript 后移到 _ensure_column 之后、建索引之前,
#   因 v2 迁移回灌 SET comprehension SELECT 依赖 _ensure_column 补的 client_os/timestamp 等列; 且
#   建 chat_task_steps(ai_message_id) 索引需迁移改名后的新列, 故必须晚于补列、早于索引(修正初版时序错误)
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
                display_name TEXT
            );
            
            -- 独立步骤表 — 小欧 2026-07-14; v2.0 改名 chat_task_steps — 小欧 2026-08-19
            CREATE TABLE IF NOT EXISTS chat_task_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_message_id INTEGER NOT NULL,  -- v2.0 改名: message_id → ai_message_id, 与代码变量同名贯通
                session_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_json TEXT NOT NULL,
                created_at TEXT,  -- 本地ISO无Z
                task_id TEXT,
                usage TEXT,
                user_message_id INTEGER,  -- v2.0 冗余：免 JOIN 直达 user 消息 — 小欧 2026-08-19
                FOREIGN KEY (ai_message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
            );

            -- ===== S0 新增 3 表（10.1.7① 表结构先行，北京老陈 2026-08-16 定案，幂等）— 小欧 2026-08-16 =====
            -- ① chat_tasks 新建（B1：任务级存储 + 上下文链落库列；字段以文档2 3.1.2/3.5.3 权威为准）
            CREATE TABLE IF NOT EXISTS chat_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                user_message_id INTEGER, user_input TEXT, response TEXT,
                artifacts TEXT DEFAULT '[]',
                status TEXT DEFAULT 'executing',
                start_time TEXT, end_time TEXT, duration REAL,          -- 开始/结束/耗时（文档2 3.1.2 时间三字段）
                context_link_mode TEXT, context_root_task_id TEXT,   -- 上下文链：续聊/新任务 + 链根任务id
                provider TEXT, model TEXT, display_name TEXT,
                accumulated_usage TEXT DEFAULT '{}',
                llm_call_count INTEGER DEFAULT 0, total_steps INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0, max_steps INTEGER DEFAULT 0,   -- 最大步骤数上限（文档2 3.5.3）
                error_type TEXT, error_message TEXT,
                 ai_message_id INTEGER,  -- v2.0 改动9新增: task→assistant 消息直达（与 user_message_id 对称），与 chat_task_steps.ai_message_id 同名贯通 — 小欧 2026-08-19
                created_at TEXT, updated_at TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            -- ④ token_usage 新建（B2：token 四维度归属落库，权威=9.3）
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL, task_id TEXT NOT NULL,
                llm_call_count INTEGER NOT NULL,   -- 直取 react_cycle 既有 agent.llm_call_count, 与 chat_tasks 同名同值
                model TEXT NOT NULL, provider TEXT,
                prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
                created_at TEXT
            );

            -- ⑤ chat_session_trust 新建（B3：HITL 会话信任清单，权威=文档2 3.1.7）
            CREATE TABLE IF NOT EXISTS chat_session_trust (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                created_at TEXT,
                UNIQUE(session_id, tool_name),
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            -- v2.0 新建 chat_user_message 表（用户消息+AI最终回答汇总）— 小欧 2026-08-19
            CREATE TABLE IF NOT EXISTS chat_user_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                task_id TEXT,
                response TEXT,
                reasoning TEXT,
                outcome TEXT,
                model TEXT,
                provider TEXT,
                accumulated_usage TEXT,
                client_os TEXT,
                browser TEXT,
                device TEXT,
                network TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
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
        
        for field in ["client_os", "browser", "device", "network", "user_message_id"]:
            col_type = "INTEGER" if field == "user_message_id" else "TEXT"
            _ensure_column(conn, "chat_messages", field, col_type)

        # 小欧 2026-07-13: 终态列(status), 记录一次请求的任务终态, 供前端/迁移直接读取
        _ensure_column(conn, "chat_messages", "status", "TEXT")
        _ensure_column(conn, "chat_messages", "thought", "TEXT")  # 小欧 2026-07-16

        # ===== S0 补列（10.1.7① ②③，幂等只 ADD 缺列、老行 NULL 不丢数据）— 小欧 2026-08-16 =====
        # ② chat_messages / chat_task_steps 补 task_id 列（B1 挂任务；对齐文档2 3.1.8-⑥）
        _ensure_column(conn, "chat_messages", "task_id", "TEXT")
        _ensure_column(conn, "chat_task_steps", "task_id", "TEXT")
        # ③ chat_sessions 补 model_override 列
        _ensure_column(conn, "chat_sessions", "model_override", "TEXT")    # L2 会话级模型覆盖落库点

        # v2.0 结构迁移 — 小欧 2026-08-19
        #  ①必须在 _ensure_column 之后(_ensure_column 为回灌 SELECT 补齐 client_os/timestamp 等列)
        #  ②必须在建 idx_steps_message 索引之前(索引依赖迁移改名后的 ai_message_id 列)
        #  ③migrate_steps 顶层依赖 storage→db→database→db_initializer 存在循环导入, 采用函数内延迟 import
        from app.services.chat.migrate_steps import migrate_v2_chat_restructure
        migrate_v2_chat_restructure(get_conn)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")

        # steps 表索引 — 小欧 2026-07-14
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_message ON chat_task_steps(ai_message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_session ON chat_task_steps(session_id, step_index)")

        # ===== S0 新增索引（10.1.7①，对齐文档2 3.1.8-⑥）— 小欧 2026-08-16 =====
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON chat_tasks(session_id)")
        # chat_task_steps 复合索引：按 ai_message_id 与 (task_id, step_index)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_task ON chat_task_steps(task_id, step_index)")
        # chat_messages 索引：按 task_id / timestamp（10.1.7① ② 权威=idx_msg_timestamp）— 小欧 2026-08-16
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_task ON chat_messages(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON chat_messages(timestamp)")
        # token_usage 五索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_session ON token_usage(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_task ON token_usage(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_llm_call ON token_usage(llm_call_count)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_model ON token_usage(model)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_created ON token_usage(created_at)")
        # chat_session_trust 索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trust_session ON chat_session_trust(session_id)")

        # v2.0: 旧 execution_steps 列退役(结构迁移已前移至索引之前执行) — 小欧 2026-08-19


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
