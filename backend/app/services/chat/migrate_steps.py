# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #5 fix: _needs_migration final分支补response字段
# 2026-08-19 小欧 v2.0: chat_messages.execution_steps 列随冻结废弃删除, migrate_execution_steps_status
#   加"列存在"守卫(PRAGMA table_info 判断), 新库无此列直接跳过, 防触发时报 no such column
# 2026-08-19 小欧 v2.0结构迁移: 新增 migrate_v2_chat_restructure, 复用 schema_migrations 登记机制,
#   完成 chat_message_steps→chat_task_steps 改名/列改名/加列、metadata 清理、title_history 清死表、
#   execution_steps→chat_task_steps 回灌、chat_user_message 回灌, 支持现网中间态库幂等收敛
# 2026-08-19 小欧 v2.0迁移补全: 补第8步 删 chat_sessions.metadata/chat_tasks.metadata/idx_messages_timestamp
#   (对齐 v2_chat_restructure.sql 第7步, 首版漏实现); 第7步 execution_steps 回灌加"ai_message_id 已有行即跳过"
#   幂等守卫(对齐文档9.6 line407, 防登记丢失重跑导致重复回灌)
# 2026-08-19 小欧 v2.0迁移补全2: 步骤6 回灌 chat_user_message 后新增 6.5 反向回填 task_id
#   (由 chat_tasks.user_message_id 关联补上, 历史回灌只复制 content 无 task_id, 否则 C1 按 task_id 查 user 消息全落空)
# 2026-08-19 小欧 v2.0迁移补全3: 新增 6.6 回填 chat_tasks.ai_message_id
#   (由同session内相邻 assistant 消息补上 user+1; user↔assistant id 相邻配对对齐 storage.allocate;
#    历史迁移漏带此列导致 ai_message_id 全空, 幂等仅回填为空的行)
# 2026-08-27 小欧 阶段3(chat_messages表退役): migrate_execution_steps_status 新增"表存在"守卫(_table_exists), 表已DROP则跳过迁移, 防 PRAGMA table_info(chat_messages) 表不存在时报 no such table
# 2026-08-27 小欧 阶段3(chat_messages表退役)清理: 整删migrate_execution_steps_status死函数(全backend无调用方)及其MIGRATION_NAME常量、migrate_v2_chat_restructure块5/6/7(chat_messages双列/回灌chat_user_message/chat_task_steps, 表已DROP永跳过)死分支; scripts/migrate_utc_to_local.py与migrate_time_format.py(硬编码引用已退役chat_messages列)删除; 系统对该表零残留运行代码引用
# 2026-07-18 小欧 #5 fix: _needs_migration final分支补齐response字段(与_migrate_one_step一致); 取消文本仅存response的历史消息不再漏迁移误判完成(恢复docstring改写时误删的第二板块同条记录, 禁止删除历史)
# 2026-09-07 小欧 4.4.1(B7/B8): 规则#3 incident_value=cancelled 改产 type=final+outcome=cancelled; 规则#4 旧取消FinalStep 改原地补 outcome=cancelled(不再重建 type=cancelled dict, 保字段不丢)
# 2026-09-07 小欧 4.4.1旧case清零(北京老陈裁定删死代码): 删 _needs_migration/_migrate_one_step/_confirm_id_of 三死函数及 typing/json_utils/storage 死导入(驱动 migrate_execution_steps_status 已于 2026-08-27 删除, 零调用方); 旧取消行改写另立新一次性行迁移 migrate_cancelled_rows_to_final 承接
# 2026-09-07 小欧 4.4.1(B7/B8): 规则#3 incident_value=cancelled 改产 type=final+outcome=cancelled;
#   规则#4 旧取消 FinalStep 改原地补 outcome=cancelled(不再重建 type=cancelled dict, 保字段不丢);
#   模块 docstring 目标表示同步; _needs_migration 检测条件不变(两类旧标记仍需迁移, 仅目标表示变)
"""
migrate_steps — 数据迁移

背景: 4.4.1(2026-09-07)前取消终态曾用 type='cancelled' 事件步; 4.4.1 起取消收尾单一由
type=final+outcome=cancelled 承担, 前端不再消费 cancelled 事件。本模块提供
migrate_cancelled_rows_to_final, 在 init_chat_db 末尾幂等执行一次, 将
chat_task_steps.step_json 中 type='cancelled' 的历史行改写为
type=final+outcome=cancelled(content/timestamp/step 原样保留), 与运行期新契约同口径。
改写后徽章推导(useTaskInfo 认 final+cancelled)与终态推导(derive_status_from_steps 读
最后一条 final)对历史取消消息恢复正确。

一次性守卫: 用 chat 库 schema_migrations 表登记"已执行",
跑过一次后续启动直接跳过全表扫描(沿用 2026-07-13 守卫机制)。
"""

from app.logger import logger


def _ensure_migrations_table(conn):
    """确保迁移记录表存在(chat 库) — 小欧 2026-07-13
    用于登记"一次性迁移"是否已执行, 避免每次启动重跑。
    """
    conn.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def _is_migration_applied(conn, name: str) -> bool:
    """该一次性迁移是否已执行过 — 小欧 2026-07-13

    用途: 避免每次启动都对 chat_messages 做全表扫描。
    背景: 该迁移原本每次启动无条件执行, 对 2.5GB 聊天库扫描 3107 行并逐行
          JSON 解析, 单次耗时约 25s, 是启动变慢的根因。加守卫后只跑一次。
    """
    _ensure_migrations_table(conn)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM schema_migrations WHERE name=?", (name,))
    return cur.fetchone() is not None


def _mark_migration_applied(conn, name: str) -> None:
    """标记该一次性迁移已执行(幂等) — 小欧 2026-07-13"""
    _ensure_migrations_table(conn)
    conn.execute("INSERT OR IGNORE INTO schema_migrations(name) VALUES(?)", (name,))





V2_MIGRATION_NAME = "migrate_v2_chat_restructure"


def _table_exists(conn, table: str) -> bool:
    """表是否存在 — 小欧 2026-08-19"""
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _col_exists(conn, table: str, column: str) -> bool:
    """表中列是否存在 — 小欧 2026-08-19"""
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    return column in cols


def migrate_v2_chat_restructure(get_conn) -> bool:
    """v2.0 核心数据模型结构迁移(现网中间态库幂等收敛) — 小欧 2026-08-19

    背景: 现网库处于 v2.0 冻结"中间态" — 新代码 db_initializer 已建新结构表,
    但旧库存的 chat_message_steps(150万行)/chat_task_steps(旧结构空表)/双列并存等
    未收敛, 导致新代码写库报 no such column。本迁移在 init_chat_db 末尾幂等执行:
      1. 改名 chat_message_steps→chat_task_steps(撞表先 DROP 空表)
      2. chat_task_steps 列 message_id→ai_message_id
      3. chat_task_steps 加 usage / user_message_id 列
       4. chat_tasks 加 ai_message_id 列
       5-7. (已随 chat_messages 表退役整体移除: 双列处理/回灌 chat_user_message/chat_task_steps 均依赖已删表)
       8. 清死字段与冗余索引: DROP chat_sessions.metadata / chat_tasks.metadata / idx_messages_timestamp
      9. 清 chat_session_title_history 死表
      10. 返值: 本次是否实际执行迁移(False=已登记跳过)

    一次性守卫: 复用 schema_migrations 登记, 跑过一次后续启动直接跳过。
    10规范(复用优先): 复用 _is_migration_applied / _mark_migration_applied。
    """
    import time as _time
    _t0 = _time.time()
    with get_conn("chat") as conn:
        if _is_migration_applied(conn, V2_MIGRATION_NAME):
            logger.info(f"[migrate] {V2_MIGRATION_NAME} 已执行过, 跳过")
            logger.info(f"[启动耗时] migrate_v2_chat_restructure: {_time.time()-_t0:.3f}s (skipped)")
            return False

        # 1. chat_message_steps→chat_task_steps 改名(撞表守卫) — 小欧 2026-08-19
        if _table_exists(conn, "chat_message_steps"):
            if _table_exists(conn, "chat_task_steps"):
                conn.execute("DROP TABLE chat_task_steps")  # 仅旧结构空表, 无数据安全
            conn.execute("ALTER TABLE chat_message_steps RENAME TO chat_task_steps")

        # 2. chat_task_steps 列 message_id→ai_message_id — 小欧 2026-08-19
        if _table_exists(conn, "chat_task_steps") and _col_exists(conn, "chat_task_steps", "message_id"):
            conn.execute("ALTER TABLE chat_task_steps RENAME COLUMN message_id TO ai_message_id")

        # 3. chat_task_steps 加 usage / user_message_id — 小欧 2026-08-19
        if _table_exists(conn, "chat_task_steps"):
            if not _col_exists(conn, "chat_task_steps", "usage"):
                conn.execute("ALTER TABLE chat_task_steps ADD COLUMN usage TEXT")
            if not _col_exists(conn, "chat_task_steps", "user_message_id"):
                conn.execute("ALTER TABLE chat_task_steps ADD COLUMN user_message_id INTEGER")

        # 4. chat_tasks 加 ai_message_id 列(与 chat_task_steps 同名贯通) — 小欧 2026-08-19
        if _table_exists(conn, "chat_tasks") and not _col_exists(conn, "chat_tasks", "ai_message_id"):
            conn.execute("ALTER TABLE chat_tasks ADD COLUMN ai_message_id INTEGER")







        # 8. 清死字段与冗余索引(对齐 v2_chat_restructure.sql 第7步, 首版漏实现, 本版补全) — 小欧 2026-08-19
        #    仅删 sessions_/tasks 死字段
        if _table_exists(conn, "chat_sessions") and _col_exists(conn, "chat_sessions", "metadata"):
            conn.execute("ALTER TABLE chat_sessions DROP COLUMN metadata")
        if _table_exists(conn, "chat_tasks") and _col_exists(conn, "chat_tasks", "metadata"):
            conn.execute("ALTER TABLE chat_tasks DROP COLUMN metadata")
        # 删除冗余 timestamp 双索引(保留 idx_msg_timestamp)
        conn.execute("DROP INDEX IF EXISTS idx_messages_timestamp")

        # 9. 清 chat_session_title_history 死表 — 小欧 2026-08-19
        if _table_exists(conn, "chat_session_title_history"):
            conn.execute("DROP TABLE chat_session_title_history")

        _mark_migration_applied(conn, V2_MIGRATION_NAME)
    logger.info(f"[migrate] {V2_MIGRATION_NAME} 结构迁移完成")
    logger.info(f"[启动耗时] migrate_v2_chat_restructure: {_time.time()-_t0:.3f}s")
    return True


CANCELLED_ROWS_MIGRATION_NAME = "migrate_cancelled_rows_to_final"


def migrate_cancelled_rows_to_final(get_conn) -> bool:
    """现存 type=cancelled 旧行一次性改写(4.4.1 旧case清零) — 小欧 2026-09-07

    背景: 4.4.1 前取消终态曾用 type='cancelled' 事件步, 前端删 case 后该类行:
      徽章推导走 default 不变(应为已取消)、终态推导 derive_status_from_steps 读最后
      final、无则判 failed(应为 cancelled)。本迁移将 chat_task_steps.step_json 中
      type='cancelled' 的历史行原地改写为 type=final+outcome=cancelled,
      content/timestamp/step 等其余字段原样保留(content 缺失才补"任务已被取消")。

    幂等: 改写后行 type 已是 final, 重跑不再匹配; schema_migrations 登记后跳过。
    安全: 表/列缺失(新库无旧行)直接登记跳过; 坏 JSON 行跳过不中断。
    返值: 本次实际执行迁移 True; 已登记/无表列跳过 False。
    """
    import json as _json
    import time as _time
    _t0 = _time.time()
    with get_conn("chat") as conn:
        if _is_migration_applied(conn, CANCELLED_ROWS_MIGRATION_NAME):
            logger.info(f"[migrate] {CANCELLED_ROWS_MIGRATION_NAME} 已执行过, 跳过")
            return False
        if not _table_exists(conn, "chat_task_steps") or not _col_exists(conn, "chat_task_steps", "step_json"):
            logger.info(f"[migrate] {CANCELLED_ROWS_MIGRATION_NAME} 无 chat_task_steps.step_json, 登记跳过")
            _mark_migration_applied(conn, CANCELLED_ROWS_MIGRATION_NAME)
            return False
        _rows = conn.execute("SELECT rowid, step_json FROM chat_task_steps").fetchall()
        _n = 0
        for _rid, _raw in _rows:
            try:
                _step = _json.loads(_raw) if isinstance(_raw, str) else None
            except Exception:
                continue
            if not isinstance(_step, dict) or _step.get("type") != "cancelled":
                continue
            _step["type"] = "final"
            _step["outcome"] = "cancelled"
            if not _step.get("content"):
                _step["content"] = "任务已被取消"
            conn.execute("UPDATE chat_task_steps SET step_json=? WHERE rowid=?",
                         (_json.dumps(_step, ensure_ascii=False), _rid))
            _n += 1
        _mark_migration_applied(conn, CANCELLED_ROWS_MIGRATION_NAME)
    logger.info(f"[migrate] {CANCELLED_ROWS_MIGRATION_NAME} 完成, 改写 {_n} 行")
    logger.info(f"[启动耗时] migrate_cancelled_rows_to_final: {_time.time()-_t0:.3f}s")
    return True
