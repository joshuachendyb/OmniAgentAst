# 事件 Journal：SSE 事件的持久流水（落库/回放/判活/读终态/清理），供内存缓冲回收或后端重启后回放
# SQLite，与 LLM 的 httpx 池正交。表由 db_initializer 建，本模块只读写、零 DDL — 小欧 2026-09-29
import json
from datetime import datetime, timedelta
from typing import Optional
from app.db import db
from app.services.chat.storage import get_task_detail
from app.utils.json_utils import safe_json_dumps   # 复用 SafeJSONEncoder: 裸 json.dumps 遇不可序列化值会整帧丢失
from app.utils.time_utils import get_local_iso_timestamp

TERMINAL = ("completed", "failed", "cancelled")
PAGE_SIZE = 500
_CLOCK_SKEW_TOLERANCE_SECONDS = 5   # 未来时间戳容差：机器时钟微跳不算脏数据（2026-09-29 小欧）


async def append(task_id: str, session_id: str, seq: int, event_type: str, payload: dict) -> None:
    """单事件落库（基线形态）；合批挂载点见 3.5.2 落地注记——届时本函数扩展为可接收事件列表
    （同名接口向内兼容，单事件路径不变），一次事务提交多行，帧 1:1、seq 逐帧"""
    payload_json = safe_json_dumps(payload, ensure_ascii=False)
    created_at = get_local_iso_timestamp()
    await db.atxn("chat", lambda conn: conn.execute(
        "INSERT OR IGNORE INTO chat_stream_events"
        "(task_id, session_id, seq, event_type, payload_json, created_at) VALUES (?,?,?,?,?,?)",
        (task_id, session_id, seq, event_type, payload_json, created_at)))


async def read_after(task_id: str, after_seq: int, limit: int = PAGE_SIZE):
    """回放读取：seq >= after_seq；分页 limit；同事务附终态存在性与归属 session_id
    返回 (events, has_terminal, owner_session_id)：
      events = [(列 seq, 解析后 payload), ...]。**列 seq 是 DB 权威序号**（INTEGER、单调、必存在），
      回放的游标推进与缺口检测一律只用它；payload 是外部 JSON，形状不可信（可能非 dict、可能缺 seq），
      是否转发交调用方做类型闸门决定。
    owner 供 journal_reader 做归属校验，防知道 task_id 就能读他人流（3.7 一致性要求）"""
    def _q(conn):
        rows = conn.execute(
            "SELECT seq, event_type, payload_json FROM chat_stream_events "
            "WHERE task_id=? AND seq>=? ORDER BY seq LIMIT ?", (task_id, after_seq, limit)).fetchall()
        term = conn.execute(
            "SELECT 1 FROM chat_stream_events WHERE task_id=? AND event_type IN ('final','final_stats') LIMIT 1",
            (task_id,)).fetchone()
        owner = conn.execute(
            "SELECT session_id FROM chat_stream_events WHERE task_id=? LIMIT 1", (task_id,)).fetchone()
        return rows, term is not None, (owner["session_id"] if owner else None)
    rows, has_terminal, owner = await db.atxn("chat", _q)
    return [(r["seq"], json.loads(r["payload_json"])) for r in rows], has_terminal, owner


async def get_persisted_task_status(task_id: str):
    """终态权威 chat_tasks.status 的唯一读取口（3.10.1）；复用既有 get_task_detail。
    命名对立（[63] v1.33 北京老陈裁定"绝不允许同名"）：本函数读 **DB chat_tasks 持久行**，
    故名 get_persisted_task_status；task_state 侧读**内存 running_tasks 活跃表**的那一只
    （原名 get_task_status）同步改名为 get_running_task_status（见 3.6.2 末 hunk）。
    两者语义域正交（进程内活跃态 vs 跨重启终态权威），严禁同名、严禁互相替代。"""
    def _q(conn):
        row = get_task_detail(conn, task_id)
        return row.get("status") if row else None
    return await db.atxn("chat", _q)


async def is_producer_alive(task_id: str, window_seconds: int = 60) -> bool:
    """产出方存活判定：最近一条事件的写入时间在 window 内即视为活着。
    非终态不等于已停摆——任务仍在跑、只是长时间无新事件（慢思考/HITL 静默/工具长耗时）
    时也会这样，误判会中断回放 — 小欧 2026-09-29
    """
    def _q(conn):
        row = conn.execute(
            "SELECT created_at FROM chat_stream_events WHERE task_id=? "
            "ORDER BY seq DESC LIMIT 1", (task_id,)).fetchone()
        return row["created_at"] if row else None
    last = await db.atxn("chat", _q)
    if not last:
        return False
    try:
        age = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
    except ValueError:          # 历史脏数据格式异常：按不存活处理，不让回放链路因解析失败崩
        return False
    # 未来时间戳（时钟回拨/脏数据）不得判活：否则死任务永不收敛，reader 无限等
    return -_CLOCK_SKEW_TOLERANCE_SECONDS <= age < window_seconds


async def checkpoint_wal() -> Optional[dict]:
    """WAL checkpoint（PASSIVE）：把 WAL 里的页回写主库并截断

    自动 checkpoint 阈值约 1000 页，写够就同步做一次，实测会把单帧落库卡到 0.6~1.1s。
    挪到保留期任务（每小时）里做，尖峰只落在清理那一刻。
    PASSIVE 不阻塞其他连接：忙时返回 busy=1 并跳过，不与写入抢锁。
    """
    def _q(conn):
        return conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
    row = await db.atxn("chat", _q)
    return dict(row) if row else None


async def retention_cleanup(retention_days: int) -> int:
    """清理已终态且超保留期的事件。活跃/非终态永不删；end_time 缺失的终态任务按 created_at 双倍保留期兜底清理"""
    days = int(retention_days)   # 容忍 yaml 写成 "7"；非数值由 settings range 闸门在配置加载期拦
    def _q(conn):
    # 全精度 isoformat()：与 get_local_iso_timestamp() 存储格式一致；timespec="seconds"
    # 截微秒会让同秒边界的字符串比较误判 — 小欧 2026-09-29
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        fallback = (datetime.now() - timedelta(days=days * 2)).isoformat()
        rows = conn.execute(
            "SELECT DISTINCT e.task_id FROM chat_stream_events e "
            "LEFT JOIN chat_tasks t ON t.task_id = e.task_id "
            # 孤儿行（无 chat_tasks 行：建 buffer 早于 insert_task，写库失败即产生）按事件自身 created_at 兜底清理，
            # 否则 INNER JOIN 会把它整个丢弃、永不清理导致 Journal 无限增长
            "WHERE (t.status IN ('completed','failed','cancelled') "
            "       AND ((t.end_time IS NOT NULL AND t.end_time < ?) "
            "         OR (t.end_time IS NULL AND t.created_at < ?))) "
            "   OR (t.task_id IS NULL AND e.created_at < ?)",
            (cutoff, fallback, fallback)).fetchall()
        ids = [r["task_id"] for r in rows]
        for tid in ids:
            conn.execute("DELETE FROM chat_stream_events WHERE task_id=?", (tid,))
        return len(ids)
    return await db.atxn("chat", _q)
