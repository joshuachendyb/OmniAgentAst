-- v2.0 核心数据模型重构迁移脚本 — 小欧 2026-08-19
-- 执行条件：停服窗口，无并发写入
-- 幂等：SQLite 不支持 IF EXISTS 改名 / DROP COLUMN，须应用层 PRAGMA 守卫（见各步注释与前置守卫）

-- 0. 应用层前置守卫（Python 伪代码，所有 ALTER 执行前先做存在性判断，已迁移则跳过，保证可重复执行）
--      tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
--      def table_exists(t): return t in tables
--      def col_exists(t, c): return c in {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}

-- 1. 改名 chat_message_steps → chat_task_steps
--    ⚠ 撞表风险（小健 2026-08-19 P0-3）：db_initializer 启动时会 CREATE TABLE IF NOT EXISTS chat_task_steps（空表）；
--      若 chat_task_steps 已存在，须先 DROP 空表再 RENAME，否则报 "table chat_task_steps already exists"。
--    应用层守卫：
--      if table_exists('chat_message_steps'):
--          if table_exists('chat_task_steps'):
--              conn.execute("DROP TABLE chat_task_steps")   -- 仅 db_initializer 建好的空表，无数据，安全
--          conn.execute("ALTER TABLE chat_message_steps RENAME TO chat_task_steps")
ALTER TABLE chat_message_steps RENAME TO chat_task_steps;

-- 1.2 chat_task_steps 列改名 message_id → ai_message_id（与 chat_tasks.ai_message_id 同名贯通）— 小健 2026-08-19 P0-1
--    SQLite 3.25+ 支持 RENAME COLUMN；重复执行报 no such column，应用层 col_exists('chat_task_steps','message_id') 守卫
ALTER TABLE chat_task_steps RENAME COLUMN message_id TO ai_message_id;

-- 1.5 chat_messages 列改名 reply_to_message_id → user_message_id（与chat_tasks/chat_task_steps同名贯通）
--    SQLite 3.25+ 支持 RENAME COLUMN；重复执行报 no such column，应用层 col_exists('chat_messages','reply_to_message_id') 守卫
ALTER TABLE chat_messages RENAME COLUMN reply_to_message_id TO user_message_id;

-- 2. 为 chat_task_steps 新增 usage 列（col_exists 守卫）
ALTER TABLE chat_task_steps ADD COLUMN usage TEXT;

-- 2.5 为 chat_task_steps 新增 user_message_id 列（冗余免 JOIN，改动10）— 小欧 2026-08-19（col_exists 守卫）
ALTER TABLE chat_task_steps ADD COLUMN user_message_id INTEGER;

-- 3. 新建 chat_user_message 表
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

-- 3.5 历史回灌 chat_user_message（小健 2026-08-19 关联逻辑补全：保证旧任务 C1 详情可读，避免功能退化）
--    SQLite 不支持 SELECT→多行展开，应用层 Python 循环：
--      for row in conn.execute("SELECT id, session_id, content, client_os, browser, device, network, created_at FROM chat_messages WHERE role='user'"):
--          conn.execute("INSERT OR IGNORE INTO chat_user_message(id, session_id, content, client_os, browser, device, network, created_at) VALUES(?,?,?,?,?,?,?,?)",
--                       (row['id'], row['session_id'], row['content'], row['client_os'], row['browser'], row['device'], row['network'], row['created_at']))
--      conn.commit()
--    说明：chat_user_message.id 显式取 chat_messages.id（一对一贯通，与 P0-2 修复一致）

-- 4. 清 chat_session_title_history 死表
DROP TABLE IF EXISTS chat_session_title_history;

-- 5. chat_tasks 新增 ai_message_id 列（补齐 task→assistant 消息直达关联，与 chat_task_steps.ai_message_id 对称）— 小欧 2026-08-19（col_exists 守卫）
ALTER TABLE chat_tasks ADD COLUMN ai_message_id INTEGER;

-- 6. 冻结 chat_messages：不再写入（代码层面冻结，不删表不删列，存量保留降级可读）
-- 不做 DDL 变更，仅由代码保证新链路不写 chat_messages

-- 7. 清死字段与冗余索引
-- chat_messages.metadata（已在chat_messages冻结范畴，代码不再写入，列保留不删）
-- chat_sessions.metadata 死字段（SQLite 不支持 DROP COLUMN IF EXISTS，col_exists 守卫）
ALTER TABLE chat_sessions DROP COLUMN metadata;
-- chat_tasks.metadata 死字段（col_exists 守卫）
ALTER TABLE chat_tasks DROP COLUMN metadata;
-- 删除冗余 timestamp 双索引（保留 idx_msg_timestamp）
DROP INDEX IF EXISTS idx_messages_timestamp;

-- 8. 历史 144 行 execution_steps 回灌 chat_task_steps（改动2 保底，5.4 已证实数据）— 小健 2026-08-19 P1-6
--    SQLite 不支持 SELECT→多行展开，应用层 Python 循环（迁移登记名：backfill_steps_from_execution_steps_column）：
--      for row in conn.execute("SELECT id, session_id, task_id, execution_steps, user_message_id FROM chat_messages WHERE role='assistant' AND execution_steps IS NOT NULL"):
--          steps = parse_json(row['execution_steps']) or []
--          for idx, d in enumerate(steps, start=1):
--              conn.execute(
--                  "INSERT INTO chat_task_steps(task_id, ai_message_id, session_id, step_index, step_data, usage, user_message_id) "
--                  "VALUES(?,?,?,?,?,?,?)",
--                  (row['task_id'], row['id'], row['session_id'], idx,
--                   json.dumps(d, ensure_ascii=False), d.get('usage'), row['user_message_id']))
--      conn.commit()
--    说明：ai_message_id 取该 assistant 消息 chat_messages.id（改名后为 user_message_id 即 reply 目标）；user_message_id 取 chat_messages.user_message_id
