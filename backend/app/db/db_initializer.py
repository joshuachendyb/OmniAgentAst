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
# 2026-08-20 - 小欧 - 11.1 token 四层同构: 新增 task_accumulated_tokens/session_accumulated_tokens 实时累计列(落库口径与 react_cycle 同源); 新增 _verify_acc_columns() 复核落库, 防 _ensure_column 隐性失败致隐性 OperationalError
# 2026-08-21 - 小欧 - 12.2-C1/C2/C5/Q7/Q8(按文档[1]12.2 diff设计落地): ①C1-D1 chat_task_steps去重+唯一索引(idx_steps_unique); ②C2-D1 token_usage去重+唯一索引(idx_token_usage_task_call); ③C5-D1 启动期空白AI行清扫(标败不删行); ④Q7-D2 init_operations_db拆分——移除timers DDL+新增init_timers_db独立函数(新库TEXT时间列=Q8落地); ⑤Q8-D1 新库timers.db三列TEXT(老列不动, SQLite不支持ALTER COLUMN)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 定: chat_sessions.sessionModel 结构化落地 + 旧 model_override 兼容迁移:
#   ①_ensure_column 补 sessionModel TEXT(会话级模型覆盖落库点); ②旧列 model_override 兼容: 存在则 RENAME COLUMN 到 sessionModel(现代 SQLite),
#     回退路径先建 sessionModel 列再尝试 DROP 旧列(失败保留无害); 旧裸字符串数据缺 provider 不复制(免污染 JSON 解析);
#   ③修正初版回退缺陷(原 UPDATE 引用尚未创建的 sessionModel 列致初始化崩溃)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.2: 三表归一幂等迁移——chat_tasks(provider/model/display_name→
#   sessionModel JSON)、token_usage(model/provider→task_model JSON)、chat_user_message(model/provider→chat_model JSON),
#   老库 PRAGMA 查列后 ALTER 补列+旧行数据回灌(旧列废弃保留不删); idx_token_model 改 json_extract 表达式索引
# 2026-08-23 - 小欧 - 三轮三堂会审修复: ①P0 新增 _verify_model_ref_columns fail-loud 硬校验(迁移吞异常则三写路径
#   全线崩, 仿 _verify_acc_columns 先例); ②P1 chat_tasks.sessionModel 新建 DDL 补 NOT NULL(insert_task 必填,
#   与 token_usage.task_model 约束对称)
# 2026-08-23 - 小欧 - 回归bug#2修复(token_usage.model NOT NULL): 原"旧列废弃保留不删"对 token_usage 不完整——
#   旧 model 列带 NOT NULL 约束, token_usage_insert 只写 task_model 不写 model → 新行 model=NULL 触发
#   NOT NULL constraint failed, 全部任务落库失败; 旧 idx_token_model 为 model 裸列索引(DDL:CREATE INDEX IF NOT EXISTS
#   因重名跳过未替换为 json_extract), DROP 列前须先删; 故迁移收尾: DROP 旧 idx_token_model → 建 json_extract 表达式索引
#   (与 DDL:245 对齐) → ALTER DROP COLUMN model/provider(已无代码引用, 干净归一并解除 NOT NULL 约束)
# 2026-08-23 - 小欧 - 锚B解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): chat_task_steps 外键退役——
#   新建 DDL 删 FOREIGN KEY(ai_message_id) REFERENCES chat_messages(id) ON DELETE CASCADE 行;
#   老库经幂等表重建迁移(查 sqlite_master DDL 含旧引用→建新表→复制→DROP子表→RENAME), 位于索引创建之前。
#   动因: foreign_keys=ON 下该外键是硬依赖(步骤落库要求 chat_messages 行存在/删行级联删步骤),
#   解除后 ai_message_id 为纯贯通键, chat_messages 对系统彻底无结构性约束; W7 启动清扫 UPDATE 加 TODO 删除注释
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.7.1 D7/11.9 P5): chat_tasks 加 files_dir 列
#   (TEXT DEFAULT '', _ensure_column 幂等)——任务级文件A/B 目录引用 $dir=files/{session_id}/{task_id}/,
#   排查定位锚: 任务→files_dir→文件A 按 step/tool_no/retry_no 三键组定位→顺链文件B; orchestrator 同事务写入
# 2026-08-24 - 小欧 - 目录前导(北京老陈裁定, 仅注释更正防失真, 本文件零代码改动): files_dir 实际值改为
#       files/Sion_{session_id}/Task_{task_id}/(前缀常量定义于 file_persist, orchestrator 同源拼装落库)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除W7启动清扫UPDATE chat_messages(崩溃残留空白AI行标败), 系统对该表零写依赖
# 2026-08-27 - 小欧 - 阶段3(chat_messages表退役): 停建表——移除CREATE TABLE chat_messages及铁律注释、_ensure_column补齐(timestamp/display_name/client_os等/status/thought/task_id列)、idx_messages_session/idx_msg_task/idx_msg_timestamp索引; init_chat_db末尾真实DROP TABLE chat_messages(旧库历史数据已先由migrate_v2_chat_restructure回灌结构化表, 不丢数据); 系统对该表零依赖
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5⑤①(北京老陈定案, 详见doc-9月优化/会话信任功能修复方案): chat_session_trust 表结构+迁移——
#  path 列(TEXT, NULL=无路径工具的工具级通配; 非空=该路径及子目录树前缀递归豁免), UNIQUE 从(session_id,tool_name)扩为(session_id,tool_name,path)支持同工具多路径行;
#  建表后插入迁移段: PRAGMA table_info 检测旧表无 path 列→DROP 重建(存量工具级信任全部视为无效清空, 定案"存量全部清空不迁移")→新库含path列跳过
"""
db_initializer — 数据库初始化

职责: 创建表、确保字段存在
小欧 2026-06-18 从database.py拆分，遵守SRP
"""
import sqlite3
import json as _json
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
            

            
            -- 独立步骤表 — 小欧 2026-07-14; v2.0 改名 chat_task_steps — 小欧 2026-08-19
            -- 锚B解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): 外键 REFERENCES chat_messages(id)
            --   已退役(旧库经下方幂等表重建迁移); ai_message_id 为纯贯通键, 与 chat_tasks.ai_message_id 同名同值,
            --   不再外键引用任何表 — 小欧 2026-08-23
            CREATE TABLE IF NOT EXISTS chat_task_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ai_message_id INTEGER NOT NULL,  -- v2.0 改名: message_id → ai_message_id, 与代码变量同名贯通
                session_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_json TEXT NOT NULL,
                created_at TEXT,  -- 本地ISO无Z
                task_id TEXT,
                usage TEXT,
                user_message_id INTEGER  -- v2.0 冗余：免 JOIN 直达 user 消息 — 小欧 2026-08-19
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
                sessionModel TEXT NOT NULL,                          -- 归一 JSON(ModelRef) 单列; display_name 列废弃(设计要求2); 三堂会审 P1: 任务行创建必有模型, 与 token_usage.task_model 约束对称 — 小欧 2026-08-22
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
                task_model TEXT NOT NULL,          -- 归一 JSON(ModelRef) 单列(设计6.2: NOT NULL) — 小欧 2026-08-22
                prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0, total_tokens INTEGER DEFAULT 0,
                created_at TEXT
            );

            -- ⑤ chat_session_trust 新建（B3：HITL 会话信任清单，权威=文档2 3.1.7）
            -- v1.5(2026-09-02 小欧, 北京老陈定案): 信任精确到 tool+path——
            --   path 列: NULL=无路径工具的工具级通配; 非空=该路径及其子目录树递归(前缀递归);
            --   UNIQUE 从 (session_id, tool_name) 扩为 (session_id, tool_name, path) 支持同工具多路径行
            CREATE TABLE IF NOT EXISTS chat_session_trust (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                path TEXT,
                created_at TEXT,
                UNIQUE(session_id, tool_name, path),
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
                chat_model TEXT,   -- 归一 JSON(ModelRef) 单列 — 小欧 2026-08-22
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
        

        




        # ===== S0 补列（10.1.7① ②③，幂等只 ADD 缺列、老行 NULL 不丢数据）— 小欧 2026-08-16 =====
        # ② chat_task_steps 补 task_id 列（B1 挂任务；对齐文档2 3.1.8-⑥）
        _ensure_column(conn, "chat_task_steps", "task_id", "TEXT")
        # ③ chat_sessions 补 sessionModel 列(会话级模型覆盖落库点, 结构化 provider+model 的 JSON)
        # 旧列 model_override 兼容迁移: 存在则改名(现代 SQLite); 老 SQLite 不支持 RENAME 时降级为
        # 先建目标列再尝试删旧列(失败则保留, 无害)。旧 model_override 是裸字符串(缺 provider),
        # 无法映射结构化, 故不复制数据(复制会污染 sessionModel 致解析失败) — 北京老陈 2026-08-22
        _cur = conn.execute("PRAGMA table_info(chat_sessions)")
        _cols = [r[1] for r in _cur.fetchall()]
        if "model_override" in _cols:
            if "sessionModel" not in _cols:
                try:
                    conn.execute("ALTER TABLE chat_sessions RENAME COLUMN model_override TO sessionModel")
                except Exception:
                    _ensure_column(conn, "chat_sessions", "sessionModel", "TEXT")
                    try:
                        conn.execute("ALTER TABLE chat_sessions DROP COLUMN model_override")
                    except Exception:
                        pass  # 老 SQLite 不支持 DROP COLUMN, 保留旧列无害
            else:
                # sessionModel 已存在, 旧列冗余, 尝试删除
                try:
                    conn.execute("ALTER TABLE chat_sessions DROP COLUMN model_override")
                except Exception:
                    pass
        _ensure_column(conn, "chat_sessions", "sessionModel", "TEXT")    # L2 会话级模型覆盖落库点
        # 11.1 token 四层同构：任务级/会话级实时累计列 — 小欧 2026-08-20
        _ensure_column(conn, "chat_tasks", "task_accumulated_tokens", "TEXT DEFAULT '{}'")
        _ensure_column(conn, "chat_sessions", "session_accumulated_tokens", "TEXT DEFAULT '{}'")
        # 文件A/B 排查目录引用(文档[1]11.7.5-1 $dir / 11.8.7.1 D7 #5) — 物理目录 = files/Sion_{session_id}/Task_{task_id}/(前导 2026-08-24 北京老陈裁定)
        _ensure_column(conn, "chat_tasks", "files_dir", "TEXT DEFAULT ''")   # 11.9 P5 — 小欧 2026-08-23
        # 11.1 增强: 复核新增列确已落库, 缺失则显式抛出, 避免后续 SELECT/UPDATE 隐性 OperationalError 致任务链崩溃 — 小欧 2026-08-20
        _verify_acc_columns(conn)

        # ===== 归一迁移(小欧 2026-08-22 报告v1.25 6.2): 三表旧分离列 → JSON 单列, 幂等(查列→补列→回灌) =====
        # 旧 model/provider/display_name 列废弃保留不删(SQLite DROP 兼容性差, 保留无害), 读写一律走新 JSON 列
        _migrate_model_ref_columns(conn)
        # 三堂会审修复(P0·小欧): 三写路径(insert_task/token_usage_insert/update_user_message_final)每任务强依赖
        #   新 JSON 列, 补列失败若静默降级则全部任务落库崩溃——仿 _verify_acc_columns 先例 fail-loud 硬校验
        _verify_model_ref_columns(conn)

        # v2.0 结构迁移 — 小欧 2026-08-19
        #  ①必须在 _ensure_column 之后(_ensure_column 为回灌 SELECT 补齐 client_os/timestamp 等列)
        #  ②必须在建 idx_steps_message 索引之前(索引依赖迁移改名后的 ai_message_id 列)
        #  ③migrate_steps 顶层依赖 storage→db→database→db_initializer 存在循环导入, 采用函数内延迟 import
        from app.services.chat.migrate_steps import migrate_v2_chat_restructure
        migrate_v2_chat_restructure(get_conn)

        # ===== 锚B解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): chat_task_steps 外键退役 =====
        # 旧 DDL: FOREIGN KEY(ai_message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
        # 在 PRAGMA foreign_keys=ON(database.py:172) 下是硬依赖: 步骤落库要求 chat_messages 行存在,
        # 删 chat_messages 行会 CASCADE 级联删步骤数据。解除后 ai_message_id 为纯贯通键
        # (与 chat_tasks.ai_message_id 同名同值), 不再外键引用任何表。
        # SQLite 不支持 ALTER 外键 → 幂等表重建(建新表→复制→DROP子表→RENAME), 仅当 sqlite_master DDL
        # 仍含旧引用时执行一次; 被重建的是子表, FK=ON 下 DROP 子表不违规, 无需摆弄 foreign_keys pragma。
        # 时序(三堂会审实证修正 小欧 2026-08-23): 必须位于 migrate_v2_chat_restructure 之后
        #   (message_id→ai_message_id 改名收敛后, 重建 SELECT 才能引用新列名)、
        #   位于本函数索引创建(idx_steps_*)之前——DROP TABLE 会连带删旧索引
        _fk_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='chat_task_steps'"
        ).fetchone()
        if _fk_sql and _fk_sql["sql"] and "REFERENCES chat_messages" in _fk_sql["sql"]:
            conn.executescript("""
                CREATE TABLE chat_task_steps_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_message_id INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    step_json TEXT NOT NULL,
                    created_at TEXT,
                    task_id TEXT,
                    usage TEXT,
                    user_message_id INTEGER
                );
                INSERT INTO chat_task_steps_new
                    SELECT id, ai_message_id, session_id, step_index, step_json,
                           created_at, task_id, usage, user_message_id
                    FROM chat_task_steps;
                DROP TABLE chat_task_steps;
                ALTER TABLE chat_task_steps_new RENAME TO chat_task_steps;
            """)
            logger.info("[init] chat_task_steps 外键已退役(不再 REFERENCES chat_messages), 幂等表重建完成")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON chat_sessions(updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_deleted ON chat_sessions(is_deleted)")


        # steps 表索引 — 小欧 2026-07-14
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_message ON chat_task_steps(ai_message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_session ON chat_task_steps(session_id, step_index)")

        # ===== S0 新增索引（10.1.7①，对齐文档2 3.1.8-⑥）— 小欧 2026-08-16 =====
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON chat_tasks(session_id)")
        # chat_task_steps 复合索引：按 ai_message_id 与 (task_id, step_index)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_task ON chat_task_steps(task_id, step_index)")

        # token_usage 五索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_session ON token_usage(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_task ON token_usage(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_llm_call ON token_usage(llm_call_count)")
        # 归一(小欧 2026-08-22): 旧 model 裸列索引 → task_model JSON 表达式索引(query_token_usage json_extract 过滤走此索引)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_model "
            "ON token_usage(json_extract(task_model,'$.provider'), json_extract(task_model,'$.model'))")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_token_created ON token_usage(created_at)")
        # chat_session_trust 索引
        # v1.5(2026-09-02 小欧): 存量信任全部视为无效(定案) + 加 path 列——检测到旧表无 path 列即重建(清空存量)
        _trust_cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_session_trust)").fetchall()]
        if "path" not in _trust_cols:
            conn.execute("DROP TABLE chat_session_trust")
            conn.execute("""CREATE TABLE chat_session_trust (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                path TEXT,
                created_at TEXT,
                UNIQUE(session_id, tool_name, path),
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE)""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trust_session ON chat_session_trust(session_id)")

        # ===== 12.2-C1: 步骤唯一性下沉DB — 同一AI行×同一任务×同一序号恰一行 =====
        # 老库先去重(保首行)再建唯一索引(均幂等); append_execution_step 保持裸INSERT不改,
        # UNIQUE冲突即bug, fail-loud暴露(与database.py get_conn_with_retry 哲学一致) — 小欧 2026-08-21
        conn.execute(
            "DELETE FROM chat_task_steps WHERE rowid NOT IN ("
            "  SELECT MIN(rowid) FROM chat_task_steps"
            "  GROUP BY ai_message_id, IFNULL(task_id,''), step_index)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_steps_unique "
            "ON chat_task_steps(ai_message_id, task_id, step_index)")

        # ===== 12.2-C2: token明细唯一性 — 同任务×同步号(llm_call_count实为记录时步号)恰一行 =====
        # 老库先去重再建唯一索引(均幂等); task_id为NOT NULL列无NULL分组歧义 — 小欧 2026-08-21
        conn.execute(
            "DELETE FROM token_usage WHERE rowid NOT IN ("
            "  SELECT MIN(rowid) FROM token_usage GROUP BY task_id, llm_call_count)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_token_usage_task_call "
            "ON token_usage(task_id, llm_call_count)")

        # 镜像写点 W7(启动清扫 UPDATE chat_messages 崩溃残留空白AI行) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27

        # v2.0: 旧 execution_steps 列退役(结构迁移已前移至索引之前执行) — 小欧 2026-08-19


def init_operations_db(get_conn):
    """初始化操作数据库（文件操作域）
    历史遗留说明(12.2-Q8): 老 operations.db 中 file_operations 时间列为 TEXT(本地ISO无Z)、
    timers 表时间列为 TIMESTAMP(实存本地ISO TEXT, NUMERIC亲和) — 类型混用为历史遗留,
    SQLite 不支持 ALTER COLUMN 故老列不动; 新库一律 TEXT。— 小欧 2026-08-21 (12.2-Q7 拆分)"""
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
            
            CREATE INDEX IF NOT EXISTS idx_operations_session ON file_operations(task_id);
            CREATE INDEX IF NOT EXISTS idx_operations_created ON file_operations(created_at);
        ''')


def init_timers_db(get_conn):
    """初始化定时器数据库（独立域）— 12.2-Q7 新增 — 小欧 2026-08-21"""
    with get_conn("timers") as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS timers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timer_id TEXT UNIQUE NOT NULL,
                delay REAL NOT NULL,
                callback TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,   -- 本地ISO无Z (12.2-Q8: 新表一律TEXT)
                trigger_at TEXT NOT NULL,   -- 本地ISO无Z (12.2-Q8)
                triggered_at TEXT,          -- 本地ISO无Z (12.2-Q8)
                status TEXT NOT NULL DEFAULT 'active'
            );
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

        # 阶段3(chat_messages表退役): 建表DDL/列补齐/索引已全部移除, 此处真实删除该表。
        # 时序保障: 本 DROP 位于 init_chat_db 内所有 migrate(含 migrate_v2_chat_restructure 历史数据
        # 回灌 chat_user_message/chat_tasks)与索引创建之后, 旧库 chat_messages 历史数据已被结构化表承载后再删,
        # 不丢数据; 运行时已零读 chat_messages(阶段1/2 验证)。 — 小欧 2026-08-27
        conn.execute("DROP TABLE IF EXISTS chat_messages")


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


def _verify_acc_columns(conn: sqlite3.Connection) -> None:
    """复核 11.1 token 累计列确已落库(防止 _ensure_column 隐性失败致后续 SELECT/UPDATE 隐性 OperationalError 崩溃) — 小欧 2026-08-20"""
    _checks = [("chat_tasks", "task_accumulated_tokens"), ("chat_sessions", "session_accumulated_tokens")]
    for _t, _c in _checks:
        _rows = conn.execute(f"PRAGMA table_info({_t})").fetchall()
        if _c.lower() not in {r["name"].lower() for r in _rows}:
            raise RuntimeError(f"token 累计列缺失(迁移失败): {_t}.{_c}")


def _verify_model_ref_columns(conn: sqlite3.Connection) -> None:
    """复核归一 JSON 列确已落库(仿 _verify_acc_columns: 缺失显式抛出, 防写路径隐性 OperationalError 全线崩) — 三堂会审 P0 修复 小欧"""
    _checks = [("chat_tasks", "sessionModel"), ("token_usage", "task_model"), ("chat_user_message", "chat_model")]
    for _t, _c in _checks:
        _rows = conn.execute(f"PRAGMA table_info({_t})").fetchall()
        if _c.lower() not in {r["name"].lower() for r in _rows}:
            raise RuntimeError(f"model 归一列缺失(迁移失败): {_t}.{_c}")


def _migrate_model_ref_columns(conn: sqlite3.Connection) -> None:
    """归一迁移(小欧 2026-08-22 报告v1.25 6.2): 三表旧分离列旧行 → JSON(ModelRef) 单列, 幂等可重复执行。
    策略: PRAGMA 查列→缺则 ALTER 补列→旧行回灌 JSON; 旧列默认废弃保留不删, 读写一律走新 JSON 列。
    例外(小欧 2026-08-23): token_usage.model 带 NOT NULL 约束, token_usage_insert 只写 task_model 不写 model →
    新行 model=NULL 触发 NOT NULL 约束失败, 故 token_usage 分支回灌后 DROP 旧 model/provider 列(解约束+彻底归一);
    chat_tasks/chat_user_message 旧列本就可空, 保留不删(最小改动, YAGNI)。
    chat_tasks: provider/model/display_name → sessionModel;
    token_usage: model/provider → task_model; chat_user_message: model/provider → chat_model。"""
    # 1) chat_tasks: 三列 → sessionModel JSON
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_tasks)").fetchall()]
        if ("provider" in cols or "model" in cols) and "sessionModel" not in cols:
            conn.execute("ALTER TABLE chat_tasks ADD COLUMN sessionModel TEXT")
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_tasks)").fetchall()]
        if "sessionModel" in cols and "provider" in cols:
            for r in conn.execute(
                    "SELECT task_id, provider, model, display_name FROM chat_tasks "
                    "WHERE sessionModel IS NULL AND (provider IS NOT NULL OR model IS NOT NULL)").fetchall():
                j = _json.dumps({"provider": r["provider"], "model": r["model"],
                                 "display_name": r["display_name"]})
                conn.execute("UPDATE chat_tasks SET sessionModel=? WHERE task_id=?", (j, r["task_id"]))
    except Exception as e:
        logger.warning(f"[归一迁移] chat_tasks 回灌失败(降级不阻断启动): {e}")

    # 2) token_usage: 两列 → task_model JSON
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(token_usage)").fetchall()]
        if "model" in cols and "task_model" not in cols:
            conn.execute("ALTER TABLE token_usage ADD COLUMN task_model TEXT")
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(token_usage)").fetchall()]
        if "task_model" in cols and "model" in cols:
            for r in conn.execute(
                    "SELECT id, model, provider FROM token_usage "
                    "WHERE task_model IS NULL AND (model IS NOT NULL OR provider IS NOT NULL)").fetchall():
                j = _json.dumps({"provider": r["provider"], "model": r["model"]})
                conn.execute("UPDATE token_usage SET task_model=? WHERE id=?", (j, r["id"]))
            # 归一收尾(小欧 2026-08-23): 删旧 model 列 — 其 NOT NULL 约束致 token_usage_insert 只写 task_model 不写
            # model → 新行 model=NULL 触发 NOT NULL constraint failed, 全部任务落库失败; 旧 idx_token_model 为 model 裸列
            # 索引(DDL:CREATE INDEX IF NOT EXISTS 因重名跳过未替换为 json_extract), DROP 列前须先删; 故: 删旧索引 →
            # 建 json_extract 表达式索引(与 DDL:245 对齐) → ALTER DROP COLUMN model/provider(已无代码引用, 干净解约束)
            conn.execute("DROP INDEX IF EXISTS idx_token_model")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_token_model "
                "ON token_usage(json_extract(task_model,'$.provider'), json_extract(task_model,'$.model'))")
            conn.execute("ALTER TABLE token_usage DROP COLUMN model")
            if "provider" in cols:
                conn.execute("ALTER TABLE token_usage DROP COLUMN provider")
    except Exception as e:
        logger.warning(f"[归一迁移] token_usage 回灌失败(降级不阻断启动): {e}")

    # 3) chat_user_message: 两列 → chat_model JSON
    try:
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_user_message)").fetchall()]
        if "model" in cols and "chat_model" not in cols:
            conn.execute("ALTER TABLE chat_user_message ADD COLUMN chat_model TEXT")
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(chat_user_message)").fetchall()]
        if "chat_model" in cols and "model" in cols:
            for r in conn.execute(
                    "SELECT id, model, provider FROM chat_user_message "
                    "WHERE chat_model IS NULL AND (model IS NOT NULL OR provider IS NOT NULL)").fetchall():
                j = _json.dumps({"provider": r["provider"], "model": r["model"]})
                conn.execute("UPDATE chat_user_message SET chat_model=? WHERE id=?", (j, r["id"]))
    except Exception as e:
        logger.warning(f"[归一迁移] chat_user_message 回灌失败(降级不阻断启动): {e}")
