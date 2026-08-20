# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-20 - 小欧 - 新建: 监控独立库 monitoring.db 落库层(独立模块, 11.2-C)。库路径由
#   database.py._db_paths["monitoring"] 注册, 复用 get_conn("monitoring")/get_conn_with_retry(WAL+参数安全闸门+locked退避)。
#   本文件不依赖 agent, 纯 DB 操作; 表结构权威=11.2-C; 惰性导入 database 防环(database→db_initializer→storage→database)。
# 2026-08-20 - 小欧 - 真实缺陷复核三遍修复: ①C1: task_metrics 增 trim_count/trim_tokens 列(DDL + persist _cols + PRAGMA 幂等补列迁移, 兼容老库);
#   ②F: persist_tool_metrics 的 ON CONFLICT 由累积(`+=excluded`)改 latest-wins(`=excluded`), 与 persist_task_metrics 的 REPLACE 语义一致,
#   消除冗余持久化(同一 task_id 落两次)时 tool 指标翻倍而汇总只留最新的不一致。
"""监控独立库 monitoring.db 落库层（独立模块）—— 小欧 2026-08-20

- 库路径由 database.py._db_paths["monitoring"] 注册，复用 get_conn("monitoring")（WAL+闸门+退避全复用）。
- 本文件不依赖 agent，纯 DB 操作；表结构权威=11.2-C。
- 惰性导入 database 防环（database→db_initializer→storage→database）。
"""
from typing import Dict, Any, List


def init_monitoring_db(get_conn) -> None:
    """建 monitoring.db 五表 + monitoring_meta（幂等 DDL，模式同 init_chat_db）"""
    with get_conn("monitoring") as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS task_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT, task_id TEXT UNIQUE,
                context_root_task_id TEXT, context_link_mode TEXT,
                outcome TEXT, error_type TEXT,
                model TEXT, provider TEXT,
                total_steps INTEGER, llm_call_count INTEGER, retry_count INTEGER,
                trim_count INTEGER, trim_tokens INTEGER,
                tool_call_count INTEGER, tool_error_count INTEGER,
                duration_seconds REAL, llm_latency_seconds REAL, tool_execution_seconds REAL,
                first_token_latency_seconds REAL,
                estimated_cost REAL,
                prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
                context_message_count INTEGER, context_estimated_tokens INTEGER,
                context_truncated INTEGER, context_injected_message_count INTEGER,
                context_injected_estimated_tokens INTEGER, context_injected_ratio REAL,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS task_tool_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT, tool_name TEXT,
                call_count INTEGER, error_count INTEGER, total_latency_seconds REAL,
                UNIQUE(task_id, tool_name)
            );
            CREATE TABLE IF NOT EXISTS http_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT, path TEXT, status_code INTEGER, kind TEXT,
                duration_seconds REAL, request_size_bytes INTEGER, response_size_bytes INTEGER,
                timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT, session_id TEXT, model TEXT, provider TEXT,
                call_index INTEGER, duration_seconds REAL,
                prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
                error_type TEXT, finish_reason TEXT, timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, type TEXT, value REAL, labels TEXT, timestamp TEXT
            );
            CREATE TABLE IF NOT EXISTS monitoring_meta (
                version INTEGER PRIMARY KEY
            );
            CREATE INDEX IF NOT EXISTS idx_http_path_ts ON http_requests(path, timestamp);
            CREATE INDEX IF NOT EXISTS idx_llm_task_ts ON llm_calls(task_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, timestamp);
        ''')
        conn.execute("INSERT OR IGNORE INTO monitoring_meta(version) VALUES (1)")
        # C1修复(小欧 2026-08-20 复核确认): task_metrics 增 trim_count/trim_tokens 列 —— 老库幂等补列迁移
        #   (CREATE TABLE IF NOT EXISTS 不会改既有表; SQLite 无 ADD COLUMN IF NOT EXISTS, 故查 PRAGMA 再 ALTER)
        _need_cols = ("trim_count", "trim_tokens")
        _has_cols = {r[1] for r in conn.execute("PRAGMA table_info(task_metrics)").fetchall()}
        for _c in _need_cols:
            if _c not in _has_cols:
                conn.execute(f"ALTER TABLE task_metrics ADD COLUMN {_c} INTEGER")


def persist_task_metrics(row: Dict[str, Any]) -> None:
    from app.db import db as _db   # DatabaseManager 单例（get_conn_with_retry 是实例方法）— 小欧 2026-08-20 修正
    _cols = ["session_id", "task_id", "context_root_task_id", "context_link_mode", "outcome", "error_type",
             "model", "provider", "total_steps", "llm_call_count", "retry_count", "trim_count", "trim_tokens",
             "tool_call_count", "tool_error_count",
             "duration_seconds", "llm_latency_seconds", "tool_execution_seconds", "first_token_latency_seconds",
             "estimated_cost",
             "prompt_tokens", "completion_tokens", "total_tokens", "context_message_count", "context_estimated_tokens",
             "context_truncated", "context_injected_message_count", "context_injected_estimated_tokens",
             "context_injected_ratio", "created_at"]
    _vals = [row.get(c) for c in _cols]
    _ph = ",".join(["?"] * len(_cols))
    _sql = f"INSERT OR REPLACE INTO task_metrics({','.join(_cols)}) VALUES ({_ph})"
    with _db.get_conn_with_retry("monitoring") as conn:
        conn.execute(_sql, _vals)


def persist_tool_metrics(task_id: str, rows: List[Dict[str, Any]]) -> None:
    from app.db import db as _db   # DatabaseManager 单例 — 小欧 2026-08-20 修正
    with _db.get_conn_with_retry("monitoring") as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO task_tool_metrics(task_id, tool_name, call_count, error_count, total_latency_seconds) "
                "VALUES (?,?,?,?,?) ON CONFLICT(task_id, tool_name) DO UPDATE SET "
                "call_count=excluded.call_count, error_count=excluded.error_count, "
                "total_latency_seconds=excluded.total_latency_seconds",   # F修复(复核确认): 改 latest-wins 与 task_metrics REPLACE 一致, 冗余持久化不再翻倍计数 — 小欧 2026-08-20
                (task_id, r["tool_name"], r["call_count"], r["error_count"], r["total_latency_seconds"]),
            )


def persist_llm_calls(rows: List[Dict[str, Any]]) -> None:
    from app.db import db as _db   # DatabaseManager 单例 — 小欧 2026-08-20 修正
    with _db.get_conn_with_retry("monitoring") as conn:
        for r in rows:
            conn.execute(
                "INSERT INTO llm_calls(task_id, session_id, model, provider, call_index, duration_seconds, "
                "prompt_tokens, completion_tokens, total_tokens, error_type, finish_reason, timestamp) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (r["task_id"], r["session_id"], r["model"], r["provider"], r["call_index"],
                 r["duration_seconds"], r["prompt_tokens"], r["completion_tokens"], r["total_tokens"],
                 r["error_type"], r["finish_reason"], r["timestamp"]),
            )


def persist_http_request(method: str, path: str, status_code: int, kind: str,
                         duration: float, request_size: int = 0, response_size: int = 0) -> None:
    """middleware 每请求后 flush 一行（原始 + 计数器入 metrics 表）；非阻塞降级"""
    from datetime import datetime
    from app.db import db as _db   # DatabaseManager 单例 — 小欧 2026-08-20 修正
    try:
        _ts = datetime.now().isoformat(sep=" ")
        with _db.get_conn_with_retry("monitoring") as conn:
            conn.execute(
                "INSERT INTO http_requests(method, path, status_code, kind, duration_seconds, "
                "request_size_bytes, response_size_bytes, timestamp) VALUES (?,?,?,?,?,?,?,?)",
                (method, path, status_code, kind, round(duration, 3), request_size, response_size, _ts),
            )
            conn.execute(
                "INSERT INTO metrics(name, type, value, labels, timestamp) VALUES (?,?,?,?,?)",
                ("http_requests_total", "counter", 1.0,
                 '{"method":"%s","path":"%s","status":"%s"}' % (method, path, status_code), _ts),
            )
    except Exception as _e:
        from app.logger import logger
        logger.warning(f"[monitoring.storage] http flush 失败(降级): {_e!r}")