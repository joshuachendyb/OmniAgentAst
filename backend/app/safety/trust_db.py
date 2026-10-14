# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 - 小欧 - 架构边界修正(三堂会审): 会话信任读写三函数从 app/services/chat/storage.py
#   迁入本层 app/safety/trust_db.py —— 修复 app/tools 禁 app.services 依赖方向守护违规
#   (test_architecture_boundaries.py test_layer_boundaries 报 trust.py imports app.services.chat.storage)。
#   原逻辑逐字复制不改业务(能复制不重写): get_session_id_by_task/check_session_trust/insert_session_trust
#   + _norm_trust_path(储storage侧 delete/list 仍使用, 双侧各持一份保持落库/查询一致)。
#   迁移后 trust.py 由 import app.services.chat.storage 改为 import app.safety.trust_db(同层, 零越层)。
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
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust_db.py 迁入 app/safety/(业务逻辑一字不改)。
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust_db.py 迁入 app/safety/(业务逻辑一字不改); 旧文件已删。
# 2026-10-15 - 小欧 - 文档[33] 5.17(P5步21): 会话信任 TTL 落地。
#   新增 _ttl_expiry()(now+security.trust_ttl_days, 默认90天) / _not_expired_clause()(未过期判据单源) /
#   cleanup_expired_trust()(删 expires_at<=now, 返回条数); insert 同步写 expires_at;
#   check 查询加未过期过滤(过期行不再豁免)。NULL=不过期, 存量行行为不变。
#   边界: UNIQUE(session_id,tool_name,path) + INSERT OR IGNORE 下重复信任**不续期** ——
#   续期等于「点一次就永久有效」, 与 TTL 初衷相悖。— 小欧-2026-10-15
# 2026-10-15 - 小欧 - 文档[33] 5.23: 本文件历史条目内的旧路径按终态订正(第4/8行 app/tools/trust_db.py → app/safety/trust_db.py)。
#   北京老陈裁定「改」: 编辑历史内的**路径**具误导性(读者会以为该路径仍可用), 故订正; 仅动路径字面,
#   事件的日期/署名/描述一字不改(保留「2026-09-05 迁入」这一事实本身)。— 小欧-2026-10-15
# 2026-10-15 - 北京老陈裁定 - insert_session_trust 增 task_id 形参并落库(可追溯/审计)。
#   边界三条: ①**不进 UNIQUE 键**(否则同一路径跨任务重复建行, 功能退化);
#   ②**check_session_trust 不按它过滤**(否则跨任务信任失效); ③存量行 task_id=NULL 表"来源未知",
#   豁免行为与加列前完全一致(零退化)。调用方 trust.save_session_trust 形参本就持有 task_id, 顺手透传。
#   随后北京老陈裁定「改成记最后一次」: INSERT OR IGNORE → UPSERT(ON CONFLICT DO UPDATE SET task_id),
#   只 set task_id 一个字段 —— created_at/expires_at 保持首次值, 故 TTL 不因重复点击而续期。— 小欧-2026-10-15
#   **已知既有边界(非本次引入, UPSERT 也不修)**: SQLite 的 UNIQUE 列含 NULL 时 NULL 互不相等,
#   故 path IS NULL 的行(无路径工具 shell/execute_sql/registry_*)去重失效, 每次点信任都新增一行;
#   此场景下无冲突可捕获, INSERT OR IGNORE 与 ON CONFLICT **同样不生效**。待后续设计决策。— 小欧-2026-10-15
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust_db.py 迁入 app/safety/(业务逻辑一字不改)。
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust_db.py 迁入 app/safety/(业务逻辑一字不改)。
"""tools 层会话信任读写(纯 SQL 查询, 不依赖 services 层) — 小欧 2026-09-05"""
from pathlib import Path
from typing import Optional
from sqlite3 import Connection

from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库
from app.tools.tool_constants import NON_FILE_TRUST_TOOLS  # 小欧 2026-09-16 非文件信任域(与 storage:561 撤销侧同位)
from app.config import get_config  # 2026-10-15 小欧 - 文档[33] 5.17: TTL 天数读 security.trust_ttl_days


# 2026-10-15 小欧 - 文档[33] 5.17: 会话信任 TTL(落库写过期时刻 → 查询按未过期过滤 → 周期清理)
#   病根: 信任一旦落库即永久有效, 用户点过一次「信任本次会话」后该路径永远不再弹窗,
#   撤权无路径、时间无上限。TTL 是唯一的自然撤销手段。
#   NULL 语义: expires_at IS NULL = 不过期 —— 存量行(未写该列)保持原有行为不被误杀。
DEFAULT_TRUST_TTL_DAYS = 90


def _ttl_expiry() -> str:
    """信任过期时刻 = now + security.trust_ttl_days(默认 90 天) — 小欧 2026-10-15

    与 created_at 同为本地 naive ISO, 同格式可字典序比较, 故 SQL 侧直接字符串比较即可。
    配置值 <= 0 视为「不设过期」(写 NULL), 供运维关闭 TTL。
    """
    try:
        days = get_config().get("security.trust_ttl_days", DEFAULT_TRUST_TTL_DAYS)
    except Exception:
        days = DEFAULT_TRUST_TTL_DAYS
    if not days or days <= 0:
        return None
    from datetime import datetime, timedelta
    return (datetime.now() + timedelta(days=days)).isoformat()


def _not_expired_clause() -> str:
    """未过期判定 SQL 片段(单源) — 小欧 2026-10-15

    查询侧(check_session_trust)与清理侧(cleanup_expired_trust)共用同一判据,
    免得两处各写一份日后漂移 —— 「什么算过期」只能有一个答案。
    NULL = 不过期, 兼容存量行。
    """
    return "(expires_at IS NULL OR expires_at > ?)"


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


def insert_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None,
                         task_id: Optional[str] = None) -> None:
    """HITL"信任本次会话"落库（UNIQUE(session_id, tool_name, path) 幂等）— 小欧 2026-08-16; v1.5 增 path 参数
    path=None=无路径工具的工具级通配; 非空=该路径及子目录树递归豁免
    2026-10-06 小欧 - 落库前经 trust_scope_path 归一：文件类工具登记【所在目录】而非叶子文件，
      否则"信任此操作"只对那一个文件名生效(实测连续信任 4 个文件仍 4 次弹窗) — 小欧-2026-10-06
    2026-10-15 小欧 - 文档[33] 5.17: 落库写 expires_at(now+TTL), 信任不再是永久有效。— 小欧-2026-10-15
    2026-10-15 北京老陈裁定 - 增 task_id(可追溯): 记录该条信任由哪个任务产生, 供事后审计。
      **不进 UNIQUE 键、也不参与豁免判定** —— 信任仍是会话级, task_id 纯只读旁挂。
      落库改 UPSERT: 重复信任时 task_id 记【最后一次】(审计要看最近一次是谁点的)。
      UPSERT 只 set task_id —— created_at/expires_at 保持首次值, 故 TTL 不因重复点击而续期。— 小欧-2026-10-15

    TODO(临时决策, 待后续完善 -- 北京老陈 2026-10-15 裁定登记): path IS NULL 的行去重失效。
      现象: 无路径工具(bash / execute_sql / registry_*)每点一次「信任本次会话」就新增一行。
      根因: SQLite 的 UNIQUE 约束中 NULL 与 NULL 互不相等, (S, bash, NULL) 与 (S, bash, NULL)
            被判为两行 => 无冲突可捕获, 故 INSERT OR IGNORE 与 ON CONFLICT **同样不生效**。
      为何是临时决策: 这类工具恰恰是信任风险最高的一类(一条 bash 信任覆盖整条命令),
            重复建行属真实缺陷, 但修它必须动唯一键, 属设计决策, 本次不擅自改。
      三个候选(均需清洗存量行 + 改查询语义, 后续设计时择一):
        A 哨兵值     —— path 为 NULL 时改存 '' (需同步改 check_session_trust 的 None 判定)
        B 表达式索引 —— UNIQUE(session_id, tool_name, COALESCE(path,''))
                        (SQLite 支持, 但 ON CONFLICT 目标写法随之变复杂)
        C 先查后写   —— SELECT 有则 UPDATE 无则 INSERT (有竞态窗口, 多任务并发可能双写)
      现状已由 tests/test_p5_trust_task_id.py::test_null_path_dedup_is_a_preexisting_limit
      锁定(断言 2 行), 防止后人误以为已修; 修好后该测试应同步改为断言 1 行。— 小欧-2026-10-15
    """
    conn.execute(
        "INSERT INTO chat_session_trust"
        "(session_id, tool_name, path, created_at, expires_at, task_id) VALUES (?,?,?,?,?,?)"
        " ON CONFLICT(session_id, tool_name, path) DO UPDATE SET task_id=excluded.task_id",
        (session_id, tool_name, trust_scope_path(path, tool_name),
         get_local_iso_timestamp(), _ttl_expiry(), task_id),
    )


def check_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> bool:
    """工具安全检查豁免查询：会话已信任该 tool+path 则免二次 HITL 确认 — 小欧 2026-08-16; v1.5 增 path 前缀递归匹配
    [SA2] 权限信任框架第2步信任判定实体, 上游trust.resolve_skip — 小欧-2026-10-14
    匹配规则(北京老陈 2026-09-02 定案, 2026-10-05 修订为B):
      path=None: 仅命中本工具的通配行(path IS NULL);
      path 给定: 命中的是【本工具的path IS NULL通配行】, 或【任意工具登记的具体信任路径为该目标前缀祖先/等于】——
        即目录信任按 session_id 跨工具前缀豁免。path是None的无路径工具(execute_shell等)不受指定路径的其他工具信任影响。
    """
# 2026-10-05 小欧 北京老陈裁定B: 目录信任跨工具生效, 具体规则见上方 docstring;
    #   撤销粒度仍是(session_id,tool_name,path) —— 删掉单行只撤销该工具的登记, 若需完全撤销某目录信任需删掉其下全部工具行 — 小欧 2026-10-05
    # 2026-10-15 小欧 - 文档[33] 5.17: 加未过期过滤, 过期行不再豁免(TTL 生效点)。
    #   判据复用 _not_expired_clause() 单源, 与清理侧同口径。
    rows = conn.execute(
        f"SELECT path FROM chat_session_trust WHERE session_id=? AND (tool_name=? OR path IS NOT NULL)"
        f" AND {_not_expired_clause()}",
        (session_id, tool_name, get_local_iso_timestamp()),
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


def cleanup_expired_trust(conn: Connection) -> int:
    """清理已过期的会话信任行, 返回删除条数 — 小欧 2026-10-15

    文档[33] 4.16/5.17。落点判据: 与 insert/check/delete 同域故落本文件(信任读写一体);
    不落 task_registry(内存任务注册表, 无 DB 清理职责)、不落 storage(会话业务读写层, 异域)、
    不设调度中间层(main.py 是唯一调用方, 为单调用方造归口违 KISS-DIRECT)。

    判据与 check_session_trust 共用 _not_expired_clause(): NULL=不过期 保留,
    只删 expires_at <= now 的行 —— 即使本函数没跑, 查询侧过滤已使过期行不豁免,
    本函数只负责回收存储, 不承担正确性。
    """
    cur = conn.execute(
        f"DELETE FROM chat_session_trust WHERE NOT ({_not_expired_clause()})",
        (get_local_iso_timestamp(),),
    )
    return cur.rowcount or 0