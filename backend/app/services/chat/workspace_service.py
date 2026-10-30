# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-14 小欧: 路径校验导入改从 app.safety.path_safe_check(路径校验已升系统层)
# 2026-10-21 小欧 - J3: _ws_deny_reason 准入口径 = 只拒禁区·系统档(forbidden_system),
#   forbidden_non_system 档(代码目录/允许根)放行, 修常见配置整单 422 — 小欧-2026-10-21
# 2026-10-28 小欧 - [54]全链路重构: workspace_property/memo/is_default 三标注字段。
#   常量+归一化唯一源; get/select/apply/set/classify/load/reconcile 全链路四元组化;
#   reconcile 始终创建默认工作区(项目根感知+旧默认降级)。标注字段不参与安全判定。
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

# 2026-10-28 小欧 - 属性/备注常量与标签映射（单一真源）
MAX_PROP_CHARS = 32
MAX_MEMO_CHARS = 256
WS_PROP_READ_ONLY = "read_only"
WS_PROP_READ_WRITE = "read_write"
WS_PROP_WRITE = "write"
WS_PROP_LABELS = {
    WS_PROP_READ_ONLY: "读取工作区",
    WS_PROP_READ_WRITE: "读写工作区",
    WS_PROP_WRITE: "写工作区",
}
DEFAULT_WS_PROP = WS_PROP_READ_WRITE           # 兜底：缺失一律回落 read_write
DEFAULT_MEMO = "本事项工作区默认读写区域"       # 默认目录专用备注（UI/界面口径：事项工作区）


def ws_prop_value(raw) -> str:
    """属性归一化唯一源（入库值）：None/空/全空白 → read_write；
    中文标签 → 对应机器值；其余（自定义文本）原样保留。
    纯文字标签, 不做任何权限判定。"""
    _v = (raw or "").strip()[:MAX_PROP_CHARS]
    if not _v:
        return DEFAULT_WS_PROP
    if _v in WS_PROP_LABELS:
        return _v
    for _k, _label in WS_PROP_LABELS.items():
        if _v == _label:
            return _k
    return _v                                   # 自定义文本标签，原样存


def ws_prop_label(raw) -> str:
    """属性展示/注入唯一源：机器值 → 中文标签；自定义值原样返回；缺失 → 读写工作区。"""
    _v = ws_prop_value(raw)
    return WS_PROP_LABELS.get(_v, _v)


def _normalize_ws_meta(prop, memo) -> tuple[str, Optional[str]]:
    """属性/备注归一化唯一源：trim → 空归默认 → 超长截断 → memo 换行转空格。

    属性是文字标签不是权限开关，故非法值一律**放行**（不 reject），
    只做长度与空白处理 —— 拒单会让整条 PATCH 失败，代价远大于收益。
    memo 禁换行：注入时按行拼接，换行会破坏 <会话工作目录> 块结构。"""
    _m = (memo or "").strip().replace("\r", " ").replace("\n", " ")[:MAX_MEMO_CHARS]
    return ws_prop_value(prop), (_m or None)


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
    """读该会话使用的全部目录行（含属性/备注/默认标志）。ORDER BY rowid = 加入顺序。"""
    return conn.execute(
        "SELECT path, workspace_property, memo, is_default FROM chat_session_workspaces "
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
    """会话目录合法性判据：返回拒绝原因(None=可用)。复用全局判据，不自造黑名单。

    2026-10-21 小欧 - J3 口径(北京老陈裁定): 准入只有一条 —— 不能落在**禁区·系统档**
      (forbidden_system, 写格=DENY; 非法路径/异常也兜底到该档, fail-closed)。
      forbidden_non_system 档(代码目录/允许根/启动目录)一律放行: 原实现 `if scope:` 把
      写线矩阵里的 CONFIRM 档也当 DENY → 常见配置整单 422, 会话目录根本设不上。
      宽根规则保留: 授权家目录/盘根会放大删除允许范围, 与档位无关。"""
    # 2026-10-15 小欧: path_safe_check.validate_path 已随三线分离删除,
    #   等价能力迁至 app.safety.write_path_check.validate_write(返回三元组, system 口径一致)。
    #   本函数原在函数内延迟导入, 拆分后未同步 -> 一旦调用即 ImportError, 故同步改口。
    # 2026-10-16 小欧 - 去越层: services 层只走写线公开接口, 不越过它直接摸底层分类模块
    from app.safety.write_path_check import validate_write as _validate_write_path
    from app.safety.path_dir_lists import SCOPE_FORBIDDEN_SYSTEM
    _ok, _msg, scope = _validate_write_path(p)
    if scope == SCOPE_FORBIDDEN_SYSTEM:
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


def _ws_apply(conn, session_id: str, entries: list[tuple[str, str, Optional[str]]]) -> None:
    """覆盖写 —— PATCH 的唯一写库实现（懒建占行不走这里）。

    DELETE 全删 → executemany INSERT(path, workspace_property, memo, is_default)。
    全删全插天然支持编辑：前端改了某条 path/属性/memo 后整批提交，
    后端不需要区分"新增/修改/删除"——全量覆盖即可。

    ⚠ is_default 由系统维护，前端 PATCH 无权携带：写库前先读旧默认行，
    覆盖时按 path（大小写不敏感）原样继承。否则用户每点一次「确定」都会把
    默认标志抹成 0，下次建任务再建一个新时间戳目录，历史产物被拆散。"""
    _old_defaults = {
        r["path"].casefold()
        for r in conn.execute(
            "SELECT path FROM chat_session_workspaces "
            "WHERE session_id = ? AND is_default = 1", (session_id,)).fetchall()
    }
    conn.execute("DELETE FROM chat_session_workspaces WHERE session_id = ?", (session_id,))
    if not entries:
        return
    conn.executemany(
        "INSERT INTO chat_session_workspaces"
        "(session_id, path, workspace_property, memo, is_default) "
        "VALUES (?, ?, ?, ?, ?)",
        [(session_id, p, r, m, 1 if p.casefold() in _old_defaults else 0)
         for p, r, m in entries])


def set_session_workspaces(conn, session_id: str, items: list[dict]) -> list[dict]:
    """PATCH 唯一写入口：数量先拦 → 归一化 → 去重 → 预检 → 写库。
    返回被拒清单；非空即调用方返 422，空即 200。

    入参固定 list[dict]（{"path", "workspace_property", "memo"}），与 WorkspaceItem 一对一。
    **不接收 list[str]**：API 层已收单形态，前后端同版本发布，没有旧形态需要兼容；
    保留分支会让"路径数组"与"三字段对象"两套语义长期并存（违反禁止 backward）。
    属性/memo **不参与预检**（不是路径，与安全判定无关）。
    前端编辑（改 path/属性/memo）后整批提交，本函数不区分新增/编辑——全量覆盖。"""
    if len(items) > MAX_WORKSPACES:
        return [{"path": f"({len(items)} 条)", "reason": f"目录数超上限({MAX_WORKSPACES})"}]

    entries, rejected, _seen = [], [], set()
    for it in items:
        _p = it.get("path", "")
        try:
            _n = _normalize_ws_path(_p)
        except (OSError, ValueError) as _e:
            rejected.append({"path": _p, "reason": f"路径非法: {type(_e).__name__}: {_e}"})
            continue
        _k = _n.casefold()
        if _k in _seen:                      # 去重(大小写不敏感)，存值保大小写
            continue
        _seen.add(_k)
        _prop, _memo = _normalize_ws_meta(it.get("workspace_property"), it.get("memo"))
        entries.append((_n, _prop, _memo))
    if rejected:
        return rejected                      # 归一化失败即整单 422，不再写库

    rejected = _ws_precheck([p for p, _r, _m in entries])
    if rejected:
        return rejected

    _ws_apply(conn, session_id, entries)
    logger.info(f"[workspace] 会话工作区已更新: session={session_id} 数量={len(entries)}")
    return []


def classify_workspace_rows(rows) -> tuple[list, list]:
    """行 → (有效条目集, 不可用清单)：**会话工作区过滤唯一真源**。

    返回值：effective 为 list[tuple[str, str, Optional[str], bool]]
    = [(path, workspace_property, memo, is_default)]。
    属性/备注/默认标志只**透传**，不参与任何裁决 ——
    归一化/禁区/宽根/存在性判定全部只看 path，安全语义零变化。

    ⚠ 本函数只判定不落盘：面板 GET 走这里，因此打开面板永不创建目录。

    裁决顺序（禁区判定必须先于存在判定）：
       归一化失败 → 不可用（优雅跳过，绝不抛；调用方整单不崩）
       `_ws_deny_reason` 全套判据 → 不可用（禁区/系统保护/宽根）
       非目录（不存在，或是个文件）→ 不可用
       通过 → 有效

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
        _prop, _memo = _normalize_ws_meta(r["workspace_property"], r["memo"])
        _is_def = bool(r["is_default"])
        effective.append((p, _prop, _memo, _is_def))
    return effective, unusable


def _load_workspaces_conn(conn, session_id: str) -> list[tuple[str, str, Optional[str], bool]]:
    """任务快照源：读行 → 过滤（复用 classify_workspace_rows 单一真源）。
    返回 [(path, workspace_property, memo, is_default)] 四元组，供 _load_ws_snapshot 构造。

    不可用行必须告警：目录被改名、移动或盘符没挂时若静默跳过，徽标显示 N 而运行时生效 0，
    且行还在、进入会话时也不会补建，错位会一直持续。"""
    effective, unusable = classify_workspace_rows(get_session_workspaces(conn, session_id))
    for u in unusable:
        _ws_warn(f"会话工作区本轮不生效({u['reason']}): {u['path']}")
    return effective


def reconcile_session_workspaces(conn, session_id: str) -> list[tuple[str, str, Optional[str], bool]]:
    """创建新 Task 并绑定该会话时的唯一落盘入口。

    默认工作区始终存在（先添加目录也建）→ 逐条裁决（禁区行清库 / 缺目录则建 / 可用则留）
    → 返回有效条目集。用户目录同样在此懒建（面板 GET 不建，只此处建）。
    返回 [(path, workspace_property, memo, is_default)] 四元组。

    ⚠ 只删数据库行，绝不删除磁盘目录。"""
    from app.config import get_config
    rows = get_session_workspaces(conn, session_id)
    current_root = get_config().get_project_root()

    # ── 默认工作区是否需创建/重建 ──
    # 需要（任一）：a) 无任何 is_default=1 行（首次，或用户删了默认行）
    #               b) 默认行不在当前项目根下（项目根变了）
    need_new_default = True
    for r in rows:
        if r["is_default"] and Path(r["path"]).parent == Path(current_root):
            need_new_default = False
            break

    if need_new_default:
        d = _build_default_workspace_dir(session_id)
        if d:
            try:
                _p = _normalize_ws_path(d)
                # 先登记/升级新默认（同路径已存在则原地置 1），再降级其余默认行 ——
                # 顺序不可颠倒：先降后插一旦插入失败，会话将没有任何默认工作区
                conn.execute(
                    "INSERT INTO chat_session_workspaces"
                    "(session_id, path, workspace_property, memo, is_default) "
                    "VALUES (?, ?, ?, ?, 1) "
                    "ON CONFLICT(session_id, path) DO UPDATE SET "
                    "workspace_property = excluded.workspace_property, "
                    "memo = excluded.memo, is_default = 1",
                    (session_id, _p, DEFAULT_WS_PROP, DEFAULT_MEMO))
                # 旧默认目录降为普通目录（保留历史产物，用户可自行处置）
                conn.execute(
                    "UPDATE chat_session_workspaces SET is_default = 0 "
                    "WHERE session_id = ? AND is_default = 1 AND path <> ?",
                    (session_id, _p))
                logger.info(f"[chat] 默认工作区已就绪: session={session_id} path={_p}")
            except Exception as _e:
                logger.warning(f"[chat] 默认工作区登记失败（本轮无默认区，下次再试）: {_e}")
        rows = get_session_workspaces(conn, session_id)

    _, unusable = classify_workspace_rows(rows)
    for u in unusable:
        if u["kind"] != "denied":
            continue                                     # 脏行/缺目录：本轮跳过，下次再看
        try:                                             # 禁区行：从表里清掉（只删库行）
            conn.execute(
                "DELETE FROM chat_session_workspaces WHERE session_id = ? AND path = ?",
                (session_id, u["path"]))
        except Exception as _de:
            logger.warning(f"[chat] 禁区目录清理失败(本轮仍不放行): {u['path']} - {_de}")
            continue
        logger.warning(f"[chat] 会话工作区已落入禁区, 已从列表清理: {u['path']}")

    for u in unusable:                                   # 缺目录：建出来（禁区/脏行不建）
        if u["kind"] != "missing":
            continue
        try:
            Path(u["path"]).mkdir(parents=True, exist_ok=True)
            logger.info(f"[chat] 会话工作区目录不存在, 已自动建立: {u['path']}")
        except Exception as _e:
            logger.warning(f"[chat] 会话工作区目录建立失败(本轮不生效, 下次再试): {u['path']} - {_e}")

    return _load_workspaces_conn(conn, session_id)       # 重读重判：刚建好的目录本轮即生效


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