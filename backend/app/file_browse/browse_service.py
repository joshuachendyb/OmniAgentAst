# -*- coding: utf-8 -*-
# 编辑历史: 2026-10-13 小欧 - 文档[28] v3.7: 文件浏览服务层(路径边界+递归扫描+读文本/图片+recent-files) — 小欧-2026-10-13
#   同批新增 _scan_dir / _walk / _resolve_within_root 三个私有函数：前两者是"唯一实现"
#   （防多处分叉），后者是"安全唯一入口"（五个对外端点全部经它）。
# 2026-10-13 小欧 - 文件名 service.py → browse_service.py：与既有 app/services/lifecycle/service.py
#   撞名，且项目主流命名为 *_service.py（8 处）。改名后语义也更精确（非通用 service，是浏览服务）。
"""文件浏览服务：项目根目录内的只读浏览。

对外五个函数：
    get_workspace_info / build_tree / read_text_file / read_image_file / recent_files

三条不可协商的边界（v3.4 北京老陈裁定）：
  1. 只读 —— 本模块无任何写路径
  2. 不出项目根目录 —— 唯一判定点在 _resolve_within_root
  3. 不跳过任何目录、不做文件类型黑名单 —— 目录里有什么就返回什么
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.responses import FileResponse

from app.config import get_config, get_code_root
from app.db import db
from app.logger import logger
from app.file_browse.errors import (
    FILE_TOO_LARGE,
    IMAGE_TOO_LARGE,
    INVALID_PATH,
    NOT_FOUND,
    PATH_FORBIDDEN,
    PATH_OUTSIDE_ROOT,
    SESSION_NOT_FOUND,
    UNDECODABLE,
    UNSUPPORTED_TYPE,
    fail,
)

# ── 常量（后缀规则唯一真源，前端不自己判后缀） ──────────────────────────
TEXT_EXTS = {".txt", ".md"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg"}
IMAGE_MIME = {                      # 显式映射，不用 mimetypes 猜：猜错会把二进制当 text/plain 吐出
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".svg": "image/svg+xml",
}
MAX_TEXT_BYTES = 2 * 1024 * 1024        # C1，北京老陈定
MAX_IMAGE_BYTES = 10 * 1024 * 1024     # C3，北京老陈定
MAX_TREE_DEPTH = 5                     # C2，北京老陈定
MAX_TREE_NODES = 5000                  # C2，北京老陈定

# utf-8-sig 必须在 utf-8 之前 —— 2026-10-13 小欧 - 真实缺陷(单测 c03 抓出)：
#   含 BOM 的文件用 utf-8 解码**也会成功**，只是首字符残留 '\ufeff'，
#   于是永远走不到 utf-8-sig 分支 → Markdown 首行 '# 标题' 带上不可见 BOM 而失效。
#   utf-8-sig 对无 BOM 文件与 utf-8 等价，故前置安全。
_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")   # Windows 中文环境常见
_TIME_FMT = "%Y-%m-%d %H:%M:%S"
_RECENT_SCAN_LIMIT = 200      # 扫描步数上限
_RECENT_KEEP = 50             # 返回条数上限


# ══════════════════════════════════════════════════════════════════════
# 私有：路径边界（安全唯一入口）
# ══════════════════════════════════════════════════════════════════════

_CODE_ROOT_WARNED = False     # 2026-10-13 小欧 - S6/M17: 降级提示只打一次，否则每次请求刷屏


def _code_root() -> Optional[Path]:
    """代码库根（realpath 后）。取不到返回 None —— **唯一取值点**。

    2026-10-13 小欧 - DRY: 原先本函数、_resolve_within_root、get_workspace_info
    各自 realpath(get_code_root()) 一遍，同一根算三遍；收敛到此。
    """
    try:
        root = get_code_root()
    except (OSError, AttributeError):   # noqa: BLE001 - 取不到代码根不该让只读浏览全废
        return None
    if not root:
        return None
    try:
        return Path(os.path.realpath(root))
    except OSError:
        return None


def _code_root_conflicts(root: Path) -> bool:
    """project_root 是否落在代码库根子树内 → 决定禁区是否生效（S6 消解规则）。"""
    cr = _code_root()
    return bool(cr) and (cr == root or cr in root.parents)


def _resolve_within_root(rel_path: str) -> Tuple[Path, str]:
    """把用户传入的相对路径解析为项目根内的绝对路径。

    返回 (target, normalized_rel)。任何越界/非法一律 fail()，绝不返回半成品。

    2026-10-13 小欧 - 边界判定用**祖先关系**而非字符串前缀：
    `F:\\proj-evil` 是 `F:\\proj` 的兄弟而非子目录，前缀比较会误放行。
    """
    global _CODE_ROOT_WARNED
    raw = (rel_path or "").strip()
    rel = raw or "."
    if Path(rel).is_absolute() or rel.startswith(("\\\\", "\\")):
        fail(INVALID_PATH)                     # 拒绝对路径与 UNC
    if ".." in Path(rel).parts:
        fail(INVALID_PATH)                     # 显式拒绝穿越（resolve 之外的第二道保险）

    root = Path(get_config().get_project_root()).resolve()
    try:
        target = (root / rel).resolve()        # 消解 .. 与符号链接
    except OSError:
        fail(INVALID_PATH)
    if target != root and root not in target.parents:
        fail(PATH_OUTSIDE_ROOT)

    # 代码库根禁区；与可用性冲突时按 S6 降级（只读浏览场景可用性优先）
    cr = _code_root()
    if cr is None:
        pass                                   # 取不到代码根：不拦（只读浏览不应因此全废）
    elif _code_root_conflicts(root):
        if not _CODE_ROOT_WARNED:
            _CODE_ROOT_WARNED = True
            logger.warning(
                "[file_browse] project_root 落在代码库根内，已按 S6 跳过代码库根禁区"
                "（只读浏览场景可用性优先）"
            )
    elif target == cr or cr in target.parents:
        fail(PATH_FORBIDDEN)

    # 2026-10-13 小欧 - 修复 BUG-B: 不可再 .strip("./")。str.strip 从两端剥点，
    #   会把 '.env' 规范化成 'env'（磁盘上并不存在该文件），导致前端深链/J1 校验全拿错路径。
    #   Path(...).as_posix() 本身已是规范相对路径（'./a/b'→'a/b'、'.'→'.'），无需再处理。
    normalized = Path(rel).as_posix()
    return target, (normalized if normalized else ".")


# ══════════════════════════════════════════════════════════════════════
# 私有：扫描（唯一实现）
# ══════════════════════════════════════════════════════════════════════

def _preview_of(path: Path) -> str:
    """返回 text / image / none —— 后缀规则唯一真源（前端不自己判）。"""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTS:
        return "text"
    if suffix in IMAGE_EXTS:
        return "image"
    return "none"


def _fmt_time(ts: float) -> str:
    """时间戳格式化（单点，避免各处 strftime 写法漂移）。"""
    return time.strftime(_TIME_FMT, time.localtime(ts))


def _exists(p: Path) -> bool:
    """Path.exists() 的**安全版**。

    2026-10-13 小欧 - 真实缺陷(单测 b07/b06 抓出)：Path.exists() 内部 stat 遇
    超长路径 / 保留设备名会抛 OSError 而不是返回 False，此处一旦冒出去就是 500。
    另：Windows 上 NUL/CON/PRN 等保留设备名 exists() 恒为 True，须靠 is_dir/read 二次挡住。
    """
    try:
        return p.exists()
    except OSError:
        return False


def _encoding_candidates(head: bytes) -> Tuple[str, ...]:
    """按文件头 BOM 决定解码顺序。

    2026-10-13 小欧 - 单测 c02 抓出的真实缺陷：Windows 记事本「另存为」默认写 **UTF-16**，
    原先 utf-8/utf-8-sig/gbk 三级兜底全部失败 → 415，用户在记事本里存的文件读不出来。
    这里按 BOM 精确判定（utf-16/utf-32 的 BOM 互不相同），**没有 BOM 就不试 utf-16**，
    避免把任意二进制误解成 UTF-16 产出一堆乱码。
    """
    if head.startswith(b"\xff\xfe\x00\x00"):
        return ("utf-32",) + _ENCODINGS
    if head.startswith(b"\x00\x00\xfe\xff"):
        return ("utf-32",) + _ENCODINGS
    if head.startswith(b"\xff\xfe"):
        return ("utf-16",) + _ENCODINGS
    if head.startswith(b"\xfe\xff"):
        return ("utf-16",) + _ENCODINGS
    return _ENCODINGS


def _join_rel(rel: str, name: str) -> str:
    """拼相对路径 —— 全模块唯一的相对路径拼接点（DRY：杜绝三处分叉口径）。

    根层（rel 为 "." 或空）不产出 "./" 前缀：前端会把 key 拼进深链 URL，
    './backend' 会逐级累积成难排查的路径不一致（单测 e04 抓出）。
    不用 strip("./")/lstrip("./")：那会把 '.env' 削成 'env'（v3.3 记录的坑）。
    """
    base = rel.rstrip("/")
    return f"{base}/{name}" if base and base != "." else name


def _scan_dir(root: Path, target: Path, rel: str) -> Tuple[List[Dict[str, Any]], int]:
    """列一层目录，返回 (条目列表, 跳过条数)。条目已排序。

    ① 不跳过任何目录、不做类型过滤 —— 目录里有什么就返回什么（v3.4 裁定）
    ② os.scandir 而非 Path.iterdir：DirEntry 复用系统调用，is_dir 近乎免费
    ③ 每条一次带出 name/type/size/mtime（无 hover 单查端点）
    ④ 单条目异常（权限/坏链接）跳过并计数，不让一个坏条目拖垮整个目录
    ⑤ 排序：目录在前 + 名称不区分大小写升序
    ⑥ **解析后越出项目根的条目（符号链接）不返回** —— 设计 4.1.3/4.1.4 硬要求：
       树里出现一个点开必然 403 的死条目，比不列出来更糟（用户会反复点）。
       注意与 v3.4「不跳过任何目录」不冲突：这里跳过的**只有越界链接**，普通目录照列。
    """
    entries: List[Dict[str, Any]] = []
    skipped = 0
    try:
        it = os.scandir(target)
    except OSError as e:      # 目录不可读：返回空并留日志（不静默，否则前端误显"空目录"）
        logger.warning(f"[file_browse] 目录不可读已跳过 rel={rel}: {e}")
        return entries, 0
    with it:
        for de in it:
            try:
                is_dir = de.is_dir(follow_symlinks=True)
                st = de.stat(follow_symlinks=True)
            except OSError:    # ④ 权限不足/坏链接
                skipped += 1
                continue
            if _escapes_root(de.path, root):     # ⑥ 越界链接不列出
                skipped += 1
                continue
            entries.append({
                "key": _join_rel(rel, de.name),  # key 用相对路径，防同名撞车；口径统一走 _join_rel
                "name": de.name,
                "type": "dir" if is_dir else "file",
                "size": None if is_dir else st.st_size,
                "mtime": _fmt_time(st.st_mtime),
                "preview": _preview_of(Path(de.name)),
            })
    entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
    return entries, skipped


def _escapes_root(candidate: str, root: Path) -> bool:
    """该条目（可能是符号链接）解析后是否越出项目根。"""
    try:
        real = Path(os.path.realpath(candidate))
    except OSError:
        return True
    return real != root and root not in real.parents


class _ScanResult(NamedTuple):
    """一次递归的产出：节点 + 两个截断标志。

    2026-10-13 小欧 - 修复 BUG-A: 原先深度到顶时只标 truncated_child 而**不置 truncated**，
       前端据此以为树完整 → 永不触发按需补拉 → 第 6 层文件永远看不到。
       拆成两个独立标志，语义互不覆盖：
         truncated        节点数触顶（后面还有条目没返回）
         incomplete_depth 深度到顶（这层以下的目录未展开，前端需按需补拉）
    """
    nodes: List[Dict[str, Any]]
    truncated: bool
    incomplete_depth: bool
    skipped: int


def _walk(root: Path, target: Path, rel: str, depth: int, max_depth: int,
          budget: int) -> _ScanResult:
    """递归列目录。budget = 剩余节点额度，整棵树共享（M26/C2 节点闸门）。"""
    if budget <= 0:
        return _ScanResult([], True, False, 0)
    items, skipped = _scan_dir(root, target, rel)
    nodes: List[Dict[str, Any]] = []
    truncated = False
    incomplete_depth = False
    for e in items:
        if len(nodes) >= budget:            # 节点闸门：超限即停
            truncated = True
            break
        # 2026-10-13 小欧 - KISS/DRY: key 已由 _scan_dir 依 _join_rel 统一产出，
        #   原先这里又重算一遍（且与 _scan_dir 口径不一致 → 根层带 "./" 的坑）。
        #   _scan_dir 每次都新建 dict，可直接挂 children，无需拷贝。
        node = e
        if e["type"] == "dir":
            child_rel = _join_rel(rel, e["name"])
            if depth < max_depth:
                child = _walk(root, target / e["name"], child_rel, depth + 1,
                              max_depth, budget - len(nodes))
                node["children"] = child.nodes
                node["incomplete_child"] = child.truncated or child.incomplete_depth
                truncated = truncated or child.truncated
                incomplete_depth = incomplete_depth or child.incomplete_depth
                skipped += child.skipped
            else:
                node["children"] = None          # 深度上限：只出节点不展开
                node["incomplete_child"] = True  # 前端展开时按需补拉（驱动降级）
                incomplete_depth = True          # ← BUG-A 修复点
        nodes.append(node)
    return _ScanResult(nodes, truncated, incomplete_depth, skipped)


# ══════════════════════════════════════════════════════════════════════
# 对外 API
# ══════════════════════════════════════════════════════════════════════

def get_workspace_info() -> Dict[str, Any]:
    """项目根与授权目录，供前端做路径归一与 J1 校验。无 IO。"""
    cfg = get_config()
    root = Path(cfg.get_project_root()).resolve()
    return {
        "project_root": str(root),
        "allowed_dirs": list(cfg.get_allowed_dirs() or []),
        "code_root_blocked": _code_root_conflicts(root),
    }


def build_tree(rel_path: str = "", max_depth: int = MAX_TREE_DEPTH,
               max_nodes: int = MAX_TREE_NODES) -> Dict[str, Any]:
    """广度优先递归列目录树；深度/节点双闸门，超限置对应标志。

    单层列表亦由本函数承担（path 传某目录即等价于列该目录），无独立 list 端点（M26）。
    """
    # 2026-10-13 小欧 - 变量名纠错（单测 e06 抓出）: _resolve_within_root 返回的是
    #   **(target, normalized_rel)**，第一个值是起点目录本身而非 project_root。
    #   原先写作 `root, rel = ...` 再拼 `root / rel` → 路径被拼两次
    #   （proj/many/many 不存在 → 整棵树返回空）。此处按真实语义命名，杜绝再次踩坑。
    start_dir, rel = _resolve_within_root(rel_path)
    base_root = Path(get_config().get_project_root()).resolve()
    result = _walk(base_root, start_dir, rel, 1, max_depth, max_nodes)
    return {
        "path": rel,
        "project_root": str(base_root),
        "nodes": result.nodes,
        "truncated": result.truncated,               # 节点数触顶
        "incomplete_depth": result.incomplete_depth,  # 深度到顶（前端据此补拉）
        "skipped": result.skipped,                   # 本次扫描跳过的坏条目数
    }


def search_files(keyword: str, limit: int = 20,
                 max_depth: int = 4, max_nodes: int = 20000) -> Dict[str, Any]:
    """按文件名模糊搜索（输入框 @ 补全的数据源）。

    为什么需要它：北京老陈裁定「在输入框里手打 @文件名 也应能带内容」（文档[28] 决策）。
    纯前端过滤不可行 —— 树只在打开文件页时才进内存，用户没开过文件页就搜不到任何东西。

    扫描策略：深度受限的广度优先，每层先看文件再看目录（用户要找的通常就是文件），
    命中数达 limit 即停；节点总数超 max_nodes 也停 —— 与 tree 同一套双闸门思路，
    保证不会因为搜一个词把整个大仓库翻一遍。

    2026-10-13 小欧 - 越界符号链接与越界根路径一律不进结果（与 _scan_dir 同一口径）。
    """
    kw = (keyword or "").strip().lower()
    if not kw:      # 空关键词必然零命中，却要扫完整仓库 —— 直接短路。
                    # 路由层有 min_length=1 挡住，此处是防御（防止直接调函数时白扫一遍大仓库）。
        return {"keyword": keyword, "results": [], "scanned": 0,
                "hit_limit": False, "scanned_cap": False}
    base_root = Path(get_config().get_project_root()).resolve()
    start_dir, rel = _resolve_within_root("")
    results: List[Dict[str, Any]] = []
    scanned = 0
    hit_limit = False       # 结果数达 limit（可能还有更多，前端应提示"还有更多"）
    scanned_cap = False     # 扫描节点超 max_nodes（可能漏结果，前端应提示"结果不全"）

    # 广度优先：每层是 (目录, 相对路径)。深度用不上 —— _join_rel 已让每层自带完整 rel，
    # 故只按层数循环，不再维护 depth 变量（原变量从未被使用）。
    frontier: List[Tuple[Path, str]] = [(start_dir, rel)]
    for _ in range(max_depth):
        next_frontier: List[Tuple[Path, str]] = []
        for dir_path, dir_rel in frontier:
            # 每层先文件后目录：用户找的通常是文件，早命中早停。
            # (_scan_dir 已按"目录在前"排序，这里只把文件提到前面，不再二次全排序)
            items, _skipped = _scan_dir(base_root, dir_path, dir_rel)
            for e in sorted(items, key=lambda x: x["type"] == "dir"):
                scanned += 1
                if scanned > max_nodes:
                    scanned_cap = True
                    break
                if kw in e["name"].lower():
                    results.append({
                        "path": e["key"],            # _join_rel 口径，根层无 "./"
                        "name": e["name"],
                        "type": e["type"],
                        "preview": e["preview"],
                        "dir": "" if dir_rel == "." else dir_rel,
                    })
                    if len(results) >= limit:
                        hit_limit = True
                        break
                if e["type"] == "dir":
                    next_frontier.append((dir_path / e["name"], e["key"]))
            if hit_limit or scanned_cap:
                break
        if hit_limit or scanned_cap:
            break
        frontier = next_frontier

    return {
        "keyword": keyword,
        "results": results,
        "scanned": scanned,
        "hit_limit": hit_limit,
        "scanned_cap": scanned_cap,
    }


def sanitize_refs(refs: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """过滤输入框引用条目中的越界 path（chat 链路专用）。

    为什么在这里：判定「路径是否在项目根内」的知识只有本模块有（_resolve_within_root
    含代码库根禁区），若在 message_builder 里另写一份判定，必然与本模块分叉口径 ——
    实测正是这样分叉的（agent 层那份漏了代码库根禁区）。
    层次也正确：services/chat → app.file_browse 是同层横向依赖，反之 agent → file_browse
    会让更内层的模块依赖更外层。故校验前移到编排入口，**渲染期零 IO**。

    越界条目整条丢弃（含 content）：不给模型任何指向项目外的线索。
    无 path 的条目（纯 label 引用）不校验，放行。
    """
    if not refs:
        return []
    kept: List[Dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = (ref.get("path") or "").strip()
        if path:
            try:
                _resolve_within_root(path)
            except Exception as e:     # noqa: BLE001 —— fail() 抛的是业务错误类型，此处一律按越界丢弃
                logger.warning("[file_browse] 丢弃越界的引用路径 path=%s (%s)", path, e)
                continue
        kept.append(ref)
    return kept


def read_text_file(rel_path: str) -> Dict[str, Any]:
    """读 .txt / .md 正文：存在性 → 是目录 → 大小 → 类型 → 编码 五道闸门。

    2026-10-13 小欧 - KISS 修复: 原先类型闸门在前，`is_dir` 分支几乎不可达
    （目录通常无 .txt/.md 后缀，会先被类型闸门拦掉 415），属死代码。
    is_dir 提到类型判定之前：先说清"这是目录"，再说"类型不支持"。
    """
    target, rel = _resolve_within_root(rel_path)
    if not _exists(target):
        fail(NOT_FOUND)
    if target.is_dir():
        fail(INVALID_PATH, "该路径是目录，请使用目录树接口")
    if target.suffix.lower() not in TEXT_EXTS:
        fail(UNSUPPORTED_TYPE)
    try:
        size = target.stat().st_size
    except OSError:
        fail(NOT_FOUND)
    if size > MAX_TEXT_BYTES:
        fail(FILE_TOO_LARGE)

    content: Optional[str] = None
    used_enc = ""
    try:
        head = target.open("rb").read(4)
    except OSError:
        fail(NOT_FOUND)
    for enc in _encoding_candidates(head):    # 按 BOM 决定顺序，再逐个试
        try:
            # newline="" 禁掉通用换行转换 —— 2026-10-13 小欧 真实缺陷(单测 c09 抓出)：
            #   Path.read_text 默认 universal newlines，会把 '\r\n' 悄悄转成 '\n'，
            #   导致 .bat/.ps1/.cmd 脚本内容失真（用户看到与磁盘不一致，Agent 按错换行解析）。
            with target.open("r", encoding=enc, newline="") as fh:
                content = fh.read()
            used_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if content is None:
        fail(UNDECODABLE)

    logger.info(f"[file_browse] read_text rel={rel} bytes={size} enc={used_enc}")
    return {
        "path": rel,
        "name": target.name,
        "size": size,
        "content": content,
        "encoding": used_enc,
        "total_lines": content.count("\n") + 1 if content else 0,
    }


def read_image_file(rel_path: str, request: Request) -> Response:
    """读图片：类型 → 存在性 → 大小 → 条件请求 → FileResponse。

    Range/206/416 由 Starlette FileResponse 内置处理，本模块**不自研 Range**。
    """
    target, rel = _resolve_within_root(rel_path)
    if not _exists(target):
        fail(NOT_FOUND)
    if target.is_dir():
        fail(INVALID_PATH, "该路径是目录，请使用目录树接口")
    suffix = target.suffix.lower()
    if suffix not in IMAGE_EXTS:
        fail(UNSUPPORTED_TYPE)                  # raw 端点的白名单，不成万能下载口
    try:
        st = target.stat()
    except OSError:
        fail(NOT_FOUND)
    if st.st_size > MAX_IMAGE_BYTES:
        fail(IMAGE_TOO_LARGE)

    # 2026-10-13 小欧 - ETag 必须与 Starlette FileResponse 同算法(md5 of "mtime-size")，
    #   否则前端带回的 If-None-Match 永不命中，304 白做（框架升级时需回归本行）。
    etag = '"{}"'.format(
        hashlib.md5(f"{st.st_mtime}-{st.st_size}".encode(),
                    usedforsecurity=False).hexdigest()
    )
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304,
                        headers={"ETag": etag, "Cache-Control": "no-cache"})
    # no-cache 而非 no-store：允许条件请求省流量
    return FileResponse(
        target,
        media_type=IMAGE_MIME[suffix],
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(target.name)}",
        },
    )


def recent_files(session_id: str) -> List[Dict[str, Any]]:
    """本会话 Agent 最近读过的文件（树上的 ● 标记，T3）。

    数据源：chat_task_steps.step_json 里的 action.tools[].params.path。
    注意 path 是 LLM 原样给的、未做 abspath 归一（M6），故逐条 resolve 后判界。
    """
    from app.services.chat.workspace_service import session_exists   # 函数内 import 避免循环依赖
    with db.get_conn("chat") as conn:
        if not session_exists(conn, session_id):
            fail(SESSION_NOT_FOUND)
        rows = conn.execute(
            "SELECT step_json FROM chat_task_steps "
            "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, _RECENT_SCAN_LIMIT),
        ).fetchall()   # 命中 idx_steps_session(session_id, step_index) 复合索引

    root = Path(get_config().get_project_root()).resolve()
    seen: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        blob = row[0]
        try:
            step = json.loads(blob)
        except (TypeError, ValueError):
            continue
        if not isinstance(step, dict) or step.get("type") != "action":
            continue
        for t in (step.get("tools") or []):
            if not isinstance(t, dict):
                continue
            params = t.get("params") or {}
            raw = params.get("path") or t.get("target")
            if not raw or not isinstance(raw, str):
                continue
            # 2026-10-13 小欧 - 单测 j02 抓出的真 BUG（源自文档 4.1.7 的示例代码）：
            #   原写作 `Path(raw).resolve()`，而 LLM 给的绝大多数是**相对项目根**的路径，
            #   它会被解析到**进程 CWD**（backend/）而非项目根 → 判界失败整条丢弃
            #   → 「最近文件」面板对相对路径永远空白（只有绝对路径能用）。
            #   绝对路径仍要支持，故先归一到"相对项目根"再送 _resolve_within_root 收口
            #   （它只接受相对路径，绝对路径会判 INVALID_PATH；连带享受代码库根禁区与
            #   符号链接消解，前后端及 tree/search 口径完全一致）。
            try:
                cand = Path(raw)
                abs_path = cand.resolve() if cand.is_absolute() else (root / cand).resolve()
                rel_in = abs_path.relative_to(root).as_posix()   # 不在 root 下 → ValueError → 丢弃
            except (OSError, ValueError):
                continue
            try:
                _target, rel = _resolve_within_root(rel_in)
            except Exception:      # noqa: BLE001 —— 越界/禁区/非法一律跳过，不让脏数据中断整个面板
                continue
            key = str(abs_path)
            if key in seen:
                continue
            try:
                mtime = _fmt_time(abs_path.stat().st_mtime)
            except OSError:
                mtime = ""
            seen[key] = {
                "path": rel,                       # 复用唯一入口归一出的相对路径（口径与 tree 一致）
                "name": abs_path.name,
                "preview": _preview_of(abs_path),
                "last_seen_at": mtime,
            }
    return list(seen.values())[:_RECENT_KEEP]
