# -*- coding: utf-8 -*-
"""
ETL migration -- unify legacy time formats to UTC ISO 8601 Z strings.

Legacy formats detected:
  - "2026-07-18 04:45:39"       (CURRENT_TIMESTAMP, space-separated)
  - "2026-07-18T04:45:38.822063Z" (already correct, skipped)
  - 1721284496000               (millisecond int, create_timestamp)
  - "2026-07-18T12:34:56.000000+08:00" (local offset)

Usage:
    python scripts/migrate_time_format.py              # execute write
    python scripts/migrate_time_format.py --dry-run    # scan only

Safe:
  - Idempotent: correct Z values are not re-written
  - Unparseable values are skipped with a warning
  - --dry-run for preview

Author: xiaoou - 2026-07-18
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional


# -- normalizer ------------------------------------------------

def _normalize(val: Any) -> Optional[str]:
    """Normalize any legacy time value to UTC ISO 8601 Z string.

    Returns None if value is already correct (no update needed).
    """
    if val is None:
        return None
    # millisecond int (create_timestamp)
    if isinstance(val, (int, float)):
        dt = datetime.fromtimestamp(val / 1000, timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    s = str(val).strip()
    if not s:
        return None
    # already correct UTC Z format
    if s.endswith('Z') and 'T' in s:
        return None
    # numeric string (SQLite TEXT column storing millisecond epoch)
    if s.lstrip('-').isdigit():
        dt = datetime.fromtimestamp(int(s) / 1000, timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    try:
        dt = datetime.fromisoformat(s.replace(' ', 'T'))
        if dt.tzinfo is None:
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt.astimezone(timezone.utc)
        return dt_utc.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        print(f"  [WARN] unparseable: {repr(val)}")
        return None


# -- migration table defs --------------------------------------

# (db_file, table, pk_col, time_columns)
MIGRATIONS = [
    ("chat_history.db",      "chat_sessions",            "id",       ["created_at", "updated_at", "title_updated_at"]),
    ("chat_history.db",      "chat_messages",            "id",       ["timestamp", "created_at"]),
    ("chat_history.db",      "chat_session_title_history","id",      ["created_at"]),
    ("chat_history.db",      "chat_message_steps",       "id",       ["created_at"]),
    ("operations.db",        "file_operations",          "id",       ["created_at", "executed_at", "rolled_back_at", "backup_expires_at"]),
    # timers skipped -- tool layer, not unified
    ("task_tracker.db",      "tasks",                    "task_id",  ["created_at", "completed_at"]),
    ("task_tracker.db",      "task_operations",          "operation_id", ["created_at"]),
]


# -- main ------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv

    db_dir = Path.home() / ".omniagent"
    if not db_dir.exists():
        print(f"DB dir not found: {db_dir}")
        sys.exit(1)

    summary = []

    for db_file, table, pk_col, time_cols in MIGRATIONS:
        db_path = db_dir / db_file
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
                normalized = _normalize(raw)
                if normalized is not None:
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
