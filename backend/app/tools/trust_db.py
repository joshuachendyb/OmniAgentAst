# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 - 小欧 - 架构边界修正(三堂会审): 会话信任读写三函数从 app/services/chat/storage.py
#   迁入本层 app/tools/trust_db.py —— 修复 app/tools 禁 app.services 依赖方向守护违规
#   (test_architecture_boundaries.py test_layer_boundaries 报 trust.py imports app.services.chat.storage)。
#   原逻辑逐字复制不改业务(能复制不重写): get_session_id_by_task/check_session_trust/insert_session_trust
#   + _norm_trust_path(储storage侧 delete/list 仍使用, 双侧各持一份保持落库/查询一致)。
#   迁移后 trust.py 由 import app.services.chat.storage 改为 import app.tools.trust_db(同层, 零越层)。
# 2026-09-16 小欧 - 问题B修复: _norm_trust_path 增加 tool_name 参数, 非文件信任域跳过 Path.resolve() — 小欧-2026-09-16
# 2026-09-16 小欧 - 函数化(DRY/KISS核查, 文档三堂会审): _norm_trust_path 公开化改名 norm_trust_path 单一来源,
#   storage.delete_session_trust 撤销侧改 import 消费本函数 —— 消除 split 双份 13 行逐字重复(5.4 曾因双份漏同步引入退化),
#   方向 services→tools 合法单向, 走既有模块内延迟导入同模式 — 小欧-2026-09-16
# 2026-10-05 小欧 - 设计决策B(北京老陈裁定): check_session_trust 从"按(session_id,tool_name,path)隔离"改为
#   "目录信任跨工具生效" —— 只改path非空查询的行集: WHERE session_id=? AND (tool_name=? OR path IS NOT NULL);
#   path=None(无路径工具: shell/execute_sql/registry_*)仍只命中本工具的通配行path IS NULL, 目录信任不会误放行shell。
#   本文件行 4-12 既往认"按tool_name隔离", 2026-10-05起此前记录为历史存档; 落库/查询/撤销路径分开:
#   save仍按(session_id,tool_name,path)写(UNIQUE保留), 只改豁免放行的判定。— 小欧-2026-10-05
# 2026-10-06 - 小欧 - 缺陷修复(北京老陈实测「连续信任4次仍反复弹窗」): 新增 trust_scope_path, 落库前把
#   文件类工具的 path 收敛到【所在目录】。根因: 读取端 check_session_trust 的 `trusted_p in target_p.parents`
#   早已支持目录前缀继承, 但写入端恒登记叶子文件, 生产者从不产出目录 —— 「信任此操作」退化为「只信任这一个
#   文件名」, 换个文件名即重新弹窗(DB 实测同 session 4 行全为 analysis\*.py 单文件, 无一行目录)。
#   读取端零改动(本就不需要改), 仅让生产者产出它能匹配的东西。 — 小欧-2026-10-06
"""tools 层会话信任读写(纯 SQL 查询, 不依赖 services 层) — 小欧 2026-09-05"""
from pathlib import Path
from typing import Optional
from sqlite3 import Connection

from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库
from app.tools.tool_constants import NON_FILE_TRUST_TOOLS  # 小欧 2026-09-16 非文件信任域(与 storage:561 撤销侧同位)


def norm_trust_path(path: Optional[str], tool_name: Optional[str] = None) -> Optional[str]:
    """信任路径规范化(resolve 绝对化, 供落库/查询/撤销双侧一致) — 小欧 2026-09-02
    2026-09-16 小欧 问题B修复: 非文件信任域(registry/sql)跳过 Path.resolve() 原样 strip 存储——
      注册表键(HKCU\\Software\\X)非文件系统路径, resolve 会臆造垃圾绝对路径(F:\\...\\HKCU\\...\\X);
      execute_sql 的 db path 保持相对原样(两侧一致即正确); 复用 insert/check/delete 已有 tool_name, 不新增参数 — 小欧-2026-09-16
    2026-09-16 函数化: 原名 _norm_trust_path, storage 撤销侧原双份副本删除, 统一消费本函数(DRY) — 小欧-2026-09-16"""
    if not path:
        return None
    try:
        if tool_name in NON_FILE_TRUST_TOOLS:
            return path.strip()
        return str(Path(path).resolve())
    except Exception:
        return None


def trust_scope_path(path: Optional[str], tool_name: Optional[str] = None) -> Optional[str]:
    """信任登记范围归一：文件类工具登记其【所在目录】, 目录/非文件信任域原样 — 小欧 2026-10-06

    2026-10-06 小欧 缺陷修复（北京老陈实测「连续信任4次仍反复弹窗」）：写入端此前恒登记叶子文件
    路径，而读取端 check_session_trust 的 `trusted_p in target_p.parents` 本就支持目录前缀继承
    —— 生产者从不产出目录，致「信任此操作」退化为「只信任这一个文件名」，换个文件名即重新弹窗。
    故落库前把文件收敛到所在目录，让既有读取端的前缀匹配真正生效（读取端零改动）。

    文件/目录判据（**不可用 is_dir()**：写入目标常常尚不存在，实测把 D:/a 这类不存在的目录
    误判为文件而收敛成盘根 D:\\，致整盘豁免的真退化）——按路径形态判，与 temp_auth.py:62-65
    「带后缀=文件」同一口径（DRY，不引第二套判据）：
      ① 真实存在的目录 → 原样保留（is_dir 为真）
      ② 带后缀 → 视为文件，收敛到所在目录
      ③ 不存在且无后缀 → 视为目录，原样保留（新建目录场景）

    非文件信任域(registry/sql)原样返回：其 path 是注册表键/SQL db 路径，非文件系统目录 — 小欧-2026-10-06
    """
    normalized = norm_trust_path(path, tool_name)
    if not normalized or tool_name in NON_FILE_TRUST_TOOLS:
        return normalized
    p = Path(normalized)
    try:
        if p.is_dir():
            return str(p)          # ① 真实目录
    except OSError:
        pass
    return str(p.parent) if p.suffix else str(p)


def insert_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> None:
    """HITL"信任本次会话"落库（UNIQUE(session_id, tool_name, path) 幂等）— 小欧 2026-08-16; v1.5 增 path 参数
    path=None=无路径工具的工具级通配; 非空=该路径及子目录树递归豁免
    2026-10-06 小欧 - 落库前经 trust_scope_path 归一：文件类工具登记【所在目录】而非叶子文件，
      否则"信任此操作"只对那一个文件名生效(实测连续信任 4 个文件仍 4 次弹窗) — 小欧-2026-10-06"""
    conn.execute(
        "INSERT OR IGNORE INTO chat_session_trust(session_id, tool_name, path, created_at) VALUES (?,?,?,?)",
        (session_id, tool_name, trust_scope_path(path, tool_name), get_local_iso_timestamp()),
    )


def check_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> bool:
    """工具安全检查豁免查询：会话已信任该 tool+path 则免二次 HITL 确认 — 小欧 2026-08-16; v1.5 增 path 前缀递归匹配
    匹配规则(北京老陈 2026-09-02 定案, 2026-10-05 修订为B):
      path=None: 仅命中本工具的通配行(path IS NULL);
      path 给定: 命中的是【本工具的path IS NULL通配行】, 或【任意工具登记的具体信任路径为该目标前缀祖先/等于】——
        即目录信任按 session_id 跨工具前缀豁免。path是None的无路径工具(execute_shell等)不受指定路径的其他工具信任影响。
    """
    # 2026-10-05 小欧 北京老陈裁定B: 目录信任跨工具生效, 具体规则见上方 docstring;
    #   撤销粒度仍是(session_id,tool_name,path) —— 删掉单行只撤销该工具的登记, 若需完全撤销某目录信任需删掉其下全部工具行 — 小欧-2026-10-05
    rows = conn.execute(
        "SELECT path FROM chat_session_trust WHERE session_id=? AND (tool_name=? OR path IS NOT NULL)",
        (session_id, tool_name),
    ).fetchall()
    if path is None:
        return any(r["path"] is None for r in rows)
    target = norm_trust_path(path, tool_name)
    if target is None:
        return False
    target_p = Path(target)
    for r in rows:
        p = r["path"]
        if p is None:
            return True  # 工具级通配行: 任意路径命中
        trusted_p = Path(p)
        if trusted_p == target_p or trusted_p in target_p.parents:
            return True  # 前缀递归: 信任根等于目标 或 为目标祖先目录
    return False


def get_session_id_by_task(conn: Connection, task_id: str) -> Optional[str]:
    """按 task_id 反查 session_id（chat_tasks 已建行时）— HITL trust 落库/豁免用, 禁止伪 agent.session_id — 小欧 2026-08-16"""
    row = conn.execute(
        "SELECT session_id FROM chat_tasks WHERE task_id=?",
        (task_id,),
    ).fetchone()
    return row["session_id"] if row else None