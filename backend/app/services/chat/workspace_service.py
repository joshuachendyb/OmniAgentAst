# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-14 小欧: 路径校验导入改从 app.safety.path_safe_check(路径校验已升系统层)
"""会话使用的目录：存储与落值（独立模块，不进 storage.py）

本模块只管**会话使用的目录**（= 本次任务产物落在这里）。
⚠ 授权目录不在这里 —— 授权目录归全局配置管（workspace.allowed_dirs / project_root）。

编辑历史: 2026-10-10 小欧 新建 — 会话目录存储层
编辑历史: 2026-10-10 小欧 概念订正 — 表只装"会话使用的目录", 删 is_default / ws_initialized
           两个为错误概念而生的字段, 删 get_session_default_dir/get_authorized_dirs 两个取数口
"""
from pathlib import Path
from typing import Optional

from app.logger import logger

WORKSPACE_REJECTED_FIELD = "workspace_rejected"
MAX_WORKSPACES = 64        # 单会话目录数上限(防一条 PATCH 灌爆面板/库)
MAX_PATH_CHARS = 240       # 显式长度上限(Windows MAX_PATH 260 留余量), 不靠底层 resolve 碰运气
                           # 撤回(2026-10-10)：240→200 系无实证收紧 ——
                           #   从未有真实路径因此失败，且会拒绝原本合法的 200~240 字符路径。
                           #   恢复 240 原值；要收紧必须先有真实失败 case。


def _ws_warn(msg: str) -> None:
    """统一告警出口：日志前缀只此一处(DRY)，测试可直挂 handler 断言"""
    logger.warning(f"[workspace] {msg}")


def _normalize_ws_path(p: str) -> str:
    """归一化唯一源：空串/非绝对/超长硬拒 → resolve 绝对化 + 去尾分隔符。

    订正：**保大小写入库**。Windows 大小写不敏感是"比较规则"不是"存储规则"，
    casefold 存库会导致面板全小写且无法恢复。去重走 casefold 键 + 库级 COLLATE NOCASE，
    存储本身必须无损。

    空串必须硬拒：`Path("").expanduser().resolve()` 返回**进程 cwd** 且不抛异常，
    不拦等于把整个后端启动目录静默授权。

    ⚠ 仍可能抛 OSError/ValueError（断开的 UNC 实测抛 OSError WinError 64），调用方必须捕获。"""
    if not p or not p.strip():
        raise ValueError("路径为空")
    _raw = p.strip()
    if not Path(_raw).is_absolute():
        raise ValueError(f"须为绝对路径(相对路径会随进程 cwd 漂移): {_raw}")
    if len(_raw) > MAX_PATH_CHARS:
        raise ValueError(f"路径过长({len(_raw)}>{MAX_PATH_CHARS}): {_raw[:60]}...")
    return str(Path(_raw).expanduser().resolve()).rstrip("\\/")


def get_session_workspaces(conn, session_id: str) -> list:
    """读该会话使用的全部目录行。ORDER BY rowid = 加入顺序。"""
    return conn.execute(
        "SELECT path FROM chat_session_workspaces "
        "WHERE session_id = ? ORDER BY rowid",
        (session_id,),
    ).fetchall()


def _is_broad_root(p: str) -> bool:
    """是否"宽根"：家目录本身或其上级(用户目录/盘根)。

    为什么禁：这类目录并入删除允许根后，会把"可删范围"放大到整个用户目录。
    判据取自全局事实(家目录 + 祖先链)，不自造路径黑名单。
    家目录**之内**的路径不拦(那是正常用法)。

    订正：fail-closed。安全判据解析失败时必须按"宽根"处理(拒绝)，
    不能按"非宽根"放行，且必须留日志，否则保护静默消失。"""
    try:
        home = Path.home().resolve()
        target = Path(p)
        return target == home or target in home.parents
    except (OSError, ValueError) as _e:
        _ws_warn(f"宽根判定异常, 按 fail-closed 拒绝: {p} ({_e})")
        return True


def _ws_deny_reason(p: str) -> Optional[str]:
    """会话目录合法性判据：返回拒绝原因(None=可用)。**全部复用全局判据，不自造黑名单**。

    ★2026-10-19 小欧 - 目录数组归一化: 单一真源已收敛到 write_path_check.validate_write
      (五档归属 scope + PERMISSION 矩阵), 本函数只调这一个公开接口, 不再自行判禁区。
      覆盖场景: check_preconditions(空路径/`..`穿越/异常) 与 classify_scope/permission_of
      自身异常一律兜底为 SCOPE_FORBIDDEN_SYSTEM, 确认档与放行档的区分由写线内部完成。
    另加宽根规则(本模块判据)：授权/使用宽根等于放大删除范围。"""
    # 2026-10-15 小欧: path_safe_check.validate_path 已随三线分离删除,
    #   等价能力迁至 app.safety.write_path_check.validate_write(返回三元组, system 口径一致)。
    #   本函数原在函数内延迟导入, 拆分后未同步 -> 一旦调用即 ImportError, 故同步改口。
    # 2026-10-16 小欧 - 去越层: services 层只走写线公开接口, 不越过它直接摸底层分类模块
    from app.safety.write_path_check import validate_write as _validate_write_path
    from app.safety.path_dir_lists import SCOPE_FORBIDDEN_NON_SYSTEM, SCOPE_FORBIDDEN_SYSTEM
    _ok, _msg, scope = _validate_write_path(p)
    if scope:
        # _ok=True 而 scope 非空 = 该档已获任务级授权(写线放行), 此时 _msg 为 None,
        #   需自己拼文案, 否则用户只看到无信息量的"路径在全局禁区内"。
        if _ok:
            return f"路径位于{scope}类保护区自身或其上级({p}), 不可直接作为会话目录"
        return _msg or "路径在全局禁区内"
    if _is_broad_root(p):
        return "宽根目录(家目录/用户目录/盘根)不可作为会话目录: 会放大删除允许范围"
    return None


def _ws_precheck(paths: list[str]) -> list[dict]:
    """合法性预检：逐条走判据。返回被拒清单，不抛异常（调用方整单 422）。"""
    rejected = []
    for p in paths:
        reason = _ws_deny_reason(p)
        if reason:
            rejected.append({"path": p, "reason": reason})
    return rejected


def _ws_apply(conn, session_id: str, paths: list[str]) -> None:
    """覆盖写 —— PATCH 的唯一写库实现（懒建占行不走这里）。
    先读旧路径 → DELETE 全删 → executemany INSERT。"""
    conn.execute("DELETE FROM chat_session_workspaces WHERE session_id = ?", (session_id,))
    if not paths:
        return
    conn.executemany(
        "INSERT INTO chat_session_workspaces(session_id, path) VALUES (?, ?)",
        [(session_id, p) for p in paths])


def set_session_workspaces(conn, session_id: str, raw_paths: list[str]) -> list[dict]:
    """PATCH 唯一写入口：数量先拦 → 归一化 → 去重 → 预检 → 写库。
    返回被拒清单；非空即调用方返 422，空即 200。
    归一化单条失败（OSError/ValueError，含空串/相对路径/超长）归入 rejected 一并报出，不 500。
    ⚠ 只改数据库行，**绝不删除磁盘目录** —— 面板移除条目 = 目录留在磁盘由用户自行处置。

    订正：数量检查必须在归一化之前。归一化每条都做磁盘 resolve，
    超量请求先归一化后拒绝等于先吃全部 IO 再说不(实测 3000 条 209ms)。
    订正：去重键用 casefold，存值保大小写(Windows 大小写不敏感，
    `C:\\A` 与 `c:\\a` 是同一目录，去重后只留一条；库级再有 COLLATE NOCASE 兜底)。"""
    if len(raw_paths) > MAX_WORKSPACES:
        return [{"path": f"({len(raw_paths)} 条)", "reason": f"目录数超上限({MAX_WORKSPACES})"}]
    paths, rejected, _seen = [], [], set()
    for p in raw_paths:
        try:
            _n = _normalize_ws_path(p)
        except (OSError, ValueError) as _e:
            rejected.append({"path": p, "reason": f"路径非法: {type(_e).__name__}: {_e}"})
            continue
        _k = _n.casefold()
        if _k not in _seen:                  # 去重(大小写不敏感)，存值保大小写
            _seen.add(_k)
            paths.append(_n)
    if rejected:
        return rejected                      # 归一化失败即整单 422，不再写库
    rejected = _ws_precheck(paths)
    if rejected:
        return rejected
    _ws_apply(conn, session_id, paths)
    logger.info(f"[workspace] 会话使用目录已更新: session={session_id} 数量={len(paths)}")
    return []


def classify_workspace_rows(rows) -> tuple[list, list]:
    """行 → (有效路径集, 不可用清单)：**会话目录过滤唯一真源**。
    入参是行而非 conn，故调用方可在关闭 DB 连接之后再做磁盘判定。
    不在此处打日志：调用方按场景决定要不要告警（运行时必须告警）。

    裁决顺序（禁区判定必须先于存在判定）：
       归一化失败 → 不可用（优雅跳过，绝不抛；调用方整单不崩）
       `_ws_deny_reason` 全套判据 → 不可用（禁区/系统保护/宽根）
       非目录（不存在，或是个文件）→ 不可用
       通过 → 有效

    根因订正：此前运行时过滤只调半套 `classify_forbidden_path`，
    与写入判据两套标准、且 exists 跑在禁区之前。此处改调全套 `_ws_deny_reason`，
    与 PATCH 预检同一把尺子；脏行一律归入 unusable，调用方永不被抛异常掀翻。
    订正：`exists()` 改为 `is_dir()`。文件不是目录，不能进白名单。
    订正：返回 `list[str]`。`(path, 恒0)` 裸 tuple 是 is_default 死后残留，
    全链路无人读第二项。
    说明（非缺陷）：此处对已归一路径再 resolve 一次是**故意的**——
    入库 resolve 防重，运行 resolve 防 TOCTOU（两次调用之间符号链接可被替换）。
    单行约 0.09ms，64 行约 6ms，相对 LLM 秒级延迟可忽略；缓存反而引入失效复杂度(YAGNI)。

    unusable 每项带机器可读 `kind`（reconcile 按 kind 行事，不匹配 reason 字符串）：
      illegal（归一化失败）/ denied（禁区/系统保护/宽根）/ missing（非目录或不存在）"""
    effective, unusable = [], []
    for r in rows:
        try:
            p = _normalize_ws_path(r["path"])
        except (OSError, ValueError) as _e:
            unusable.append({"path": r["path"], "reason": f"路径非法({type(_e).__name__})",
                             "kind": "illegal"})
            continue
        reason = _ws_deny_reason(p)          # 禁区判定先行，全套判据
        if reason:
            unusable.append({"path": p, "reason": reason, "kind": "denied"})
            continue
        if not Path(p).is_dir():             # 必须是目录：不存在/是文件都不收
            unusable.append({"path": p, "reason": "不是目录或不存在", "kind": "missing"})
            continue
        effective.append(p)
    return effective, unusable


def _load_workspaces_conn(conn, session_id: str) -> list[str]:
    """任务快照源：读行 → 过滤（复用 classify_workspace_rows 单一真源）。
    conn 由调用方经 db.atxn 传入，本函数内禁自建连接。空会话/无行 → []。

    不可用行必须告警：目录被改名、移动或盘符没挂时若静默跳过，徽标显示 N 而运行时生效 0，
    且行还在、进入会话时也不会补建，错位会一直持续。"""
    effective, unusable = classify_workspace_rows(get_session_workspaces(conn, session_id))
    for u in unusable:
        _ws_warn(f"会话目录本轮不生效({u['reason']}): {u['path']}")
    return effective


def reconcile_session_workspaces(conn, session_id: str) -> list[str]:
    """进入会话·建立一条规则（唯一真源）：空则造默认目录 → 逐条裁决 →
    禁区行清库 / 不存在则建目录 / 可用则留 → 返回有效路径集。

    根因订正：此前编排器自写一套循环，归一化无 try，一条脏行抛异常
    掀翻整个任务。此处复用 `classify_workspace_rows` 做全部裁决（脏行只进
    unusable 不抛），本函数只做 classify 干不了的两件事：造默认目录、建目录/清行。
    ⚠ 只删数据库行，**绝不删除磁盘目录**。"""
    rows = get_session_workspaces(conn, session_id)
    if not rows:
        d = _build_default_workspace_dir(session_id)
        if d:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO chat_session_workspaces(session_id, path) VALUES (?, ?)",
                    (session_id, _normalize_ws_path(d)),
                )
            except Exception as _e:
                logger.warning(f"[chat] 默认目录登记失败（降级走项目根）: {_e}")
        rows = get_session_workspaces(conn, session_id)

    _effective, unusable = classify_workspace_rows(rows)
    for u in unusable:
        if u["kind"] != "denied":
            continue                             # 脏行/缺目录：本轮跳过，下次再看
        try:                                     # 禁区行：从表里清掉（只删库行）
            conn.execute(
                "DELETE FROM chat_session_workspaces WHERE session_id = ? AND path = ?",
                (session_id, u["path"]))
        except Exception as _de:                 # 订正：失败就只报失败，
            logger.warning(f"[chat] 禁区目录清理失败(本轮仍不放行): {u['path']} - {_de}")
            continue                             #   不再无条件打"已清理"
        logger.warning(f"[chat] 会话目录已落入禁区, 已从列表清理: {u['path']}")

    for u in unusable:                           # 缺目录：建出来（禁区/脏行不建）
        if u["kind"] != "missing":
            continue
        try:
            Path(u["path"]).mkdir(parents=True, exist_ok=True)
            logger.info(f"[chat] 会话目录不存在, 已自动建立: {u['path']}")
        except Exception as _e:
            logger.warning(f"[chat] 会话目录建立失败(本轮不生效, 下次再试): {u['path']} - {_e}")

    return _load_workspaces_conn(conn, session_id)   # 重读重判：刚建好的目录本轮即生效


def _build_default_workspace_dir(session_id: str):
    """默认事务目录 = {项目根}\\{YYYYMMDD-HHMMSS}-{会话标识前4位}。
    从 stream_orchestrator 下沉至此(2026-10-10)：它是 workspace 的事不是编排的事，
    reconcile 在本模块，倒挂 import 会破分层。

    撤回(2026-10-10)：此前称"前4位会重名"是误报 —— 验证用的
    aaaa1111/aaaa2222 是人为构造的同秒同前缀，真实 UUID 前4位随机(65536 种)，
    碰撞需同秒建会话且前缀相同，概率可忽略。恢复 [:4] 原设计，不做过度工程。
    sanitize: Windows 非法字符 \\/:*?"<>| → _；首尾空格与结尾 . 去除；空 → session。
    同名已存在**直接返回同一路径**(不换名)：调用方 mkdir 用 exist_ok=True，已存在即复用。
    项目根不存在/非目录 → 返回 None（调用方降级走项目根兜底）。"""
    from app.config import get_config
    from app.utils.time_utils import now_str
    root = get_config().get_project_root()
    if not root or not Path(root).is_dir():
        return None
    import re

    ts = now_str("%Y%m%d-%H%M%S")
    name = re.sub(r'[\\/:*?"<>|]', "_", (session_id or "").strip())[:4].strip(" .") or "session"
    return str(Path(root) / f"{ts}-{name}")


def session_exists(conn, session_id: str) -> bool:
    """会话存在性：存在且未删才放行，否则调用方返 404。
    必要性：PRAGMA foreign_keys=ON 下，对不存在 session_id 的 INSERT 会抛
    sqlite3.IntegrityError → 500。

    订正：`is_deleted = FALSE` 漏掉 NULL。is_deleted 列是后 ADD 的，
    存量行全是 NULL，三值逻辑下 `NULL = FALSE` 恒不成立 → 老会话全 404。
    改 COALESCE，NULL 按未删处理（与 link_enabled 的存量 NULL 惯例一致）。"""
    row = conn.execute(
        "SELECT 1 FROM chat_sessions WHERE id = ? AND COALESCE(is_deleted, FALSE) = FALSE",
        (session_id,),
    ).fetchone()
    return row is not None