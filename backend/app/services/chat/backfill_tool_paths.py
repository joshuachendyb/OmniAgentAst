# -*- coding: utf-8 -*-
# 2026-11-17 - 小欧 - [46b] P2b 存量回填: 从 chat_task_steps 离线派生 tool_paths_json。
#   用法: python -m app.services.chat.backfill_tool_paths [--db PATH] [--apply]
#     默认 dry-run(只统计不写); --apply 实际写入。
#   数据源: chat_task_steps.step_json 的 action.tools[].params.path(后端持久化, 可靠);
#   数据目录默认经 resolve_db_dir() 解析(唯一解析点, 不硬编码), --db 可显式指向任意库。
#   只写 chat_tasks.tool_paths_json; 幂等(重跑一致), 不触碰其他列(尤其不碰 ref_ledger_json)。
# 2026-11-18 - 小欧 - [46b] 会审整改: ①读写共用单连接(原两个连接同开一库, 读连接持共享锁与
#   写连接抢锁); ②改游标流式遍历, 每次只驻留一个任务的 steps(原全表收进 dict, 大库内存爆);
#   ③序列化改 safe_json_dumps(与在线落库同一出口); ④库文件缺失显式报错(原 sqlite3.connect
#   会静默建空库, 回填"成功"而实际零数据); ⑤tool_paths_updated 按 UPDATE rowcount 计
#   (原按扫描到的任务数计, 库中已无该任务也算一条) — 小欧-2026-11-18
# 2026-11-18 - 小欧 - 回填写入加"值未变不写"条件: rowcount 只在值真变时命中, 重跑才如实为 0
#   (原无条件 UPDATE, 同值重跑也算改写, 与"幂等"表述打架) — 小欧-2026-11-18
"""[46b] P2b 存量回填脚本 — 小欧 2026-11-17

回填边界(已核实的客观数据边界):
  - tool_paths 可离线回填: chat_task_steps.step_json 是后端持久化字段, 可靠。
  - ref_ledger 不可从 DB 回填: 历史台账数据从未持久化(引用块仅入 LLM prompt 不落表,
    refs_notice 首发纯 yield 不落库), 存量台账自上线起由前端上交累积, 本脚本不触碰。
"""
import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from app.db.database import db_file_path
from app.services.chat.storage import derive_tool_paths_from_steps  # 复用派生函数(DRY)
from app.utils.json_utils import safe_json_dumps  # 与在线落库同一序列化出口(DRY)


def _default_db_path() -> str:
    # 2026-11-21 小欧 - 改走 db_file_path 单源: 库已归入 {数据根}/db/, 此处原直接拼根路径会指向不存在的库
    return str(db_file_path("chat"))


def _write_task(conn: sqlite3.Connection, task_id: str, steps: list,
                stats: dict, apply: bool) -> None:
    """单任务派生 + 落库(调用方按任务分组喂入, 保证内存只驻留一个任务的 steps)"""
    stats["tasks_scanned"] += 1
    paths = derive_tool_paths_from_steps(steps)
    if not paths:
        return
    stats["paths_total"] += len(paths)
    stats["tasks_with_paths"] += 1
    if not apply:
        return
    payload = safe_json_dumps(paths)
    # 值相同即不写: UPDATE 的 rowcount 只认"值真的变了"的行, 重跑才会是 0(否则每次重跑都算改写)
    cur = conn.execute(
        "UPDATE chat_tasks SET tool_paths_json=?"
        " WHERE task_id=? AND (tool_paths_json IS NULL OR tool_paths_json<>?)",
        (payload, task_id, payload),
    )
    stats["tool_paths_updated"] += cur.rowcount or 0


def backfill(db_path: str, apply: bool = False) -> dict:
    """[46b] P2b 存量回填 — 小欧 2026-11-17

    dry-run 只统计(tasks_with_paths = 会被写入的任务数, tool_paths_updated 恒 0);
    apply 时 tool_paths_updated 为实际命中行数。
    """
    if not Path(db_path).is_file():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    stats = {
        "tasks_scanned": 0,
        "tasks_with_paths": 0,
        "tool_paths_updated": 0,
        "paths_total": 0,
        "parse_errors": 0,
    }
    try:
        # 流式游标: 按 task_id 分组累积, 换组即落库并清空(不把全表 steps 收进内存)
        _task_id: Optional[str] = None
        _steps: list = []
        for r in conn.execute(
            "SELECT task_id, step_json FROM chat_task_steps ORDER BY task_id, step_index"
        ):
            if r["task_id"] != _task_id:
                if _task_id is not None:
                    _write_task(conn, _task_id, _steps, stats, apply)
                _task_id, _steps = r["task_id"], []
            try:
                _steps.append(json.loads(r["step_json"]))
            except (json.JSONDecodeError, TypeError):
                stats["parse_errors"] += 1
        if _task_id is not None:
            _write_task(conn, _task_id, _steps, stats, apply)
        if apply:
            conn.commit()
    finally:
        conn.close()
    return stats


if __name__ == "__main__":
    _args = sys.argv[1:]
    _apply = "--apply" in _args
    if "--db" in _args:
        _i = _args.index("--db")
        if _i + 1 >= len(_args):
            sys.exit("--db 缺少数据库路径参数")
        _db = _args[_i + 1]
    else:
        _db = _default_db_path()
    try:
        print(backfill(_db, _apply))
    except FileNotFoundError as exc:
        sys.exit(str(exc))
