# -*- coding: utf-8 -*-
# 2026-11-17 - 小欧 - [46b] P2b 存量回填: 从 chat_task_steps 离线派生 tool_paths_json。
#   用法: python -m app.services.chat.backfill_tool_paths [--db PATH] [--apply]
#     默认 dry-run(只统计不写); --apply 实际写入。
#   数据源: chat_task_steps.step_json 的 action.tools[].params.path(后端持久化, 可靠);
#   数据目录默认经 resolve_db_dir() 解析(唯一解析点, 不硬编码), --db 可显式指向任意库。
#   只写 chat_tasks.tool_paths_json; 幂等(重跑一致), 不触碰其他列(尤其不碰 ref_ledger_json)。
"""[46b] P2b 存量回填脚本 — 小欧 2026-11-17

回填边界(已核实的客观数据边界):
  - tool_paths 可离线回填: chat_task_steps.step_json 是后端持久化字段, 可靠。
  - ref_ledger 不可从 DB 回填: 历史台账数据从未持久化(引用块仅入 LLM prompt 不落表,
    refs_notice 首发纯 yield 不落库), 存量台账自上线起由前端上交累积, 本脚本不触碰。
"""
import json
import sqlite3
import sys
from typing import Dict, Optional

from app.db.database import resolve_db_dir
from app.services.chat.storage import derive_tool_paths_from_steps  # 复用派生函数(DRY)

_CHAT_DB_FILE = "chat_history.db"


def _default_db_path() -> str:
    return str(resolve_db_dir() / _CHAT_DB_FILE)


def backfill(db_path: str, apply: bool = False) -> dict:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    stats = {"tasks_scanned": 0, "tool_paths_updated": 0, "paths_total": 0, "parse_errors": 0}
    # 按任务聚合 steps(同一任务多步, 逐步扫描 action.tools[].params.path)
    task_steps: Dict[str, list] = {}
    for r in conn.execute("SELECT task_id, step_json FROM chat_task_steps ORDER BY task_id, step_index"):
        try:
            task_steps.setdefault(r["task_id"], []).append(json.loads(r["step_json"]))
        except (json.JSONDecodeError, TypeError):
            stats["parse_errors"] += 1
    conn2: Optional[sqlite3.Connection] = sqlite3.connect(db_path) if apply else None
    for task_id, steps in task_steps.items():
        stats["tasks_scanned"] += 1
        # 归一与在线路径一致(项目根由 browse.root_relative 内部读 config)
        paths = derive_tool_paths_from_steps(steps)
        if not paths:
            continue
        stats["paths_total"] += len(paths)
        if apply and conn2 is not None:
            conn2.execute("UPDATE chat_tasks SET tool_paths_json=? WHERE task_id=?",
                          (json.dumps(paths, ensure_ascii=False), task_id))
            stats["tool_paths_updated"] += 1
    if apply and conn2 is not None:
        conn2.commit()
        conn2.close()
    conn.close()
    return stats


if __name__ == "__main__":
    _apply = "--apply" in sys.argv
    _db = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else _default_db_path()
    print(backfill(_db, _apply))
