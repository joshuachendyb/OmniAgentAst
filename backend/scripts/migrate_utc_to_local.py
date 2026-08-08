# -*- coding: utf-8 -*-
"""
ETL migration -- unify UTC ISO 8601 Z / 带偏移时间 to 本地ISO无Z.

设计依据: doc/时间戳全程统一本地时区方案-小欧-2026-08-08.md v1.6
背景: 全程统一本地时区(task004报告问题1), 旧数据为 UTC Z 或带 +08:00 偏移,
      新代码全部写入 本地ISO无Z(如 2026-08-08T16:52:34.123456)。
      本脚本把历史数据一次性转换为本地ISO无Z, 避免新旧混存乱序。

与 migrate_time_format.py 区别: 旧脚本是反向(统一为UTC Z, 历史遗留), 本脚本是正向(UTC→本地), 不执行不修改旧脚本。

Usage:
    python scripts/migrate_utc_to_local.py              # execute write
    python scripts/migrate_utc_to_local.py --dry-run    # scan only

Safe:
  - 自动备份三个DB文件(.bak) 到同目录
  - Idempotent: 已是本地naive无偏移的值跳过(不重写)
  - Unparseable values are skipped with a warning
  - --dry-run for preview

Author: 小欧 - 2026-08-08
"""

import sqlite3
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

DB_DIR = Path.home() / ".omniagent"

# (db_file, table, pk_col, time_columns)
MIGRATIONS = [
    ("chat_history.db",      "chat_sessions",             "id",        ["created_at", "updated_at", "title_updated_at"]),
    ("chat_history.db",      "chat_messages",             "id",        ["timestamp", "created_at"]),
    ("chat_history.db",      "chat_message_steps",        "id",        ["created_at"]),
    ("chat_history.db",      "chat_session_title_history","id",        ["created_at"]),
    ("operations.db",        "file_operations",           "id",        ["created_at", "executed_at", "rolled_back_at", "backup_expires_at"]),
    ("operations.db",        "timers",                    "timer_id",  ["created_at", "trigger_at", "triggered_at"]),
    ("task_tracker.db",      "tasks",                     "task_id",   ["created_at", "completed_at"]),
    ("task_tracker.db",      "task_operations",           "operation_id", ["created_at"]),
]


def utc_z_to_local(utc_str: str) -> Optional[str]:
    """UTC Z / 带偏移 字符串 → 本地ISO无Z — 小欧 2026-08-08
    会审修正: 用 astimezone() 自动转本地(Python 按当前系统时区/夏令时处理),
    替代 safe_utc_offset() 手动加偏移(后者对历史数据/夏令时切换不准确, 且是绕路)。
    判断逻辑扩展: 以 Z 结尾 或 含时区偏移(如+08:00) 均需转换; 本地naive无偏移原样跳过。"""
    if not utc_str or not isinstance(utc_str, str):
        return utc_str  # 空/非字符串，跳过
    s = utc_str.strip()
    # 判断是否含时区信息(Z 或 +08:00 偏移) — 会审修正: 兼容 timers 表的 +08:00 格式
    has_tz = s.endswith('Z') or ('+' in s[10:]) or ('-' in s[10:])
    if not has_tz:
        return utc_str  # 已是本地naive无偏移，跳过(幂等)
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))  # Z → +00:00
        local_dt = dt.astimezone()  # 任意时区 → 本地(自动处理偏移/夏令时)
        return local_dt.replace(tzinfo=None).strftime('%Y-%m-%dT%H:%M:%S.%f')
    except (ValueError, TypeError, OverflowError):
        return utc_str  # 解析失败原样返回(幂等)


def _backup_db(db_path: Path) -> None:
    """备份DB到同目录 .bak — 小欧 2026-08-08"""
    backup_path = db_path.with_suffix(db_path.suffix + '.bak')
    shutil.copy2(str(db_path), str(backup_path))


def _normalize_col(value: Any) -> Optional[str]:
    """单列值归一化 — 小欧 2026-08-08"""
    if value is None:
        return None
    return utc_z_to_local(str(value))


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if not DB_DIR.exists():
        print(f"DB dir not found: {DB_DIR}")
        sys.exit(1)

    summary = []

    for db_file, table, pk_col, time_cols in MIGRATIONS:
        db_path = DB_DIR / db_file
        if not db_path.exists():
            print(f"[SKIP] {db_file}/{table} -- DB not found")
            continue

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cur.fetchone():
            print(f"[SKIP] {db_file}/{table} -- table not found")
            conn.close()
            continue

        if not dry_run:
            _backup_db(db_path)

        cur.execute(f"SELECT * FROM [{table}]")
        rows = cur.fetchall()
        if not rows:
            summary.append((db_file, table, 0, 0))
            conn.close()
            continue

        changed = 0
        for row in rows:
            pk_val = row[pk_col]
            updates = {}
            for col in time_cols:
                try:
                    raw = row[col]
                except (IndexError, KeyError):
                    continue
                normalized = _normalize_col(raw)
                if normalized is not None and normalized != raw:
                    updates[col] = normalized
            if updates:
                changed += 1
                if not dry_run:
                    set_clause = ", ".join(f"[{c}] = ?" for c in updates)
                    params = list(updates.values()) + [pk_val]
                    cur.execute(f"UPDATE [{table}] SET {set_clause} WHERE [{pk_col}] = ?", params)

        if not dry_run:
            conn.commit()

        summary.append((db_file, table, changed, len(rows)))
        conn.close()

    # -- report --
    label = "[DRY-RUN]" if dry_run else "[EXEC]"
    print()
    print("=" * 60)
    print(f" {label} Migration Summary")
    print("=" * 60)
    total_rows = 0
    total_changed = 0
    for db_file, table, changed, total in summary:
        total_rows += total
        total_changed += changed
        pct = f"({changed}/{total})" if total else "(0)"
        print(f"  {db_file:20s} {table:30s} {pct:>12s}")
    print("=" * 60)
    print(f"  Total {total_rows} rows, {total_changed} changed")
    if dry_run:
        print()
        print("Remove --dry-run to execute")
    else:
        print("Done")


if __name__ == "__main__":
    main()
