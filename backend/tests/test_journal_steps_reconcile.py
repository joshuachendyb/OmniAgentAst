# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-03 - 小欧 - 新建: journal_steps_reconcile 守护(③ Journal vs ② chat_task_steps 启动期对账,
#   文档[5] 5.3 D2) — 只告警不自动补, 故守护重点是"判定口径正确 + 不误报 + 不漏报" — 小欧-2026-10-03
"""journal_steps_reconcile 守护 — 小欧 2026-10-03

被测: app/services/chat/stream_event_journal.py::journal_steps_reconcile

口径(该函数 docstring 已声明, 此处钉死):
  Journal(③) 不过滤, 业务步含 4 类(action/observation/thought/final)
  + 5 类"落库但不计业务步"的框架步(start/stats/context_overview/final_stats/authorization_required)
  故 **帧数 > 行数 属正常**(SSE 专属 9 类不入库); **行数 > 帧数 才是异常**(Journal 丢帧)。

守护两态:
  ① 帧数 > 行数 → 不得误报(过滤类不入库是设计, 不是异常)
  ② 行数 > 帧数 → 必须检出(Journal 丢帧, 该任务重连回放会缺内容)
"""
import asyncio
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def chat_db(tmp_path, monkeypatch):
    """独立 chat 库 + 建表, 与 conftest.isolated_config_dir 同款隔离(够不到真库)"""
    from app.db import db as db_manager
    from app.db.db_initializer import init_chat_db
    monkeypatch.setitem(db_manager._db_overrides, "chat", str(tmp_path / "chat.db"))
    init_chat_db(db_manager.get_conn)
    yield


def _seed(conn, task_id, journal_frames, step_rows):
    """造一个 task: Journal N 帧 + steps M 行(绕过外键, 直接插两张表)"""
    conn.execute("INSERT OR IGNORE INTO chat_sessions(id,title) VALUES('S1','t')")
    conn.execute(
        "INSERT OR IGNORE INTO chat_tasks(task_id,session_id,sessionModel) VALUES(?,'S1','m')",
        (task_id,))
    for i in range(journal_frames):
        conn.execute(
            "INSERT OR IGNORE INTO chat_stream_events"
            "(task_id,session_id,seq,event_type,payload_json,created_at) "
            "VALUES (?,'S1',?,'action','{}','2026-10-03T00:00:00')", (task_id, i))
    for i in range(step_rows):
        conn.execute(
            "INSERT OR IGNORE INTO chat_task_steps"
            "(ai_message_id,session_id,step_index,step_json,created_at,task_id) "
            "VALUES (1,'S1',?,'{}','2026-10-03T00:00:00',?)", (i, task_id))


def test_reconcile_flags_only_when_steps_exceed_journal(chat_db):
    """帧数>行数(正常)不报; 行数>帧数(Journal 丢帧)必报"""
    from app.db import db as db_manager
    from app.services.chat.stream_event_journal import journal_steps_reconcile

    with db_manager.get_conn("chat") as conn:
        _seed(conn, "T-normal", journal_frames=9, step_rows=2)   # 7 个 SSE 专属类不入库 → 正常
        _seed(conn, "T-lost",   journal_frames=1, step_rows=3)   # Journal 丢帧 → 异常

    bad = asyncio.run(journal_steps_reconcile())
    ids = {b["task_id"] for b in bad}

    assert "T-lost" in ids, "Journal 丢帧(task) 必须检出"
    assert "T-normal" not in ids, "帧数>行数属正常设计, 不得误报"
    lost = next(b for b in bad if b["task_id"] == "T-lost")
    assert lost["journal_frames"] == 1 and lost["step_rows"] == 3


def test_reconcile_empty_db_returns_empty(chat_db):
    """干净库不得报错, 返回空列表"""
    from app.services.chat.stream_event_journal import journal_steps_reconcile
    assert asyncio.run(journal_steps_reconcile()) == []


def test_reconcile_equal_counts_not_flagged(chat_db):
    """帧数 == 行数: Journal 无丢帧, 不算异常"""
    from app.db import db as db_manager
    from app.services.chat.stream_event_journal import journal_steps_reconcile

    with db_manager.get_conn("chat") as conn:
        _seed(conn, "T-eq", journal_frames=4, step_rows=4)

    assert asyncio.run(journal_steps_reconcile()) == []