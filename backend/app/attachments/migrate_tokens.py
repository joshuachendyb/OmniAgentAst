# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 旧占位 [[IMAGE_ATTACHMENT:<id>]] → [[ATTACHMENT:<id>]] 一次性迁移,
#   覆盖 DB(chat_user_message/chat_stream_events) + files/**/*.jsonl(conv_hist_/tool_data_),
#   幂等可重跑, 只做纯文本替换不动其他内容 — 小欧-2026-11-11

"""attachments.migrate_tokens — 图片附件旧占位 → 新占位的存储迁移。

运行: python -m app.attachments.migrate_tokens
范围:
  1. DB: chat_user_message(content/response/reasoning) + chat_stream_events(payload_json);
  2. files 根下所有 *.jsonl(conv_hist_ / tool_data_ 前缀)。
旧 [[IMAGE_ATTACHMENT:32hex]] 与新 [[ATTACHMENT:32hex]] 的 id 同源(attachments 表主键),
替换即语义等价, wire 正则按新形态识别。
"""
import json
from pathlib import Path
from typing import List, Tuple

_OLD = "[[IMAGE_ATTACHMENT:"
_NEW = "[[ATTACHMENT:"


def _migrate_text(text: str) -> Tuple[str, int]:
    if _OLD not in text:
        return text, 0
    return text.replace(_OLD, _NEW), text.count(_OLD)


def migrate_db() -> int:
    from app.db.database import db  # 延迟导入: 纯文本场景不拖 DB 依赖
    total = 0
    with db.get_conn("chat") as conn:
        for table, col in (("chat_user_message", "content"),
                           ("chat_user_message", "response"),
                           ("chat_user_message", "reasoning"),
                           ("chat_stream_events", "payload_json")):
            cur = conn.execute(
                f"UPDATE {table} SET {col} = replace({col}, ?, ?) "
                f"WHERE {col} LIKE ?", (_OLD, _NEW, f"%{_OLD}%"))
            total += cur.rowcount or 0
    return total


def migrate_jsonl(root: Path) -> Tuple[int, int]:
    files = hits = 0
    for path in root.rglob("*.jsonl"):
        if not (path.name.startswith("conv_hist_") or path.name.startswith("tool_data_")):
            continue
        try:
            lines: List[str] = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        except OSError:
            continue
        changed = 0
        out: List[str] = []
        for line in lines:
            new, n = _migrate_text(line)
            changed += n
            out.append(new)
        if changed:
            path.write_text("".join(out), encoding="utf-8")
            files += 1
            hits += changed
    return files, hits


def main() -> None:
    from app.file_persist import _files_root
    db_rows = migrate_db()
    files, hits = migrate_jsonl(_files_root())
    print(json.dumps({"db_rows_updated": db_rows,
                      "jsonl_files_updated": files,
                      "jsonl_tokens_replaced": hits}, ensure_ascii=False))


if __name__ == "__main__":
    main()
