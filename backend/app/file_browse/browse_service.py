# -*- coding: utf-8 -*-
# 编辑历史: 2026-10-13 小欧 - 文档[28] v3.7: 文件浏览服务层(路径边界+递归扫描+读文本/图片+recent-files) — 小欧-2026-10-13
#   同批新增 _scan_dir / _walk / _resolve_within_root 三个私有函数：前两者是"唯一实现"
#   （防多处分叉），后者是"安全唯一入口"（五个对外端点全部经它）。
# 2026-10-13 小欧 - 文件名 service.py → browse_service.py：与既有 app/services/lifecycle/service.py
#   撞名，且项目主流命名为 *_service.py（8 处）。改名后语义也更精确（非通用 service，是浏览服务）。
# 2026-10-21 小杨 - 修文件浏览链路的判定与遍历缺陷：未知后缀文件实探改传完整路径（无后缀文件不再恒判不可预览）、
#   目录不参与文本实探（带 .md 后缀的目录曾被判为可预览文本）、目录环按 realpath+normcase 去重、
#   子级节点额度扣除目录自身占用（整树产出不再超 max_nodes）、带 BOM 的 UTF-16/UTF-32 文本按文本判定、
#   解码后含 NUL 的伪文本按二进制拒绝；另：文件当树改报 INVALID_PATH、不可读目录计入 skipped、
#   UNSUPPORTED_TYPE 文案与实际口径对齐、recent-files 的时间字段按真实语义命名为 mtime — 小杨-2026-10-21
# 2026-10-21 小欧 - 跳过数拆两类：skipped（读不了/越界/坏链接）与 skipped_cycles（**环检测**：
#   junction/链接绕回已展开目录）。原先混在一个计数里，前端只能说"无法读取"——实测 104 条里
#   绝大多数是环，说成读取失败是误导；两类分开后前端才能分别措辞 — 小欧-2026-10-21
# 2026-10-21 小欧 - read 的 total_lines 改 _count_lines：末尾换行不产生新行（编辑器口径），
#   原式 count("\n")+1 让 "a\r\nb\r\n" 算 3 行 → 行号指到不存在的空行，且与前端行号列不一致 — 小欧-2026-10-21
# 2026-10-21 小欧 - 树扫描提速（**不加任何节点限制**）：① BINARY_EXTS 明确二进制格式走后缀零 IO；
#   ② .map/.tsbuildinfo 等进文本后缀表；③ 剩余需实探的走 _probe_pool 并发探测
#   （实测 8.9 万节点单次 7.16s，其中 8KB 实探占约 7.5s 量级，scandir 遍历本身仅约 1s）— 小欧-2026-10-21
# 2026-10-22 小欧 - 外部只读（北京老陈批准）：新增 read_external_file（盘符绝对路径单文件只读文本，
#   复用 _probe_text/_read_truncated/_read_range 读管道 + 审计日志，不碰写/工具边界）；
#   新增 _is_abs_drive_path 判据（read_external_file 与 sanitize_refs 共用）；
#   sanitize_refs 对绝对盘符路径放行（用户主动引用的外部文件），相对路径校验口径不变 — 小欧-2026-10-22
"""文件浏览服务：项目根目录内的只读浏览。

对外五个函数：
    get_workspace_info / build_tree / read_text_file / read_image_file / recent_files

三条不可协商的边界（v3.4 北京老陈裁定）：
  1. 只读 —— 本模块无任何写路径
  2. 不出项目根目录 —— 唯一判定点在 _resolve_within_root
  3. 不跳过任何目录、不做文件类型黑名单 —— 目录里有什么就返回什么
"""

import codecs
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.responses import FileResponse

from app.config import get_config, get_code_root
from app.db import db
from app.logger import logger
from app.file_browse.errors import (
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
# 2026-10-21 小杨 - 文本文件真判定在 _preview_of 的实探（首 8KB 查 NUL）；
#   本表只承担"已知后缀零 IO 短路"（树扫描热路径免开文件），
#   覆盖常用文本/代码/配置后缀，不认识的落实探兜底。
TEXT_EXTS = {
    # 文本/文档
    ".txt", ".md", ".log", ".csv", ".tsv",
    # 前端
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".less", ".vue", ".svelte",
    # 脚本/后端语言
    ".py", ".pyw", ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".cs", ".php", ".rb", ".sh", ".bat", ".cmd", ".ps1", ".psm1",
    ".lua", ".r", ".dart", ".swift", ".kt", ".kts", ".sql", ".graphql", ".proto",
    # 配置/数据
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".xml", ".properties", ".gradle",
    # 2026-10-21 小欧 - 补两类"看着不像文本、实则是"的：
    #   .map = sourcemap（JSON 文本）；.tsbuildinfo = TypeScript 增量信息（JSON 文本）
    ".map", ".tsbuildinfo", ".plist", ".in", ".lock",
}
# 2026-10-21 小欧 - 明确的二进制格式（按后缀直接判 none，**零 IO**）：
#   这些格式实探必然读到 NUL → 判二进制，实探纯属浪费 IO。
#   实测：E:\test_dir 前 2 万项里 .docx/.pdf/.xlsx/.zip/.woff2/.pyc 等占实探量的 1/4。
BINARY_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
    ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar", ".tar", ".tgz", ".iso", ".cab",
    ".exe", ".dll", ".so", ".dylib", ".class", ".jar", ".war", ".ear", ".whl", ".egg",
    ".pyc", ".pyo", ".pyd", ".o", ".obj", ".a", ".lib",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv",
    ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb", ".dat", ".bin", ".img", ".iso_img",
}
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

# ══════════════════════════════════════════════════════════════════════
# ⚠⚠ 严禁新增任何"限制型"闸门（2026-10-21 北京老陈裁定，小欧 记录）
# ══════════════════════════════════════════════════════════════════════
# 禁止清单（不要再往里加任何一条）：
#   ✗ 扫描时间预算（SCAN_TIME_BUDGET / deadline / "超时就停"）—— 被回滚过一次，永不复活
#   ✗ 节点数截断（把 max_nodes 当硬闸门、"超限即停"式截断）
#   ✗ 深度硬闸（把 max_depth 当闸门砍子树）
#   ✗ 按目录数 / 按响应体积 / 按文件数的任何"防大仓"硬限制
# 理由：这些闸门把"**后端能给多少**"变成"**后端只给这么多**"，
#   结果是大仓用户直接用不了这个功能 —— 要限量的是**首屏取多少**（前端按需拉取），
#   不是**后端能给多少**（后端要多少给多少）。
# 正确做法（已落地）：
#   · 前端首屏只取**前 3 层**（max_depth=3），点开更深目录时用已有的 loadDir 补拉；
#   · 后端路由层 max_nodes **不设上界**（只 ge=1），调用方要多少给多少；
#   · 慢的根因从**成本**上治（后缀零 IO 判定 + 实探并发 + gzip level 1 + 环检测键零 IO），
#     不用"砍数据"来治。
# 本行注释是**红线**：任何人想加上面那些闸门，先看这里，再看北京老陈的裁定。
MAX_TREE_DEPTH = 10                    # 2026-10-21 小杨 - 深度上限 5→10（性能实测达标后放宽）
MAX_TREE_NODES = 100000                # 2026-10-21 小杨 - 节点上限 5000→100000；**这是默认值，不是闸门**（路由层不设上界）

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


def _is_abs_drive_path(p: str) -> bool:
    """盘符绝对路径（C:\\x / D:/x）—— 外部文件引用判据；UNC/斜杠路径/相对路径一律不算。

    2026-10-22 小欧 - 外部只读（read_external_file）与引用放行（sanitize_refs）两处共用，
    避免口径漂移。— 小欧-2026-10-22
    """
    if p.startswith(("\\\\", "\\", "/")):
        return False
    return bool(Path(p).is_absolute())


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

# 2026-10-21 小杨 - 探测热路径缓存：
#   _preview_of / recent_files / read_text_file 对 unknown/无后缀文件各探一次
#   （.git/objects 等大平目录 = 数万次 open），且 read_text_file 重复扫已在树
#   扫描探过的文件。收敛为单点 _probe_text（DRY）+ (路径, mtime) 缓存，
#   mtime 变即失效，打不开(OSError)不缓存（transient 状态不入账）。
_PREVIEW_CACHE: Dict[str, Tuple[float, str]] = {}   # path -> (mtime, 't'|'f')
_PREVIEW_CACHE_MAX = 100000

# 2026-10-21 小欧 - 实探并发池（模块级单例，懒建线程）：
#   类型探测是树扫描耗时大头（单文件 0.36ms，串行 8.9 万节点里 24% 需实探 ≈ 7.5s）。
#   IO 型操作（open+read 8KB）并发收益直接；线程数固定 8，避免大目录把磁盘打满。
_probe_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="browse-probe")


_TEXT_BOMS = (b"\x00\x00\xfe\xff", b"\xff\xfe\x00\x00",
              b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")


def _probe_text(path: Path) -> Optional[bool]:
    """首 8KB 查 NUL 空字节判定文本/二进制 —— 全模块唯一实探点。

    返回 None=打不开（OSError）；True=无 NUL（文本）；False=含 NUL（二进制）。
    2026-10-21 小杨 - 带文本 BOM 的文件（记事本 UTF-16/UTF-32）首字节必含 NUL，
    只看 NUL 会把 UTF-16 误判二进制。BOM 是比 NUL 更强的文本证据，先判 BOM 再走 NUL。
    语义与 git/VSCode 同款廉价判定；解码与 2MB 截断仍由 read_text_file 兜底。
    """
    key = str(path)
    if key in _PREVIEW_CACHE:
        mtime, verdict = _PREVIEW_CACHE[key]
        try:
            st = path.stat()
        except OSError:
            return None
        if st.st_mtime == mtime:
            return verdict == "t"
        del _PREVIEW_CACHE[key]
    try:
        with open(path, "rb") as f:
            head = f.read(8192)
            st = os.fstat(f.fileno())
    except OSError:
        return None
    verdict = "t" if (head.startswith(_TEXT_BOMS) or b"\x00" not in head) else "f"
    if len(_PREVIEW_CACHE) >= _PREVIEW_CACHE_MAX:
        _PREVIEW_CACHE.clear()
    _PREVIEW_CACHE[key] = (st.st_mtime, verdict)
    return verdict == "t"


def _preview_by_suffix(path: Path) -> Optional[str]:
    """**只按后缀**判定可预览性：text / image / None(=需实探)。

    2026-10-21 小欧 - 拆出后缀判定层：让树扫描能**零 IO** 处理绝大多数条目，
      只把"后缀判不了"的交给实探（并发，见 _scan_dir）。"""
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTS:
        return "text"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in BINARY_EXTS:
        return "none"          # 明确的二进制格式：实探必然判二进制，纯浪费 IO
    return None


def _preview_of(path: Path) -> str:
    """返回 text / image / none — **后缀规则唯一真源**（前端不自己判）。

    2026-10-21 小杨 - 文本文件=能解码的：已知文本/图片后缀直接短路（零 IO，树扫描热路径），
      未知后缀（含 Dockerfile、LICENSE 等无后缀文件）实探——走唯一探测点 _probe_text（首 8KB 看 NUL），
      解码/2MB 截断仍由 /files/read 的解码链兜底。
    2026-10-21 小欧 - 二进制格式后缀进 BINARY_EXTS 直接判 none（零 IO）。
    """
    by_suffix = _preview_by_suffix(path)
    if by_suffix is not None:
        return by_suffix
    r = _probe_text(path)
    return "text" if r is True else "none"



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


def _scan_dir(root: Path, target: Path, rel: str) -> Tuple[List[Dict[str, Any]], int, Dict[str, Tuple]]:
    """列一层目录，返回 (条目列表, 跳过条数, 目录名 → 环检测键)。

    环检测键是 **inode 键**（见 _dir_key），不是 realpath 键。

    ① 不跳过任何目录、不做类型过滤 —— 目录里有什么就返回什么（v3.4 裁定）
    ② os.scandir 而非 Path.iterdir：DirEntry 复用系统调用，is_dir 近乎免费
    ③ 每条一次带出 name/type/size/mtime（无 hover 单查端点）
    ④ 单条目异常（权限/坏链接）跳过并计数，不让一个坏条目拖垮整个目录
    ⑤ 排序：目录在前 + 名称不区分大小写升序
    ⑥ **解析后越出项目根的条目（符号链接）不返回** —— 设计 4.1.3/4.1.4 硬要求：
       树里出现一个点开必然 403 的死条目，比不列出来更糟（用户会反复点）。
       注意与 v3.4「不跳过任何目录」不冲突：这里跳过的**只有越界链接**，普通目录照列。
    ⑦ 文本实探只对文件做，且必须传完整路径（2026-10-21 小杨 - 修复：
       原实现传 Path(de.name) 相对进程 CWD，Dockerfile/LICENSE 等无后缀文件恒探失败；
       目录也不该被探测——dir.md 这类带文本后缀的目录曾被误判为可预览文本）。
    ⑧ 2026-10-21 小欧 - 实探**并发化**：类型探测是树扫描的耗时大头
       （实测 E:\test_dir：scandir 遍历 2 万项只要 0.21s，而 8KB 实探 4886 个要 1.08s，
       单文件 0.36ms —— 全量 8.9 万节点里 24% 需实探，折算约 7.5s，占总耗时 7.16s 的绝大部分）。
       故：后缀能判的直接判（零 IO），需实探的**批量并发**探（IO 并行）。
    ⑨ 2026-10-21 小欧 - **目录身份用 (st_dev, st_ino)**（环检测主键，零额外 IO）：
       realpath 在 Windows 上要查链接链（0.14ms/目录），abspath 认不出 junction
       （junction 指向祖先时字面路径不同 → 环检不出，实测 test_r03 红）；
       inode 判定两者兼顾：junction/符号链接/硬链接都指向同一 inode → 必被识别。
       st_ino 恒 0 的盘（部分网络盘）退化为路径键兜底（此时 junction 环可能漏检，已知取舍）。
    """
    entries: List[Dict[str, Any]] = []
    skipped = 0
    pending: List[Tuple[int, Path]] = []      # (entries 下标, 绝对路径) —— 待实探
    dir_ids: Dict[str, Tuple] = {}           # 目录名 → 环检测键（_dir_key）
    try:
        it = os.scandir(target)
    except OSError as e:      # 目录不可读：返回空并计数（不静默，否则前端误显"空目录"）
        logger.warning(f"[file_browse] 目录不可读已跳过 rel={rel}: {e}")
        return entries, 1, dir_ids
    with it:
        for de in it:
            try:
                is_dir = de.is_dir(follow_symlinks=True)
                st = de.stat(follow_symlinks=True)
            except OSError:    # ④ 权限不足/坏链接
                skipped += 1
                continue
            # ⑥ 越界链接不列出。2026-10-21 小杨 - 性能修复：只有**符号链接**才可能越出根，
            #    普通条目不再调 realpath（原实现每条目一次 resolve，5 万条=几分钟级挂死）
            if de.is_symlink():
                if _escapes_root(de.path, root):
                    skipped += 1
                    continue
            preview = "none"
            if not is_dir:
                p = Path(de.path)
                by_suffix = _preview_by_suffix(p)
                if by_suffix is not None:
                    preview = by_suffix
                else:
                    pending.append((len(entries), p))   # ⑧ 后缀判不了 → 稍后并发实探
            else:
                # ⑨ 目录身份（环检测键）：De.stat(follow_symlinks=True) 对 **Windows junction
                #   不跟随**（实测返回 st_ino=0 → 键退化 → 环检不出，test_r03 红），
                #   故 stat 退化时补一次 os.stat（会跟随 junction），成本只落在异常项上。
                _st = st
                if getattr(st, "st_ino", 0) <= 0:
                    try:
                        _st = os.stat(de.path)
                    except OSError:
                        _st = st
                dir_ids[de.name] = _dir_key(Path(de.path), _st)
            entries.append({
                "key": _join_rel(rel, de.name),  # key 用相对路径，防同名撞车；口径统一走 _join_rel
                "name": de.name,
                "type": "dir" if is_dir else "file",
                "size": None if is_dir else st.st_size,
                "mtime": _fmt_time(st.st_mtime),
                # ⑦ 目录不探测；文件传绝对路径（de.path），不得相对 CWD
                "preview": preview,
            })
    if pending:
        verdicts = list(_probe_pool.map(_probe_text, [p for _, p in pending]))
        for (idx, _p), v in zip(pending, verdicts):
            entries[idx]["preview"] = "text" if v is True else "none"
    entries.sort(key=lambda e: (e["type"] != "dir", e["name"].lower()))
    return entries, skipped, dir_ids


def _escapes_root(candidate: str, root: Path) -> bool:
    """该条目（可能是符号链接）解析后是否越出项目根。"""
    try:
        real = Path(os.path.realpath(candidate))
    except OSError:
        return True
    return real != root and root not in real.parents


def _dir_key(path: Path, st: Optional[os.stat_result] = None) -> Tuple:
    """目录身份键（环检测用）—— **inode 优先**，退化路径键。

    2026-10-21 小杨 - 原始需求：junction/符号链接指向祖先时 realpath 会回到已访问目录，
      不设 visited 会无限递归（实测 loop/loop/loop）。
    2026-10-21 小欧 - 键从 realpath 改成 inode：
      realpath 在 Windows 上要查链接链（实测 0.14ms/目录，4450 目录就 0.64s，占扫描耗时一半）；
      而纯路径键（abspath）认不出 junction（junction 指向祖先时字面路径不同 → 环检不出，
      实测 test_r03 红）。inode 两者兼顾：junction/符号链接/硬链接都指向同一 inode → 必被识别，
      且 st 在 _scan_dir 里**已经取过**（de.stat(follow_symlinks=True)）→ 零额外 IO。
      st_ino 恒 0 的盘（部分网络盘）退化为路径键（此时 junction 环可能漏检，已知取舍）。
    """
    try:
        if st is None:
            st = path.stat()
        if st.st_ino > 0:
            return ("ino", st.st_dev, st.st_ino)
    except OSError:
        pass
    try:
        return ("path", os.path.normcase(os.path.abspath(str(path))))
    except OSError:
        return ("path", str(path))


class _ScanResult(NamedTuple):
    """一次递归的产出：节点 + 两个截断标志。

    2026-10-13 小欧 - 修复 BUG-A: 原先深度到顶时只标 truncated_child 而**不置 truncated**，
       前端据此以为树完整 → 永不触发按需补拉 → 第 6 层文件永远看不到。
       拆成两个独立标志，语义互不覆盖：
         truncated        节点数触顶（后面还有条目没返回）
         incomplete_depth 深度到顶（这层以下的目录未展开，前端需按需补拉）

    2026-10-21 小欧 - 跳过数拆两类（原先混在一个计数里，前端只能笼统说"无法读取"，
       实测 104 条里绝大多数是**环检测**（junction/链接绕回已展开目录），说成读取失败是误导）：
         skipped         读不了/越界/坏链接的条目数（真的没取到）
         skipped_cycles  环检测拦下的条目数（链接指回已展开目录，防无限递归）
    """
    nodes: List[Dict[str, Any]]
    truncated: bool
    incomplete_depth: bool
    skipped: int
    skipped_cycles: int


def _walk(root: Path, target: Path, rel: str, depth: int, max_depth: int,
          budget: int, visited: set) -> _ScanResult:
    """递归列目录。budget = 剩余节点额度，整棵树共享（M26/C2 节点闸门）。

    2026-10-21 小杨 - 修复预算穿透：原先外层闸门只数
    `len(nodes)`（本层已入库条目），递归 child 内部消费的节点数不回收，
    本层每个目录的 child 都能各自再烧一遍 budget → 总产出上界 K×budget，
    max_nodes 阈值失真、truncated 标志随之漂移。改为消费记账：本层维护
    used（已入库条目 + 归还的 child 消费量），判闸与递归还额都走 used，
    全树产出严格 ≤ budget。child 额度须扣掉本目录自身占用的 1 格
    （budget - used - 1）：原式 budget - used 使 child 可拿满剩余额度，
    加上本目录本身后整树必然超 1（实测 max_nodes=2 出 3 个节点）。

    2026-10-21 小杨 - 环检测：visited 存已展开目录的
    realpath+normcase，junction/符号链接绕回祖先时整条目跳过并计 skipped。

    2026-10-21 小欧 - 环检测单独计 skipped_cycles（与"读不了"分计，语义不再混）。
    """
    if budget <= 0:
        return _ScanResult([], True, False, 0, 0)
    items, skipped, dir_ids = _scan_dir(root, target, rel)
    nodes: List[Dict[str, Any]] = []
    used = 0
    truncated = False
    incomplete_depth = False
    skipped_cycles = 0            # 2026-10-21 小欧 - 环检测单独计数（与"读不了"分开）
    for e in items:
        if used >= budget:                  # 节点闸门：额度耗尽即停
            truncated = True
            break
        # 2026-10-13 小欧 - KISS/DRY: key 已由 _scan_dir 依 _join_rel 统一产出，
        #   原先这里又重算一遍（且与 _scan_dir 口径不一致 → 根层带 "./" 的坑）。
        #   _scan_dir 每次都新建 dict，可直接挂 children，无需拷贝。
        node = e
        if e["type"] == "dir":
            child_dir = target / e["name"]
            cid = dir_ids.get(e["name"]) or _dir_key(child_dir)   # inode 键（junction 也认得出）
            if cid in visited:                        # 链回已展开目录：跳过防环
                skipped_cycles += 1                  # 2026-10-21 小欧 - 与"读不了"分计
                continue
            visited.add(cid)
            child_rel = _join_rel(rel, e["name"])
            if depth < max_depth:
                child = _walk(root, child_dir, child_rel, depth + 1,
                              max_depth, budget - used - 1, visited)
                node["children"] = child.nodes
                node["incomplete_child"] = child.truncated or child.incomplete_depth
                truncated = truncated or child.truncated
                incomplete_depth = incomplete_depth or child.incomplete_depth
                skipped += child.skipped
                skipped_cycles += child.skipped_cycles
                used += len(child.nodes)    # 2026-10-21 小杨 - child 消费量记回本层额度
            else:
                node["children"] = None          # 深度上限：只出节点不展开
                node["incomplete_child"] = True  # 前端展开时按需补拉（驱动降级）
                incomplete_depth = True          # ← BUG-A 修复点
        used += 1
        nodes.append(node)
    return _ScanResult(nodes, truncated, incomplete_depth, skipped, skipped_cycles)


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
    if not _exists(start_dir):
        fail(NOT_FOUND)
    if not start_dir.is_dir():                # 2026-10-21 小杨 - 文件当树曾返回 200 空树，误导前端
        fail(INVALID_PATH, "该路径不是目录，请使用文本/图片接口")
    base_root = Path(get_config().get_project_root()).resolve()
    visited = {_dir_key(start_dir)}
    result = _walk(base_root, start_dir, rel, 1, max_depth, max_nodes, visited)
    return {
        "path": rel,
        "project_root": str(base_root),
        "nodes": result.nodes,
        "truncated": result.truncated,               # 节点数触顶
        "incomplete_depth": result.incomplete_depth,  # 深度到顶（前端据此补拉）
        "skipped": result.skipped,                   # 本次扫描跳过的坏条目数（读不了/越界）
        # 2026-10-21 小欧 - 环检测单独计数（junction/链接绕回已展开目录），与 skipped 语义分开
        "skipped_cycles": result.skipped_cycles,
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
    visited = {_dir_key(start_dir)}     # 2026-10-21 小杨 - 环检测：junction/符号链接只展开一次
    for _ in range(max_depth):
        next_frontier: List[Tuple[Path, str]] = []
        for dir_path, dir_rel in frontier:
            # 每层先文件后目录：用户找的通常是文件，早命中早停。
            # (_scan_dir 已按"目录在前"排序，这里只把文件提到前面，不再二次全排序)
            items, _skipped, _dir_ids = _scan_dir(base_root, dir_path, dir_rel)
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
                    cid = _dir_key(dir_path / e["name"])
                    if cid is not None and cid in visited:
                        continue
                    if cid is not None:
                        visited.add(cid)
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
            # 2026-10-22 小欧 - 绝对盘符路径 = 外部文件引用（用户主动引用；存在性由前端
            #   预览时经 read_external_file 校验，此处只做"是否外部"的放行判定，不重复 IO）。
            #   相对路径仍走 _resolve_within_root（项目内口径不变）— 小欧-2026-10-22
            if not _is_abs_drive_path(path):
                try:
                    _resolve_within_root(path)
                except Exception as e:     # noqa: BLE001 —— fail() 抛的是业务错误类型，此处一律按越界丢弃
                    logger.warning("[file_browse] 丢弃越界的引用路径 path=%s (%s)", path, e)
                    continue
        kept.append(ref)
    return kept


def _count_content_lines(content: str) -> int:
    """行数：末尾换行不产生新行（编辑器口径，与前端行号列同源）。

    2026-10-21 小欧 - 原式 count("\\n")+1 对 "a\\r\\nb\\r\\n" 得 3（实际 2 行），
    行号会指到不存在的空行。"""
    if not content:
        return 0
    n = content.count("\n")
    return n if content.endswith("\n") else n + 1


def _count_file_lines(target: Path) -> int:
    """流式数**文件**行数（内存恒定，不把文件读进来）。末尾无换行时多算一行。

    与 _count_content_lines（数已读内容的行数）分清：前者 IO、后者纯字符串。
    """
    n = 0
    last = b""
    try:
        with target.open("rb") as fh:
            while True:
                chunk = fh.read(1 << 20)
                if not chunk:
                    break
                n += chunk.count(b"\n")
                last = chunk[-1:]
    except OSError:
        return 0
    if last and last != b"\n":
        n += 1
    return n


def _read_lines_range(
    target: Path, enc: str, offset: int, limit: int, errors: str = "strict"
) -> Tuple[str, int, int]:
    """流式读第 [offset, offset+limit) 行（1-based）→ (文本, 读到的行数, 原始字节数)。

    2026-10-21 小欧 - 大文件翻页：整文件进内存是 OOM 源头（大仓 500MB 文件直接炸），
    故按行区间**流式**读：内存只装要的那几行，与文件总大小无关。
    2026-10-21 小欧 - 逐行迭代用 splitlines（不用"buf = buf[i+1:]"反复切片 → O(n²)）。
    """
    dec = codecs.getincrementaldecoder(enc)(errors=errors)
    out: List[str] = []
    raw_bytes = 0
    try:
        with target.open("rb") as fh:
            line_no = 0
            pending = b""
            while True:
                chunk = fh.read(1 << 16)
                if not chunk:
                    break
                pending += chunk
                lines = pending.split(b"\n")
                pending = lines.pop()          # 最后一段可能是半行，留到下一轮
                for raw in lines:
                    line_no += 1
                    if line_no < offset:
                        continue
                    raw_bytes += len(raw) + 1
                    out.append(dec.decode(raw + b"\n", False))
                    if len(out) >= limit:
                        return "".join(out), len(out), raw_bytes
            if pending:                        # 末行无换行
                line_no += 1
                if line_no >= offset and len(out) < limit:
                    raw_bytes += len(pending)
                    out.append(dec.decode(pending, True))
    except OSError:
        return "", 0, 0
    return "".join(out), len(out), raw_bytes


def _read_file_body(
    target: Path,
    rel: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    nontext_msg: Optional[str] = None,
) -> Dict[str, Any]:
    """文本正文读取公共段（根内 / 外部只读共用）：NUL 实探 → 大小 → 编码闸门 → 区间分派。

    2026-10-22 小欧 - 三堂会审抽出的共用段：read_text_file 与 read_external_file 此前
    各写一遍 exists/probe/stat/head/区间分派（约 20 行），闸门语义改动必漏一处。
    唯一保留差异：非文本文案（外部只读需说明"仅支持文本预览"）。
    路径解析（根内 _resolve_within_root / 外部盘符判定）与类型闸门留在调用方。— 小欧-2026-10-22
    """
    probe = _probe_text(target)
    if probe is None:
        fail(NOT_FOUND)
    if probe is False:
        fail(UNSUPPORTED_TYPE, nontext_msg)
    try:
        st = target.stat()
    except OSError:
        fail(NOT_FOUND)
    try:
        with target.open("rb") as fh:
            head = fh.read(4)
    except OSError:
        fail(NOT_FOUND)

    # 2026-10-21 小欧 - **行号区间翻页**（与大文件截断共存）：
    #   默认路径只读前 MAX_TEXT_BYTES(2MB) → 2MB 之后的内容拿不到（半个死路）；
    #   带 offset/limit 时按行区间**流式**读：内存恒定，可一路翻到文件末尾。
    if offset is not None or limit is not None:
        return _read_range(target, rel, st, head, int(offset or 1), int(limit or 2000))
    return _read_truncated(target, rel, st, head)


def read_external_file(
    abs_path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """读项目根**外**的文本文件（只读，用户主动点击的外部文件链接）。

    2026-10-22 小欧 - 需求：会话里 Agent 引用的文件可能不在当前项目根内。
    安全模型：只读单文件；绝对盘符路径必须 is_file；类型/大小/编码闸门与根内共用
    _read_file_body（闸门改动只改一处）；写审计日志。
    不触碰任何写/工具边界，不改 project_root 语义。
    第一版只支持文本（非文本即拒），外部图片预览留待后续。— 小欧-2026-10-22
    """
    raw = (abs_path or "").strip()
    if not _is_abs_drive_path(raw):
        fail(INVALID_PATH)                     # 只接受盘符绝对路径；相对/UNC/斜杠路径拒绝
    target = Path(raw)
    if not _exists(target):
        fail(NOT_FOUND)
    if not target.is_file():
        fail(INVALID_PATH, "该路径不是文件")

    # 审计：外部读取必须留痕（根内读只记相对路径，绝对路径读取单独记录）
    logger.info(f"[file_browse] external read abs={raw}")

    return _read_file_body(target, raw, offset, limit, "外部文件仅支持文本预览")


def read_text_file(
    rel_path: str,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """读任意文本正文：存在性 → 是目录 → NUL 实探 → 大小 → 编码 五道闸门。

    2026-10-13 小欧 - KISS 修复: 原先类型闸门在前，`is_dir` 分支几乎不可达
    （目录通常无 .txt/.md 后缀，会先被类型闸门拦掉 415），属死代码。
    is_dir 提到类型判定之前：先说清"这是目录"，再说"类型不支持"。
    2026-10-21 小杨 - 类型闸从后缀白名单改为首 8KB NUL 实探
    （文本=能解码的；代码/无后缀文件全部可读），二进制拒绝语义保持。
    2026-10-21 小欧 - **超限不再报错，改为截断读取**（北京老陈：大文件也要能读出来，
      直接 413 是死路）：超 MAX_TEXT_BYTES 只读前 2MB 并在返回值里带
      truncated/total_size，如实告知"只加载了前 N"。编码用**增量解码器**，
      尾部半个多字节字符不会炸（不静默丢字符）。
    """
    target, rel = _resolve_within_root(rel_path)
    if not _exists(target):
        fail(NOT_FOUND)
    if target.is_dir():
        fail(INVALID_PATH, "该路径是目录，请使用目录树接口")
    return _read_file_body(target, rel, offset, limit)


def _read_result(target: Path, rel: str, st: os.stat_result, content: str, enc: str) -> Dict[str, Any]:
    """read 两条路径的**公共字段**（避免同一组字段手写两遍 → 改一处漏一处）。"""
    return {
        "path": rel,
        "name": target.name,
        "size": st.st_size,
        "content": content,
        "encoding": enc,
        "mtime": _fmt_time(st.st_mtime),
    }


def _read_range(
    target: Path, rel: str, st: os.stat_result, head: bytes, offset: int, limit: int
) -> Dict[str, Any]:
    """按行区间读（翻页）：内存恒定，可一路翻到文件末尾。

    2026-10-21 小欧 - 与 _read_truncated 分开（SRP）：一条读"开头截断"，一条读"指定行段"。
    """
    off = max(1, offset)
    lim = max(1, min(limit, 5000))
    text = ""
    got = 0
    raw_bytes = 0
    used_enc = ""
    for enc in _encoding_candidates(head):
        try:
            text, got, raw_bytes = _read_lines_range(target, enc, off, lim, "strict")
            used_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if not used_enc:      # 所有编码严格解都失败 → 用首选编码替换符兜底
        used_enc = _encoding_candidates(head)[0]
        text, got, raw_bytes = _read_lines_range(target, used_enc, off, lim, "replace")
    total = _count_file_lines(target)
    logger.info(
        f"[file_browse] read_text range rel={rel} bytes={st.st_size} enc={used_enc} "
        f"offset={off} limit={lim} got={got} total={total}"
    )
    out = _read_result(target, rel, st, text, used_enc)
    out.update({
        "total_lines": total,
        "truncated": False,
        "total_size": st.st_size,
        # 2026-10-21 小欧 - loaded_size 用**原始字节数**（与 _read_truncated 口径一致，
        #   不用 len(text.encode()) —— 那是编码后长度，与磁盘字节数不是一个口径）
        "loaded_size": raw_bytes,
        # 2026-10-21 小欧 - 区间信息：前端据此续读下一段（翻页）
        "start_line": off,
        "end_line": off + got - 1 if got else off - 1,
        "returned_lines": got,
        "loaded_lines": got,
    })
    return out


def _read_truncated(
    target: Path, rel: str, st: os.stat_result, head: bytes
) -> Dict[str, Any]:
    """读文件开头：超 MAX_TEXT_BYTES 截断（不报错），如实告知截了多少。

    2026-10-21 小欧 - 超限不再报错，改为截断读取（北京老陈：大文件也要能读出来，
      直接 413 是死路）：超限只读前 2MB 并带 truncated/total_size/loaded_size。
      编码用**增量解码器**，尾部半个多字节字符不会炸（不静默丢字符）。
    """
    content: Optional[str] = None
    used_enc = ""
    raw = b""
    for enc in _encoding_candidates(head):    # 按 BOM 决定顺序，再逐个试
        try:
            # 二进制读 + 增量解码：① 天然保留 \r\n（不再需要 newline=""），
            #   ② 截断时尾部半个多字节字符由增量解码器留在缓冲区，不会炸也不丢字符。
            with target.open("rb") as fh:
                raw = fh.read(MAX_TEXT_BYTES)
            truncated = st.st_size > len(raw)
            dec = codecs.getincrementaldecoder(enc)(errors="strict")
            content = dec.decode(raw, False)
            used_enc = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if content is None:
        fail(UNDECODABLE)
    # 2026-10-21 小杨 - 修复：首 8KB 之外才出现 NUL 的"伪文本"
    #   （前段纯 ASCII、后段二进制）能通过探测，却会在预览里渲染成空白/乱码；
    #   解码后已持全文，O(n) 扫描零额外 IO，作为最后一道二进制闸门。
    if "\x00" in content:
        fail(UNSUPPORTED_TYPE)

    logger.info(f"[file_browse] read_text rel={rel} bytes={st.st_size} enc={used_enc}")
    loaded_lines = _count_content_lines(content)
    out = _read_result(target, rel, st, content, used_enc)
    out.update({
        # 2026-10-21 小欧 - 行数口径: 末尾换行不产生新行（编辑器口径）。
        #   原式 count("\n")+1 让 "a\r\nb\r\n" 算出 3 行 → 行号指到不存在的空行，
        #   且与前端行号列（已同步去掉末段空串）不一致。
        # 2026-10-21 小欧 - 默认路径**不扫全文件数行**（那是一次 O(文件) 的额外扫描，
        #   500MB 大仓每次切文件都白扫 0.5s）→ total_lines 即本次已加载行数；
        #   真实总行数由**区间读**给出（用户点「加载后续内容」时才算）。
        "total_lines": loaded_lines,
        "loaded_lines": loaded_lines,
        "start_line": 1,
        "end_line": loaded_lines,
        "returned_lines": loaded_lines,
        # 2026-10-21 小欧 - 截断如实告知：truncated=True 时 content 只是前 MAX_TEXT_BYTES，
        #   total_size 是文件真实字节数，loaded_size 是本次实际读到的字节数
        #   （前端提示用 loaded_size，否则会写成"共 8.4MB，已加载前 8.4MB"这种自相矛盾的话）。
        "truncated": st.st_size > len(raw),
        "total_size": st.st_size,
        "loaded_size": len(raw),
    })
    return out


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
    """本会话 Agent 最近读过的文件（树上的 ● 标记，T3；FT1 追加 ops 操作徽标）。

    数据源：chat_task_steps.step_json 里的 action.tools[].params.path。
    注意 path 是 LLM 原样给的、未做 abspath 归一（M6），故逐条 resolve 后判界。
    返回项含 ops: 该 path 在扫描窗口内被哪些工具动过（tool 名去重、字母序；FT1）。
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
    # 2026-10-21 小杨 - ops 聚合：该 path 在最近窗口内被哪些工具动过（tool 名去重）
    ops_by_path: Dict[str, set] = {}
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
            # 2026-10-21 小杨 - ops 累加必须在"去重 continue"之前 ——
            #   否则同一路径的其它工具操作（同一 path 的第二次/第三次动作）会被 continue 吃掉而漏计。
            #   tool 名取 tools 元素的 "tool" 字段（action_step.py:5：tools 元素含 tool/target/params）。
            ops_by_path.setdefault(key, set()).add(str(t.get("tool") or "unknown"))
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
                # 2026-10-21 小杨 - 修复：该值一直是文件系统 mtime，
                #   旧名 last_seen_at 会让前端误当"最近访问时间"。按真实语义命名。
                "mtime": mtime,
            }
    # 2026-10-21 小杨 - ops 统一在循环结束后回填：seen[key] 建在"首次出现"处（最新一次动作），
    #   而 ops_by_path 在其后的旧记录里仍在累加；若在构造时快照 sorted(ops_by_path[key])，
    #   只会拿到第一个动作的 op（漏计）→ 故此处回填，保证是全集。
    for _k, _v in seen.items():
        _v["ops"] = sorted(ops_by_path.get(_k, set()))
    return list(seen.values())[:_RECENT_KEEP]
