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
"""
migrate_steps — execution_steps 一次性数据迁移

背景: v3.2 终态 Step 统一约定上线前, 历史 chat_messages.execution_steps 存在旧表示:
  - error 末步带 recoverable 布尔(已废弃)
  - 生命周期信号用 step.type='incident' + incident_value('cancelled'/'retrying'/'paused')
  - HITL 用 authorization_required=True
  - 取消终态曾用 FinalStep(type='final', content 含'已取消')

本模块在 init_chat_db 末尾幂等执行一次, 将上述旧表示改写为新统一表示:
  - 删 recoverable
  - incident → type=incident_value(value 注入 step)
  - authorization_required → MetaStep(type='paused', confirm_id=...)
  - 旧取消 FinalStep → MetaStep(type='cancelled')

一次性守卫(小欧 2026-07-13): 用 chat 库 schema_migrations 表登记"已执行",
跑过一次后续启动直接跳过全表扫描。修复前该迁移每次启动无条件全表扫描
2.5GB 聊天库(3107 行), 单次耗时 ~25s, 是启动变慢根因; 加守卫后启动回到 <1s。

10规范(DRY): 复用 json_utils.parse_json / safe_json_dumps
小欧 2026-07-13
# 编辑历史:
# 2026-07-18 小欧 #5 fix: _needs_migration final分支补齐response字段(与_migrate_one_step一致); 取消文本仅存response的历史消息不再漏迁移误判完成
"""

from typing import Any, Dict, List, Optional

from app.logger import logger
from app.utils.json_utils import parse_json, safe_json_dumps
from app.services.chat.storage import derive_status_from_steps


def _needs_migration(steps: List[dict]) -> bool:
    """判断是否含旧标记, 决定是否需要改写(幂等)"""
    for s in steps:
        if not isinstance(s, dict):
            continue
        if "recoverable" in s:
            return True
        if "authorization_required" in s:
            return True
        if s.get("type") == "incident":
            return True
        if s.get("type") == "final":
            text = (s.get("content") or "") + (s.get("response") or "") + (s.get("reason") or "")
            if "已取消" in text or "取消" in text:
                return True
    return False


def _confirm_id_of(step: dict) -> str:
    """从 HITL step 提取 confirm_id(兼容 confirm_data / data 两种包裹) — 小欧 2026-07-13"""
    cid = step.get("confirm_id")
    if cid:
        return str(cid)
    for bucket in ("confirm_data", "data"):
        wrapper = step.get(bucket)
        if isinstance(wrapper, dict) and wrapper.get("confirm_id"):
            return str(wrapper.get("confirm_id"))
    return ""


def _migrate_one_step(step: dict) -> dict:
    """改写单条 step; 无旧标记则原样返回"""
    if not isinstance(step, dict):
        return step

    # 1) error 末步 recoverable 删除
    if "recoverable" in step:
        step.pop("recoverable", None)

    # 2) HITL authorization_required → MetaStep(paused)
    if step.get("authorization_required"):
        step.pop("authorization_required", None)
        # 兼容旧 step 把工具信息放在顶层或 data 包裹两种表示 — 小欧 2026-07-13
        _data = step.get("data") if isinstance(step.get("data"), dict) else {}
        return {
            "type": "paused",
            "step": step.get("step"),
            "timestamp": step.get("timestamp"),
            "content": step.get("content") or "等待用户确认授权",
            "confirm_id": _confirm_id_of(step),
            "tool_name": step.get("tool_name") or _data.get("tool_name"),
            "params": step.get("params") or _data.get("params"),
            "safety_level": step.get("safety_level") or _data.get("safety_level"),
        }

    # 3) incident → type=incident_value
    if step.get("type") == "incident":
        incident_value = step.get("incident_value")
        step.pop("incident_value", None)
        new_type = incident_value if incident_value in ("cancelled", "retrying", "paused") else "incident"
        step["type"] = new_type
        if "value" in step:
            step.setdefault("content", step.pop("value"))
        return step

    # 4) 旧取消 FinalStep → MetaStep(cancelled)
    # 小沈 2026-07-13: 旧 FinalStep 取消文本可能在 content 或 response 字段(取决于历史时期),
    # 必须两者都查, 否则用 response 存储的取消 FinalStep 不会被识别, 迁移后仍为 final(误判完成)
    if step.get("type") == "final":
        text = (step.get("content") or "") + (step.get("response") or "") + (step.get("reason") or "")
        if "已取消" in text or "取消" in text:
            return {
                "type": "cancelled",
                "step": step.get("step"),
                "timestamp": step.get("timestamp"),
                "content": step.get("content") or step.get("response") or "任务已被取消",
            }

    return step


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
