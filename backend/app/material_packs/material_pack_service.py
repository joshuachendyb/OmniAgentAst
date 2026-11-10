# 编辑历史:
# 2026-11-04 小欧 新建: 素材包 CRUD(名称唯一/条目同事务覆盖/只删记录不动磁盘) — 小欧-2026-11-04
# 2026-11-06 小欧 改名 service.py→material_pack_service.py: 与系统 *_service.py 命名惯例对齐(名实相符),
#   消费方 import 路径同步(`from app.material_packs import material_pack_service`) — 小欧-2026-11-06
# 2026-11-07 小欧 - 条目保留引用身份(kind/attachment_id), 附件条目投喂时
#   按 id 恢复附件语义(原只存 path/label, 附件降格为普通文件引用, resolver 走文件读分支);
#   create_pack 名称唯一检查提到总数上限之前(重名+满额时先报"重名", 提示才可行动)
# 2026-11-10 小欧 限额重设: 包总数 200→10、单包条目 10→5(合集=场景组合, 小而精);
#   新增 get_limits() 单一出口供前端预校验(消前端硬编码 MAX_ITEMS 双真源) — 小欧-2026-11-10
# 2026-11-10 小欧 注释清理: 去除修复序号等过期标识, 注释语义不变 — 小欧-2026-11-10

"""material_packs.material_pack_service — 素材包唯一读写实现。

约束:
  单包 ≤5 个文件(场景组合, 小而精); 包总数 ≤10; 名称唯一(COLLATE NOCASE);
  items 与包同事务覆盖写(先删后插), 删除包只删记录, 不动磁盘文件。
  限额经 get_limits() 单一出口下发, 前端不重复硬编码。
"""
import uuid
from typing import Any

from app.db import db
from app.file_browse.errors import INVALID_PARAM, NOT_FOUND, PACK_NAME_CONFLICT, fail
from app.utils.time_utils import get_local_iso_timestamp

MAX_PACKS = 10
MAX_ITEMS = 5
MAX_NAME = 64
MAX_LABEL = 120


def get_limits() -> dict[str, int]:
    """限额单一真源: 供前端预校验与文案, 与上方常量同源。"""
    return {"max_packs": MAX_PACKS, "max_items": MAX_ITEMS,
            "max_name": MAX_NAME, "max_label": MAX_LABEL}


def _clean_name(name: str) -> str:
    n = (name or "").strip()
    if not n or len(n) > MAX_NAME:
        fail(INVALID_PARAM, f"素材包名称需为 1~{MAX_NAME} 个字符")
    return n


def _clean_items(items: list | None) -> list[tuple]:
    """条目清洗: 保留 kind/attachment_id 引用身份。

    kind=attachment 时 attachment_id 必填(投喂按 id 查表恢复附件语义, 缺 id 无法恢复);
    其余 kind 透传(与 REF_KINDS 同域), attachment_id 恒置 None。
    """
    rows = items or []
    if len(rows) > MAX_ITEMS:
        fail(INVALID_PARAM, f"单个素材包最多 {MAX_ITEMS} 个文件")
    out: list[tuple] = []
    for i, it in enumerate(rows):
        path = str((it or {}).get("path") or "").strip()
        if not path:
            fail(INVALID_PARAM, "素材包条目缺少路径")
        kind = ((it or {}).get("kind") or "").strip() or None
        attachment_id = ((it or {}).get("attachment_id") or "").strip() or None
        if kind == "attachment" and not attachment_id:
            fail(INVALID_PARAM, "附件条目缺少 attachment_id")
        out.append((i, path, str((it or {}).get("label") or "")[:MAX_LABEL],
                    kind, attachment_id if kind == "attachment" else None))
    return out


def _pack_dict(row: Any, items: list[tuple]) -> dict[str, Any]:
    return {
        "id": row["id"], "name": row["name"], "note": row["note"],
        "group_name": row["group_name"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "items": [{"seq": s, "path": p, "label": lbl, "kind": k, "attachment_id": aid}
                  for s, p, lbl, k, aid in items],
    }


def list_packs() -> list[dict[str, Any]]:
    with db.get_conn("chat") as conn:
        packs = conn.execute(
            "SELECT * FROM material_packs ORDER BY group_name, name"
        ).fetchall()
        items = conn.execute(
            "SELECT pack_id, seq, path, label, kind, attachment_id "
            "FROM material_pack_items ORDER BY pack_id, seq"
        ).fetchall()
    by_pack: dict[str, list[tuple]] = {}
    for it in items:
        by_pack.setdefault(it["pack_id"], []).append(
            (it["seq"], it["path"], it["label"], it["kind"], it["attachment_id"]))
    return [_pack_dict(p, by_pack.get(p["id"], [])) for p in packs]


def _get(conn: Any, pack_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM material_packs WHERE id = ?", (pack_id,)
    ).fetchone()
    if not row:
        fail(NOT_FOUND, "素材包不存在")
    items = conn.execute(
        "SELECT seq, path, label, kind, attachment_id FROM material_pack_items "
        "WHERE pack_id = ? ORDER BY seq", (pack_id,)
    ).fetchall()
    return _pack_dict(row, [(i["seq"], i["path"], i["label"],
                             i["kind"], i["attachment_id"]) for i in items])


def _insert_items(conn: Any, pack_id: str, rows: list[tuple]) -> None:
    conn.executemany(
        "INSERT INTO material_pack_items (pack_id, seq, path, label, kind, attachment_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(pack_id, s, p, lbl, k, aid) for s, p, lbl, k, aid in rows],
    )


def create_pack(name: str, note: str = "", group_name: str = "",
                items: list | None = None) -> dict[str, Any]:
    n = _clean_name(name)
    rows = _clean_items(items)
    with db.get_conn("chat") as conn:
        # 名称唯一先于总数上限 —— 重名+满额时先报"重名"(用户改个名即可),
        #   报"满额"会让用户误以为必须删包, 提示不可行动
        if conn.execute(
            "SELECT 1 FROM material_packs WHERE name = ? COLLATE NOCASE", (n,)
        ).fetchone():
            fail(PACK_NAME_CONFLICT)
        total = conn.execute("SELECT COUNT(*) FROM material_packs").fetchone()[0]
        if int(total) >= MAX_PACKS:
            fail(INVALID_PARAM, f"素材包最多 {MAX_PACKS} 个，请先清理旧包")
        pid = uuid.uuid4().hex
        now = get_local_iso_timestamp()
        conn.execute(
            "INSERT INTO material_packs (id, name, note, group_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pid, n, (note or "").strip(), (group_name or "").strip(), now, now),
        )
        _insert_items(conn, pid, rows)
        return _get(conn, pid)


def update_pack(pack_id: str, *, name: str | None = None,
                note: str | None = None, group_name: str | None = None,
                items: list | None = None) -> dict[str, Any]:
    """部分更新; items 给出时整包覆盖(先删后插, 同事务)。"""
    with db.get_conn("chat") as conn:
        cur = _get(conn, pack_id)
        new_name = _clean_name(name) if name is not None else cur["name"]
        if new_name.lower() != cur["name"].lower() and conn.execute(
            "SELECT 1 FROM material_packs WHERE name = ? COLLATE NOCASE AND id <> ?",
            (new_name, pack_id),
        ).fetchone():
            fail(PACK_NAME_CONFLICT)
        conn.execute(
            "UPDATE material_packs SET name = ?, note = ?, group_name = ?, updated_at = ? "
            "WHERE id = ?",
            (new_name,
             cur["note"] if note is None else (note or "").strip(),
             cur["group_name"] if group_name is None else (group_name or "").strip(),
             get_local_iso_timestamp(), pack_id),
        )
        if items is not None:
            conn.execute("DELETE FROM material_pack_items WHERE pack_id = ?", (pack_id,))
            _insert_items(conn, pack_id, _clean_items(items))
        return _get(conn, pack_id)


def delete_pack(pack_id: str) -> None:
    """删包 + 条目; 不动磁盘文件(与附件删除同口径)。"""
    with db.get_conn("chat") as conn:
        if not conn.execute(
            "SELECT 1 FROM material_packs WHERE id = ?", (pack_id,)
        ).fetchone():
            fail(NOT_FOUND, "素材包不存在")
        conn.execute("DELETE FROM material_pack_items WHERE pack_id = ?", (pack_id,))
        conn.execute("DELETE FROM material_packs WHERE id = ?", (pack_id,))
