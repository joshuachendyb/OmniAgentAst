# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-14 小欧 - 文档[33] 4.12-B 自 app/utils/path_utils.py 迁入(当时的归属: 通用层, 因 tools 禁 import app.safety)。
#   迁入理由: 工具层硬底线 delete_file._guard_forbidden_delete 需在 app.safety 开关被关闭时仍能拦系统目录,
#     故判定必须放在工具层够得到、且不依赖任何开关的地方。
# 2026-10-15 北京老陈裁定(文档[35] 阶段五) - **迁回 app/safety/path_guard.py**:
#   职责归属回归安全域(目录分类属安全判定, 不是通用工具);
#   越层限制改由"能力分级白名单"解开, 而非靠把判定寄居 utils 绕开(见 3.6.2)。
#   本模块为纯判定: 零配置读取、零 I/O、**不读 security.enabled** —— 保证工具层依赖它
#   ≠ 依赖可被关闭的前线防线(硬底线独立性)。
#   迁移手法: 四个函数自 path_utils.py **逐字搬迁**, 实现与异常口径一字不改。
# 2026-10-15 北京老陈裁定(DRY) - is_protected_root_itself 的 extra_roots 省略时自取会话快照: 原由 path_safe_check 与 delete_file 各取一次, 改一处漏一处即致授权判定分叉。
"""
path_guard — 路径属性判定: 这条路径是什么性质

回答一个问题: **给一条路径, 它属于哪一类?**

  系统保护目录   C:\\Windows / C:\\Program Files / C:\\ProgramData ...
  磁盘根         C:\
  代码库根       代码库及其父子级
  受保护根       项目根 / 授权目录及其上级

回答的是"是什么", 不回答"能不能操作" —— 能不能操作由读/写/删三条线各自决定
(read_path_check / write_path_check / delete_path_check)。

**允许谁 import**: 工具层硬底线(app.tools.*)与安全层(app.safety.*)均可。
本模块不读 security.enabled, 是全套路径安全中唯一可被工具层直接依赖的部分。

小欧 2026-10-14 建 / 2026-10-15 小欧 迁回安全域
"""

import os
from pathlib import Path
from typing import Iterable, Optional

from app.logger import logger
from app.utils.path_utils import get_allowed_roots

# 2026-10-14 小欧 - 补 winnt/system32/system(原仅工具层有): 两层对"什么算系统目录"判定相反, 取并集为单源。
# 2026-10-14 小欧 - 迁自 app/tools/tool_constants.py:574（文档[33] 4.12-B）
SYSTEM_PROTECTED_DIR_NAMES: frozenset[str] = frozenset({
    "windows", "program files", "program files (x86)",
    "programdata", "boot", "recovery",
    "winnt", "system32", "system",
})


def is_system_protected_path(file_path: str, mode: str = "write") -> bool:
    r"""系统目录保护判定(**检测+策略单源**, 全仓共用) — 小欧 2026-10-14

    检测法: 展开(`expanduser` → `realpath`)后取**盘符后的第一段**(`parts[1]`), 比对
    SYSTEM_PROTECTED_DIR_NAMES(大小写不敏感)。异常不静默放行, 一律判为受保护。

    mode 决定该操作是否被禁(**策略在此收口, 调用方不得自行解释**):
      - `read`   → 放行(P3 设计, 内容敏感性由内容过滤兜底)
      - `write` / `delete` / 其他 → 拦

    2026-10-14 北京老陈裁定「必须是同一个逻辑」: 此前检测与策略各处分一层,
    实测同一 True 被不同调用点解释成相反结论(安全层放行读/工具层拒绝读)。
    现检测与策略同在本函数, 调用方只透传 mode、不得二次判断。消费方两处:
      ① 安全层 `path_safe_check._is_forbidden_path`(SA5 判权限, 唯一决策者)
      ② `delete_file._guard_forbidden_delete`(SA8 硬底线镜像 A 族, 不读安全总开关)
    """
    try:
        parts = Path(os.path.realpath(os.path.expanduser(file_path))).parts
        hit = len(parts) > 1 and parts[1].lower() in SYSTEM_PROTECTED_DIR_NAMES
    except Exception:
        # 2026-10-15 小欧 - P0-1: 原 `hit=True` 后仍走 `mode != "read"`, 实测传 None + read 返回 False(放行),
        #   与 docstring「异常不静默放行」矛盾。改为异常即返回, 不再过 mode 判定。
        return True
    return hit and mode != "read"


def is_disk_root(file_path: str) -> bool:
    r"""是否磁盘根(如 `C:\` / `D:\`) —— 判定单源, 各层只调用

    2026-10-14 北京老陈裁定: 此前 `_is_forbidden_path` / `validate_not_system_path` /
    `_guard_forbidden_delete` 三处各写一遍 splitdrive + 剩余为空, 现收敛到此。
    """
    try:
        drive, rest = os.path.splitdrive(str(Path(os.path.realpath(os.path.expanduser(file_path)))))
        return bool(drive) and not rest.strip("\\/")
    except Exception:
        # 2026-10-15 小欧 - P0-3: 磁盘根是最高档禁区, 原返回 False(fail-open)。归一化失败按禁。
        return True


def is_code_root_path(file_path: str) -> bool:
    """是否落在代码库根及其子/父级内 —— 判定单源, 各层只调用"""
    try:
        from app.config import get_code_root  # 延迟导入: 避免 app.safety 顶层依赖 app.config
        code_root = get_code_root()
        if not code_root:
            return False
        cr_lower = str(Path(os.path.realpath(code_root))).lower()
        p_lower = str(Path(os.path.realpath(os.path.expanduser(file_path)))).lower()
        return (p_lower == cr_lower
                or p_lower.startswith(cr_lower + os.sep)
                or p_lower.startswith(cr_lower + "/"))
    except Exception:
        # 2026-10-15 小欧 - P0-2: 代码库根是开关无关硬禁区, 原返回 False(fail-open)致硬拦截失效。按禁。
        return True


def is_protected_root_itself(file_path: str, extra_roots: Optional[Iterable[str]] = None) -> Optional[str]:
    r"""是否受保护根**自身**或其上级祖先 —— 判定单源, 各层只调用

    返回禁止原因; 不属于受保护根返回 None。根**内部**的具体文件不拦, 只禁根自己与更上层。
    extra_roots 语义同 get_allowed_roots; 【省略时本函数自取会话工作区快照】——
    取数职责收在此处一处, 调用方不再各自去 context 取, 防两处取法分叉致判定不一致。

    fail-closed: 根集读取异常(get_allowed_roots 抛错)时返回 "protected_root_itself" ——
    读不出根集就无法证明"不是受保护根", 按禁处理, 不得让异常冒泡到消费方(SA8 硬底线会崩而非拦)。
    """
    try:
        p = Path(os.path.realpath(os.path.expanduser(file_path)))
    except Exception:
        return "protected_root_itself"          # fail-closed: 归一化失败亦按禁处理
    try:
        if extra_roots is None:
            # 2026-10-15 北京老陈裁定(DRY): 取数收归本函数, 调用方不再各自取。
            # 延迟导入保本模块零顶层依赖(路径属性判定不该拖上层)。
            from app.tools.context import session_workspace_paths
            extra_roots = session_workspace_paths()
        roots = get_allowed_roots(extra_roots)
    except Exception as e:
        logger.warning(f"[path_guard] 读取允许根失败, 按受保护根拒绝: {e}")
        return "protected_root_itself"
    for root in roots:
        try:
            if p == root:
                return "protected_root_itself"
            for ancestor in root.parents:
                if p == ancestor:
                    return "protected_root_ancestor"
        except Exception:
            # 2026-10-15 小欧 - P0-4: 原 continue 使该根被当作不提供保护(fail-open 且无痕)。按禁。
            logger.warning(f"[path_guard] 受保护根比较失败, 按受保护根拒绝: root={root}")
            return "protected_root_itself"
    return None


__all__ = ["SYSTEM_PROTECTED_DIR_NAMES", "is_system_protected_path",
           "is_disk_root", "is_code_root_path", "is_protected_root_itself"]