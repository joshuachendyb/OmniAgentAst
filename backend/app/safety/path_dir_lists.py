# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-19 小欧 - 新建: 目录数组清单。承载三个一维数组(禁区-系统/禁区-非系统/白名单),
#   并成为全系统唯一的目录取值口与归属判定口 —— 原先散落在 path_env /
#   path_check_common / path_classify_category / delete_path_check 的取值与判定逻辑全部并入本文件,
#   原函数随之删除; 名单项只要 path + label 两个字段, 覆盖范围靠"命中自身"与"命中最深条目"判定;
#   名单经 ContextVar 按 loop 作用域传递, loop 内构建一次, 严禁二次构建;
#   同一份结构原样序列化落库(chat_tasks.path_scope_snapshot)
# 2026-10-19 小欧 - 清理死代码: 删 _get_current_lists(定义后全库零调用, 读取一律走 _current_or_build;
#   其 docstring 还引用了不存在的 get_or_build_directory_lists(), 一并消除)。判定逻辑零变更。
# 2026-10-19 小欧 - 格式统一收口: 名单构建(_complete)与查询原本各写一遍 realpath, 口径有
#   分裂隐患; 抽单一实现两侧共用, 术语由"归一化"改"格式化"(把 \\?\、/、~、尾分隔符等不同写法统一到一种格式)。
#   新增: 剥 Windows 扩展长度前缀 \\?\(realpath 在尾空格/超长路径上会自产, 不剥则与名单对不上 → 系统禁区
#   降级为区外); UNC 扩展分支(\\?\UNC\srv\share -> \\srv\share)还原; 统一去尾部分隔符(盘根保留)。
# 2026-10-19 小欧 - 更正上一条误记: "归属匹配侧新增 _to_match_path"不实(该函数未实现, 通配符段匹配仍待定),
#   删除该虚假记载; 唯一实现公开更名为 format_path, 并在安全模块入口对 tool 的 path/dest 值做格式化(键名不变)。
# 2026-10-19 小欧 - 修复归属误判: _locate 原只对"磁盘根目录"标签做仅自身判定, 导致"允许根自身"
#   (项目根/授权目录/会话工作区)的下级也命中禁区·非系统 → 写入被降级为需确认、删除被拒, 而设计意图
#   (:22/:295)为"仅自身"、下级归白名单。改: 引入 _SELF_ONLY_LABELS(盘根 + 允许根自身), _locate 按集判定
#   仅自身, 允许根 label 常量化为 _ALLOWED_ROOT_SELF_LABEL。判定链/权限矩阵零改动。
# 2026-10-19 小欧 - 修复跨 loop 污染: _current_or_build 原在无作用域直调后把名单写回 ContextVar
#   且不还原, 使其后 loop 作用域"已存在即复用"而误用旧名单; 改为临时构建只返回、不写回。
# 2026-10-20 小欧 - format_path 入口实测修复: 先去首尾空白(防相对路径挂错基准); 空/"."/".." 无
#   绝对语义(realpath 会解析成 cwd 泄漏), 守卫 fail-closed 抛 ValueError; 盘符外含冒号(NTFS ADS)
#   不送 realpath, 以 abspath 保留原样交安全线裁决 — 小欧-2026-10-20
# 2026-10-20 小欧 - 判定结构整改: "仅自身"改 DirRule.self_only 字段(原靠 label 判定, 改文案即改行为),
#   删 _SELF_ONLY_LABELS; _locate 复用 _is_under 并返回 (hit, rule, is_self) 三态; DirectoryLists
#   字段改 tuple(防下游就地 append 致判定/落库分裂); 名单构建失败一律上抛, 由安全入口单点转
#   blocked(原吞异常降级会让"删项目根"从 DENY 降为可授权); 收集允许根时不再 Path.resolve
#   (原始串统一交 _complete) — 小欧-2026-10-20
# 2026-10-20 小欧 - 白名单范围纠正: 删除"非系统盘整盘挂入白名单"(写/删全 PASS 属越权扩大, 绕过
#   allowed_dirs), 白名单只含 用户目录 + 临时目录 + 允许根; 盘上其余目录落白名单外(需确认);
#   _data_drive_roots() 及 26 盘符扫描删除; 绝对性检查下沉 format_path(require_absolute);
#   快照内容未变则跳过重复 UPDATE — 小欧-2026-10-20
"""
path_dir_lists · 目录数组清单 + 归属判定(全系统唯一)

三个一维数组(每个都是一个 Tuple[DirRule, ...] 只读变量):
  forbidden_system_path     禁区·系统     平台根 + 系统保护目录 + 跨平台禁区(常量清单产出)
  forbidden_non_system_path 禁区·非系统   代码目录 + 允许根自身
  whitelist_path            白名单        用户目录 + 临时目录 + 允许根, 全系统唯一允许范围

名单项字段:
  path      = 构建期已 expanduser + realpath 的完整路径, 严禁半截/相对/待拼接项
  label     = 语义标签, 仅供日志与提示文案(不参与判定)
  self_only = 是否仅判自身(盘根 / 允许根自身为 True; 其余含下级)

匹配规则(靠结构字段, 不靠 label 文案):
  self_only=True  -> 仅判自身(否则整盘命中)
  self_only=False -> 命中自身及其下级
  同一名单多条命中 -> 取 path 最深的一条(自身命中即最深, 立即定案)

跨平台: 名单结构与判定代码完全一致, 平台差异只在 _platform_root() 与常量清单的路径拼法。

小欧 2026-10-19
"""

import json
import ntpath
import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from app.logger import logger
from app.config import get_code_root, get_config
from app.session_workspace import session_workspace_paths

#: 盘根 label 标识 —— 该条目只判自身(模块内私有, 外部零使用); 行为靠 self_only, label 仅文案
_DISK_ROOT_LABEL = "磁盘根目录"

#: 允许根 label 标识 —— 允许根集里的根目录**只判自身**(其下级归白名单; 模块内私有)
_ALLOWED_ROOT_SELF_LABEL = "允许根自身"

#: 2026-10-20 05:27 小欧 - 用户级自启动目录 —— 用户树(白名单)内的持久化落点, 写=PASS 等于留下
#:   "写入后随登录自启"的通道; 列入禁区·非系统且含下级(启动项文件在目录内, 仅判自身会漏回白名单)。
#:   系统级(All Users) Startup 在 ProgramData 系统保护目录下级, 已由禁区·系统覆盖, 不重复挂
#: 2026-10-20 小欧 - 原名 _STARTUP_SELF_LABEL 带 SELF 却含下级, 易被误加进"仅自身"集合, 更名
_STARTUP_LABEL = "用户自启动目录"

# ── 系统禁区常量清单(跨平台, 本期唯一来源; 将来接配置时在此之上并入用户项) ──

#: 系统保护目录名: 与盘符/挂载点无关的纯名字, 构建期才拼成完整路径
SYSTEM_PROTECTED_DIR_NAMES: tuple = (
    "windows", "program files", "program files (x86)",
    "programdata", "boot", "recovery", "winnt", "system32", "system",
)

#: 跨平台系统禁区·文件(精确, 仅自身)
FORBIDDEN_SYSTEM_EXACT: tuple = (
    "/etc/shadow", "/etc/sudoers",
)

#: 跨平台系统禁区·目录(含下级)
FORBIDDEN_SYSTEM_PREFIX: tuple = (
    "/proc", "/sys",
)

#: 归属枚举
SCOPE_FORBIDDEN_SYSTEM = "forbidden_system"
SCOPE_FORBIDDEN_NON_SYSTEM = "forbidden_non_system"
SCOPE_WHITELIST_SELF = "whitelist_self"
SCOPE_WHITELIST_SUB = "whitelist_sub"
SCOPE_OUTSIDE = "outside"

#: 禁区两档(调用方只判"是否禁区"时用这一个集合, 无需逐档罗列) — 小欧 2026-10-19
FORBIDDEN_SCOPES = frozenset({SCOPE_FORBIDDEN_SYSTEM, SCOPE_FORBIDDEN_NON_SYSTEM})

#: 操作线枚举
PASS, CONFIRM, DENY = "pass", "confirm", "deny"

#: 权限矩阵(归属 → 读 / 写 / 删 / 递归删), 三条线共用这一张表
PERMISSION: dict = {
    SCOPE_FORBIDDEN_SYSTEM:     (PASS, DENY,    DENY,    DENY),
    SCOPE_FORBIDDEN_NON_SYSTEM: (PASS, CONFIRM, DENY,    DENY),
    SCOPE_WHITELIST_SELF:       (PASS, PASS,    DENY,    DENY),
    SCOPE_WHITELIST_SUB:        (PASS, PASS,    PASS,    PASS),
    SCOPE_OUTSIDE:              (PASS, CONFIRM, CONFIRM, DENY),
}
#: 矩阵列序: 读 / 写 / 删 / 递归删
LINE_READ, LINE_WRITE, LINE_DELETE, LINE_DELETE_RECURSIVE = range(4)

#: 归属 → 中文文案(供提示消息查用; 禁止把英文枚举值直接插进面向用户的消息)
SCOPE_TEXT: dict = {
    SCOPE_FORBIDDEN_SYSTEM:     "系统禁区, 禁止操作",
    SCOPE_FORBIDDEN_NON_SYSTEM: "受保护的代码目录或允许根, 不允许授权",
    SCOPE_WHITELIST_SELF:       "允许范围根目录本身",
    SCOPE_WHITELIST_SUB:        "允许范围内的目录",
    SCOPE_OUTSIDE:              "允许范围之外",
}


@dataclass(frozen=True)
class DirRule:
    """名单项: 完整路径 + 语义标签 + 是否仅判自身

    self_only 是**判定字段**: 盘根/允许根自身为 True(只判自身), 其余含下级。
    label 仅用于日志与提示文案, 严禁参与判定(改文案不得改变安全行为)。
    """
    path: Path
    label: str
    self_only: bool = False


@dataclass(frozen=True)
class DirectoryLists:
    """本 loop 的目录名单(唯一数据源): 三个一维只读数组

    字段用 tuple 而非 list: frozen 只防属性赋值, 可变 List 仍可被下游就地 append,
    导致判定用的名单与落库快照分裂(审计源必须不可变)。
    """
    forbidden_system_path: Tuple[DirRule, ...] = ()
    forbidden_non_system_path: Tuple[DirRule, ...] = ()
    whitelist_path: Tuple[DirRule, ...] = ()


#: 当前 loop 的目录名单。构建点唯一(安全模块入口 check_before_execute 开头), 全链路只读
_current_directory_lists: ContextVar = ContextVar("current_directory_lists", default=None)


# ────────────────── 环境事实(自 path_env 迁入) ──────────────────

def _get_system_drive() -> str:
    """动态获取真实系统盘符(三级探测, 全失败回落 C:)"""
    for var in ("SystemRoot", "WINDIR"):
        root = os.environ.get(var)
        if root:
            drive, _ = os.path.splitdrive(root)
            if drive:
                return drive
    sdrive = os.environ.get("SystemDrive", "")
    if sdrive:
        return sdrive.rstrip("\\/")
    if os.name == "nt":
        for c in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.isdir(f"{c}:\\Windows"):
                return f"{c}:"
    return "C:"


def _system_temp_dir() -> Path:
    """系统临时目录(Windows 取 TEMP/TMP, 其他平台回落 /tmp)"""
    if os.name == "nt":
        temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if temp:
            return Path(temp)
    return Path("/tmp")


# ────────────────── 路径格式化(全系统唯一实现) ──────────────────

#: Windows 扩展长度前缀
_EXT_PREFIX = "\\\\?\\"


def strip_windows_prefix(raw: str) -> str:
    """剥离 Windows 扩展长度前缀 \\?\\ — 小欧 2026-10-19

    两种来源都只此一处剥离:  LLM 直给的 `\\\\?\\C:\\x`;
     Windows `os.path.realpath` 对尾空格/超长路径**自产**的 `\\\\?\\`。
    UNC 分支还原: `\\\\?\\UNC\\srv\\share` -> `\\\\srv\\share`(其余 `\\\\?\\X` -> `X`)。
    """
    if raw.startswith(_EXT_PREFIX):
        rest = raw[len(_EXT_PREFIX):]
        if rest[:4].lower() == "unc\\":
            return "\\\\" + rest[4:]
        return rest
    return raw


def format_path(file_path: str, require_absolute: bool = False) -> str:
    """路径格式化唯一实现(全系统唯一真源) — 小欧 2026-10-19

    口径(顺序固定): 剥入参 `\\\\?\\` → expanduser → realpath(解 symlink / `..` / 8.3 短名 /
    正斜杠)→ **再剥** realpath 自产的 `\\\\?\\` → 折叠重复分隔符 → 去尾部分隔符(盘根 `X:\\` 保留)
    → 盘符统一大写(Windows)。

    名单构建 _complete / 查询 classify_path / 安全模块入口(工具 path/dest 值)三处共用本函数 ——
    保证"名单里是什么格式, 工具参数就是什么格式"; 两边若各写一遍 realpath, 口径一改即分裂。

    require_absolute=True: expanduser 后先判绝对性, 相对路径直接抛 ValueError(不在 realpath 前
    按 cwd 猜基准)。仅供名单构建使用 —— 名单条目必须"绝对且真实", 相对路径入名单等于把名单
    锚到构建时的 cwd, 换进程/换目录即错位。工具参数侧保持 False(相对路径仍按 cwd 解析, 不误拦)。
    """
    _raw = str(file_path).strip()                     # 2026-10-20 小欧 - FIX: 首尾空白不归一会把相对路径挂错基准
    if _raw in ("", ".", ".."):                       # 2026-10-20 小欧 - FIX: 无绝对语义, realpath 会解析成 cwd 泄漏
        raise ValueError(f"路径无绝对语义: {file_path!r}")
    p = strip_windows_prefix(_raw)
    # 2026-10-20 小欧 - FIX: 盘符段外的冒号(NTFS ADS)交 realpath 会被毁成 `x:ads`(实测),
    #   改走 abspath 保留原样, 由安全线按真实拼写裁决
    _drive = ntpath.splitdrive(p)[0]
    _skip_realpath = (":" in p[len(_drive):]) if _drive else (":" in p)
    p = os.path.expanduser(p)
    # 2026-10-20 小欧 - 绝对性守卫放进唯一格式化链, 避免 _complete 重复 expanduser/isabs
    if require_absolute and not os.path.isabs(p):
        raise ValueError(f"路径无绝对语义(相对路径不入名单): {file_path!r}")
    try:
        p = os.path.abspath(p) if _skip_realpath else os.path.realpath(p)
    except (ValueError, OSError):
        p = os.path.abspath(p)
    p = strip_windows_prefix(p)
    p = os.path.normpath(p) if p else p          # 折叠重复分隔符 / 统一分隔符
    if len(p) > 1:
        stripped = p.rstrip("\\/")
        # 盘根 `C:\\` 去尾后成 `C:`, 需还原; 其余一律去尾部分隔符
        p = (stripped + os.sep) if stripped.endswith(":") else (stripped or p)
    if os.name == "nt" and len(p) > 1 and p[1] == ":":
        p = p[0].upper() + p[1:]                 # 盘符统一大写
    return p


def _complete(path) -> Optional[Path]:
    """展开为完整真实路径; 失败返回 None(该项跳过, 不留半截路径)

    名单完整性的唯一守门点: 任何进入名单的路径都必须经此展开为绝对真实路径。
    格式化与"绝对性"两项检查全部走 format_path(require_absolute=True), 本函数不再
    自行 expanduser/isabs 预判, 保证全系统只有一条解析链 — 小欧-2026-10-20
    """
    try:
        return Path(format_path(path, require_absolute=True))
    except (ValueError, OSError, TypeError):
        return None


def _is_under(child: Path, parent: Path) -> bool:
    """child 是否在 parent 之下(不含相等)

    2026-10-20 05:27 小欧 - FIX: 原先安全性依赖"两侧都过 format_path"的调用纪律
    (字符串前缀匹配不校验输入), 新增消费点直送 raw 即整套失效; 现层内自证——两侧先
    normcase(统一大小写/分隔符)+normpath(消冗余拼写)再做前缀比较, 约定升级为函数级保证
    (不引入 realpath, 判定热路径零 IO 开销)。
    """
    _c = os.path.normcase(os.path.normpath(str(child))).rstrip("\\/")
    _p = os.path.normcase(os.path.normpath(str(parent))).rstrip("\\/")
    # 2026-10-20 小欧 - 平台根("/")归一后为空串, 空串 + os.sep 会退化为"任意绝对路径",
    #   这里显式按"在平台根之下"处理, 避免空串前缀造成误命中 — 小欧-2026-10-20
    if not _p:
        return _c.startswith(os.sep)
    return _c.startswith(_p + os.sep)


def _collect_white_list_scope_entries(include_session: bool) -> List[Tuple[str, str]]:
    """收集"路径作用域条目" [(原始路径, 来源标签)] — 小欧 2026-10-20

    返回带来源标签的条目(非纯根路径集合), 原始串交调用方 _complete 统一格式化。

    include_session=True : 项目根 + 授权目录 + 会话工作区(白名单用, 全量)
    include_session=False: 项目根 + 授权目录(禁区"允许根自身"用, 不含会话工作区)
      会话工作区是任务当次的工作目录根, 任务要创建它并在其中写文件; 把它挂进禁区
      "仅自身"会让"创建/写会话目录自身"被判需授权(2026-10-20 实测弹窗超时挂死)。
      其自身可写性由白名单"自身"档(PASS)承载。
    fail-closed: 读取异常即抛 RuntimeError, 不用空列表静默降级
    标签必须是真实来源(项目根 / 授权目录 / 会话工作区), 供白名单落库与日志区分 ——
      三种来源权限语义不同, 混写成一个标签等于审计失真。
    原始串统一由调用方 _complete 格式化(单一归一化点, 不在此处先行 resolve)

    会话工作区来源: session_workspace_paths() → ContextVar(编排层 task 启动时
      从 DB chat_session_workspaces 装载, 见 stream_orchestrator._load_ws_snapshot);
      执行层无任务上下文时为空列表(正常态, 非故障)。

    原 _build_allowed_roots / _build_protected_roots 两个纯透传包装已删, 调用方直接按
    include_session 传参。
    """
    try:
        cfg = get_config()
        roots: List[Tuple[str, str]] = [(str(cfg.get_project_root()), "项目根")]
        roots.extend((str(d), "授权目录") for d in cfg.get_allowed_dirs())
    except Exception as e:
        raise RuntimeError(f"读取允许根失败(config): {e}") from e
    if include_session:
        try:
            roots.extend((str(r), "会话工作区") for r in session_workspace_paths())
        except Exception as e:
            raise RuntimeError(f"读取会话工作区失败: {e}") from e
    return roots


def _platform_root() -> str:
    """平台根: Windows 取系统盘符根, Linux 取 /

    名单里只挂**当前平台的根** —— 其它盘符(D:/F:/E: ...)不进禁区, 走白名单外。
    """
    return (_get_system_drive() + "\\") if os.name == "nt" else "/"


def _build_forbidden_system_path() -> List[DirRule]:
    """构建禁区·系统一维数组 —— 来源是模块级常量清单, 跨平台同一套代码

    构建规则:
      (1) 磁盘根 —— label 磁盘根目录, 判定时只判自身(否则整盘命中)
      (2) 系统保护目录名 -> 拼在平台根下; 下级候选跳过(不下级)
      (3) 跨平台系统禁区: 文件精确 / 目录含下级
    将来接配置化时, 在 (3) 之后并入 _configured_forbidden_extra() 即可, 结构不变。
    """
    rules: List[DirRule] = []
    plat_root = _platform_root()

    # (1) 平台根 —— 只判自身
    root = _complete(plat_root)
    if root is not None:
        rules.append(DirRule(root, _DISK_ROOT_LABEL, self_only=True))

    # (2) 系统保护目录 —— 自身+下级; 下级候选跳过
    #   2026-10-20 小欧 - 跳过条件改用结构字段 self_only(原靠 label != 磁盘根目录)
    for name in SYSTEM_PROTECTED_DIR_NAMES:
        p = _complete(os.path.join(plat_root, name))
        if p is None:
            continue
        if any(_is_under(p, r.path) for r in rules if not r.self_only):
            continue                                   # 在已加入条目的下级之下 -> 不加入
        rules.append(DirRule(p, "系统保护目录"))

    # (3) 跨平台系统禁区(文件精确 / 目录含下级)
    for item in FORBIDDEN_SYSTEM_EXACT:
        p = _complete(item)
        if p is not None:
            rules.append(DirRule(p, "系统禁区(精确)"))
    for item in FORBIDDEN_SYSTEM_PREFIX:
        p = _complete(item.rstrip("/"))
        if p is not None:
            rules.append(DirRule(p, "系统禁区(前缀)"))

    return rules


def _build_forbidden_non_system_path() -> List[DirRule]:
    """构建禁区·非系统一维数组: 代码目录(自身+下级) + 允许根自身(仅自身)

    2026-10-20 小欧 - 允许根自身集只用 项目根+授权目录(不含会话工作区): 会话目录需被任务
      创建/写入, 其可写性由白名单自身档承载; 构建异常上抛, 由安全入口单点转 blocked。
    """
    rules: List[DirRule] = []
    code_root = get_code_root()
    full = _complete(code_root) if code_root else None
    if full is not None:
        rules.append(DirRule(full, "代码目录(含其内部子目录)"))
    for r, _source in _collect_white_list_scope_entries(include_session=False):
        full = _complete(r)
        if full is not None:
            rules.append(DirRule(full, _ALLOWED_ROOT_SELF_LABEL, self_only=True))
    # 2026-10-20 05:27 小欧 - FIX: 用户级自启动挂入(含下级——启动项文件在目录内, 仅自身堵不住);
    #   全局级(All Users)Startup 在 ProgramData 系统保护目录下级, 已被禁区·系统覆盖, 不重复挂
    _startup = _complete(str(Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup"))
    if _startup is not None:
        rules.append(DirRule(_startup, _STARTUP_LABEL))
    return rules


def _build_whitelist_path() -> List[DirRule]:
    """构建白名单一维数组 = 全系统唯一允许范围(自身+下级)

    2026-10-20 小欧 - 构建异常上抛, 不留残缺白名单, 由安全入口单点转 blocked。
    """
    rules: List[DirRule] = []
    for raw, label in ((Path.home(), "用户目录"), (_system_temp_dir(), "系统临时目录")):
        full = _complete(raw)
        if full is not None:
            rules.append(DirRule(full, label))
    for r, source in _collect_white_list_scope_entries(include_session=True):
        full = _complete(r)
        if full is not None:
            rules.append(DirRule(full, source))     # 标签=真实来源(项目根/授权目录/会话工作区)
    return rules


def _build_directory_lists() -> DirectoryLists:
    """构建本 loop 的目录名单(唯一构建口 / 全系统唯一目录取值口)

    调用点唯一: 安全模块入口 check_before_execute 开头(一个 loop = 一次安全检查), 每 loop 一次。
    构建后必须由调用方 _current_directory_lists.set(dl) 挂到本 loop 上下文。
    loop 内严禁二次调用 —— 任何"就近再取一次目录"都应改从名单读。
    """
    return DirectoryLists(
        forbidden_system_path=tuple(_build_forbidden_system_path()),
        forbidden_non_system_path=tuple(_build_forbidden_non_system_path()),
        whitelist_path=tuple(_build_whitelist_path()),
    )


def _current_or_build() -> DirectoryLists:
    """取当前 loop 名单; 无 loop 上下文(执行层直调)时就地构建一次返回

    用于 delete_file / temp_auth 这类"无任务上下文直调"的执行层路径: 该路径从未经过
    check_before_execute, ContextVar 必然为空。此种临时构建**不写回 ContextVar** ——
    写回会在无作用域时残留, 使紧随其后的 loop 作用域(见 directory_lists_scope 的
    "已存在即复用")误用这份来时不明的旧名单(跨 loop 污染); 直调点各自量小, 现算即用。
    """
    dl = _current_directory_lists.get()
    if dl is not None:
        return dl
    return _build_directory_lists()


@contextmanager
def directory_lists_scope(task_id: Optional[str] = None):
    """目录名单作用域 — **一个安全模块 loop = 一次本上下文** — 小欧 2026-10-19

    进入时: **构建一次目录名单(构建点唯一) → 立刻原样落库 → 挂进 ContextVar**;
    退出时自动还原。

    **为什么落库放在这里(生成的那一刻), 而不是调用方拿到之后再存**:
      · 快照的意义就是"这次判定用的到底是哪份名单"。名单**刚生成**是唯一无歧义的时刻 ——
        出了作用域名单就没了, 再去取只能靠 ContextVar 残留, 取不到就是"来路不明"。
      · 原设计把落库放在调用方(总闸返回之后), 一旦有人绕过编排层直接调判定层,
        快照就漏记 —— 而漏记的恰恰是最该被审计的场景。
      · 放在这里 = **带 task_id 时构建一次即落一次账**, 调用方无从遗漏, 也无须记得调
        (无 task_id 的执行层直调见下 Args: 该情形只构建不落库)。

    **可嵌套**: 已在作用域内时直接复用现有名单, **不二次构建、不重复落库** ——
    所以"每 loop 只构建一次"由本上下文管理器在结构上保证, 调用方无从违反。

    Args:
        task_id: 任务 id, 供快照落库定位 chat_tasks 行; 为空(None)则只构建不落库 ——
            执行层无任务上下文的直调(temp_auth / delete_file)走惰性构建, 不经过本管理器,
            故正常情况下这里总能拿到 task_id。

    用法:
        with directory_lists_scope(task_id=agent.task_id):
            ...  # 本 loop 内所有路径判定复用同一份名单
    """
    existing = _current_directory_lists.get()
    if existing is not None:
        yield existing                      # 已在 loop 内 → 复用, 不二次构建不重复落库
        return
    dl = _build_directory_lists()
    _save_snapshot(task_id, dl)             # 生成即刻落库
    token = _current_directory_lists.set(dl)
    try:
        yield dl
    finally:
        _current_directory_lists.reset(token)   # 必须还原: 不还原会顺着 asyncio task 上下文外泄


#: 各任务最近一次已落库的名单内容键(不含 built_at)。用于跳过"内容未变"的重复 UPDATE ——
#: 名单作用域每个工具调用开一次, 同一任务内名单通常不变, 每次 action 都 UPDATE 属写放大。
#: 上限保护: 超出即整体清空(只影响能否跳过写, 不影响正确性)。
_snapshot_keys: dict = {}
_SNAPSHOT_KEYS_MAX = 512


def _save_snapshot(task_id: Optional[str], dl: DirectoryLists) -> bool:
    """把刚生成的名单原样落库(审计辅助) — 小欧 2026-10-19

    Args:
        task_id: 任务 id; 为空只构建不落库
        dl: 本次判定实际使用的名单(与判定对象同一份, 保证快照=判定口径)

    失败只记 warning 不抛: 落库是审计辅助, 不得因它阻断工具执行。
    惰性导入 app.db: 只在真正落库时才引入, 且避免本模块在安全层导入期就把 db 拉进来。
    (app.db 不依赖 app.safety, 无循环依赖。)

    2026-10-20 小欧 - 内容(三数组, 不含 built_at)未变则跳过 UPDATE, 避免每 action 重复写;
      变更即写, 仍保证每任务保留最新一份完整名单。
    """
    if not task_id:
        return False
    key = (dl.forbidden_system_path, dl.forbidden_non_system_path, dl.whitelist_path)
    if _snapshot_keys.get(task_id) == key:
        return False                                  # 内容未变, 不重复写
    try:
        from app.db.task_scope_queries import save_path_scope_snapshot
        ok = save_path_scope_snapshot(task_id, _to_snapshot_json(dl))
        if ok:
            if len(_snapshot_keys) >= _SNAPSHOT_KEYS_MAX:
                _snapshot_keys.clear()
            _snapshot_keys[task_id] = key
        return ok
    except Exception as e:
        logger.warning(f"[path_dir_lists] 目录名单快照落库失败(不影响执行): {e}")
        return False


# ────────────────── 归属判定(全系统唯一) ──────────────────

def _locate(rules: Sequence[DirRule], real_path: Path) -> Tuple[bool, Optional[DirRule], bool]:
    """在一维名单中定位路径, 取最深命中项 — 小欧 2026-10-19 / 2026-10-20

    Returns:
        (hit, rule, is_self) — 自身命中 True; 下级命中 False; 未命中 (False, None, False)
    规则: 自身命中立即定案; self_only=True 的条目只判自身; 多条命中取 path 最深。
    2026-10-20 小欧 - "包含"统一走 _is_under(单一实现), 返回 is_self 免调用方二次比较。
    """
    best: Optional[DirRule] = None
    # 归一为 Path: 误传 str 时 Path 比较恒不相等(自身档静默失效), 此处统一收口 — 小欧-2026-10-20
    rp = Path(real_path)
    for rule in rules:
        if rp == rule.path:
            return True, rule, True                    # 自身命中, 最深, 立即定案
        if rule.self_only:
            continue                                   # 仅自身类条目(盘根/允许根)不向下匹配
        if _is_under(rp, rule.path):
            if best is None or len(rule.path.parts) > len(best.path.parts):
                best = rule                            # 取最深命中
    return (best is not None), best, False


def _classify_scope(dl: DirectoryLists, real_path: Path) -> Tuple[str, Optional[DirRule]]:
    """归属判定链(顺序不可换): 禁区·系统 → 禁区·非系统 → 白名单·自身 → 白名单·下级 → 白名单外"""
    hit, rule, _is_self = _locate(dl.forbidden_system_path, real_path)
    if hit:
        return SCOPE_FORBIDDEN_SYSTEM, rule

    hit, rule, _is_self = _locate(dl.forbidden_non_system_path, real_path)
    if hit:
        return SCOPE_FORBIDDEN_NON_SYSTEM, rule   # 禁区优先, 到此定案

    hit, rule, is_self = _locate(dl.whitelist_path, real_path)
    if hit:
        return (SCOPE_WHITELIST_SELF if is_self else SCOPE_WHITELIST_SUB), rule

    return SCOPE_OUTSIDE, None


def permission_of(scope: str, line: int) -> str:
    """查权限矩阵: 返回 PASS / CONFIRM / DENY"""
    return PERMISSION[scope][line]


def classify_path(file_path: str) -> Tuple[str, Optional[DirRule]]:
    """格式化 + 归属判定 — **全系统唯一的"路径 → 五档归属"入口** — 小欧 2026-10-19

    Args:
        file_path: 原始路径(可含 ~、相对段、symlink)

    Returns:
        (scope, rule) — scope 为五档之一; rule 为命中的名单条目(白名单外为 None)

    格式化口径见 `format_path`(只此一处); 判定链顺序不变(禁区优先, 见 classify_scope)。

    作用域语义(调用方必读):
      在 directory_lists_scope 内 → 用本 loop 唯一名单; 作用域外直调 → 就地临时构建, 不写回
      ContextVar(防跨 loop 污染)。两种路径判定口径相同。构建失败 fail-closed 抛异常, 执行层
      各调用点已包 try, 按"判不出即拒绝"处理。
    """
    return _classify_scope(_current_or_build(), Path(format_path(file_path)))


def _to_snapshot_json(dl: DirectoryLists) -> str:
    """把目录清单原样序列化为 JSON(全量, 不裁剪)"""
    def dump(rules: Sequence[DirRule]) -> list:
        return [{"path": str(r.path), "label": r.label} for r in rules]

    return json.dumps({
        "built_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "forbidden_system_path": dump(dl.forbidden_system_path),
        "forbidden_non_system_path": dump(dl.forbidden_non_system_path),
        "whitelist_path": dump(dl.whitelist_path),
    }, ensure_ascii=False)


__all__ = [
    # ── 判定入口(外部只需这三个 + 下面的动作/档位常量) ──
    "classify_path",          # 路径 → 五档归属(唯一判定入口, 含格式化)
    "format_path",            # 路径格式化唯一真源
    "permission_of",          # 档位 + 动作 → PASS/CONFIRM/DENY
    # ── 动作查询 ──
    "PERMISSION", "PASS", "CONFIRM", "DENY",
    "LINE_WRITE", "LINE_DELETE", "LINE_DELETE_RECURSIVE",
    # ── 档位(外部真正比较的两个 + 禁区集合) + 归属中文文案 ──
    "SCOPE_FORBIDDEN_SYSTEM", "SCOPE_FORBIDDEN_NON_SYSTEM", "FORBIDDEN_SCOPES", "SCOPE_TEXT",
    # ── 名单常量(设置页文档渲染用) ──
    "SYSTEM_PROTECTED_DIR_NAMES",
    # ── loop 作用域管理(替代原先 build/get/get_or_build 三个取值口 + ContextVar 外露) ──
    "directory_lists_scope",
]
