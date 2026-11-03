# -*- coding: utf-8 -*-
# 2026-11-03 - XiaoOu - new chat retention cleanup function - XiaoOu-2026-11-03
"""chat_history.db 保留期清理（数据治理）— 小欧 2026-11-03

设计（KISS-DIRECT）：
- 默认关闭（OMNIAGENT_CHAT_RETENTION_DAYS=0），避免误删用户对话历史。
- 开启时：删除 updated_at 早于保留期的会话，chat_tasks/chat_task_steps/chat_stream_events
  通过 ON DELETE CASCADE / 显式清理一并移除。
- 仅在启动期后台任务中运行，绝不进请求链路；失败只 warning，降级不阻断。
"""
from datetime import datetime, timedelta


async def retention_cleanup_chat(retention_days: int) -> int:
    if not retention_days or int(retention_days) <= 0:
        return 0
    days = int(retention_days)
    from app.db import db as _db
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(sep=" ")
    def _q(conn):
        # 先删流事件（无 FK 约束，显式清理防孤儿）
        conn.execute(
            "DELETE FROM chat_stream_events WHERE task_id IN "
            "(SELECT task_id FROM chat_tasks WHERE session_id IN "
            "(SELECT id FROM chat_sessions WHERE COALESCE(updated_at, created_at) < ?))",
            (cutoff,))
        # 再删会话（chat_tasks/chat_task_steps 通过 FK CASCADE 跟随；老库无 FK 时显式补删）
        conn.execute(
            "DELETE FROM chat_task_steps WHERE session_id IN "
            "(SELECT id FROM chat_sessions WHERE COALESCE(updated_at, created_at) < ?)",
            (cutoff,))
        conn.execute(
            "DELETE FROM chat_tasks WHERE session_id IN "
            "(SELECT id FROM chat_sessions WHERE COALESCE(updated_at, created_at) < ?)",
            (cutoff,))
        cur = conn.execute(
            "DELETE FROM chat_sessions WHERE COALESCE(updated_at, created_at) < ?", (cutoff,))
        return cur.rowcount
    try:
        return await _db.atxn("chat", _q)
    except Exception as _e:
        from app.logger import logger
        logger.warning("[chat_retention] cleanup failed (degrade): %r" % _e)
        return 0
