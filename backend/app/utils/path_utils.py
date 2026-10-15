
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 三堂会审复核落地: 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
# 2026-10-14 - 小欧 - 文档[33] 4.12-B: 迁入 SYSTEM_PROTECTED_DIR_NAMES 与 is_system_protected_path(老陈裁定「纯路径工具函数, 独立到 utils」); 名单与判定同处一地以免 utils 反向依赖 app.tools
# 2026-10-14 北京老陈裁定 - 4 类目录判定收敛为本文件唯一实现: is_disk_root / is_code_root_path /
#   is_protected_root_itself(原三处各写一遍 splitdrive 与前缀匹配, 结论可能相反); _get_protected_roots 无外部消费方故私有化。
# 2026-10-15 北京老陈裁定(DRY) - _get_protected_roots 更名 get_allowed_roots 并提为公开单源:
#   原根集合在 delete_safety._get_allowed_roots / path_safe_check 白名单构建 / 本文件三处各写一份同义逻辑,
#   且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现三处统一调用本函数; 失败语义改 fail-closed。

    # 2026-10-15 北京老陈裁定(三堂会审补漏) - is_protected_root_itself 调用 get_allowed_roots() 必须自带 try:
#   get_allowed_roots 已是 fail-closed(抛 RuntimeError), 而本函数两个消费方
#   (path_safe_check._is_forbidden_path / delete_file._guard_forbidden_delete SA8硬底线) 均未包 try,
#   故障注入实测异常会一路冒泡 — 硬底线将抛异常而非安全拒绝(退化: 崩掉 ≠ 拦住)。
#   现按 fail-closed 收口: 根集读不出 → 无法证明"不是受保护根" → 一律判为受保护根(禁)。
"""
path_utils — 路径处理工具

职责: Windows 长路径支持、系统保护目录判定等路径相关公共函数

2026-10-14 小欧 - 文档[33] 4.12-B: SYSTEM_PROTECTED_DIR_NAMES 与 is_system_protected_path 由
tool_constants / security.path_safe_check 一并下沉(老陈裁定「纯路径工具函数, 独立到 utils」)。
名单与判定必须同处一地: 名单留上层则 utils 要 import app.tools, 即分层倒挂。
"""
import os
from pathlib import Path
from typing import Iterable, Optional

# 2026-10-06 小欧 - 从 path_safe_check.validate_path 函数体内提到模块级(常量归位): 原先定义在函数里,
#   每次调用重建一遍 frozenset; 展示层(security_docs)拿不到, 只能硬编码 \ProgramData 等 3 条。
# 2026-10-14 小欧 - 补 winnt/system32/system(原仅工具层有): 两层对"什么算系统目录"判定相反, 取并集为单源。
# 2026-10-14 小欧 - 迁自 app/tools/tool_constants.py:574（文档[33] 4.12-B）
SYSTEM_PROTECTED_DIR_NAMES: frozenset[str] = frozenset({
    "windows", "program files", "program files (x86)",
    "programdata", "boot", "recovery",
    "winnt", "system32", "system",
})


def to_win_long_path(path: Path) -> str:
    r"""Windows长路径 \\?\ 前缀, 绕过MAX_PATH(260)限制 — 小欧 2026-08-11
    仅NT系统生效; 已带前缀或非绝对路径保持原样。
    """
    if os.name != "nt":
        return str(path)
    s = str(path)
    if s.startswith("\\\\?\\") or not Path(s).is_absolute():
        return s
    return "\\\\?\\" + s


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
    工具层 validate_path / validate_path_for_extract 已于 10-15 移除权限判断, 不再消费本函数。
    单源落 utils 而非安全层: 「硬底线不能依赖前面的防线」, 且 tools→safety 越层不可清(文档[33] 4.12-B)。
    """
    try:
        parts = Path(os.path.realpath(os.path.expanduser(file_path))).parts
        hit = len(parts) > 1 and parts[1].lower() in SYSTEM_PROTECTED_DIR_NAMES
    except Exception:
        # 异常不静默放行: 判定为受保护, 与 _is_forbidden_path 异常口径一致
        hit = True
    return hit and mode != "read"


# ====================================================================
# 目录安全判定 —— 4 类目录的**唯一实现**(全仓共用, 各层只调不写)
# 2026-10-14 北京老陈裁定「4 类目录的安全必须只能有一份, 其他地方调用」:
#   此前 磁盘根 被 3 处各写一遍 splitdrive、代码库根/项目根各写一遍, 结论可能相反。
#   现把 4 类收敛到本文件, 下游只调用。
# ====================================================================


def is_disk_root(file_path: str) -> bool:
    r"""是否磁盘根(如 `C:\` / `D:\`) —— 判定单源, 各层只调用

    2026-10-14 北京老陈裁定: 此前 `_is_forbidden_path` / `validate_not_system_path` /
    `_guard_forbidden_delete` 三处各写一遍 splitdrive + 剩余为空, 现收敛到此。
    """
    try:
        drive, rest = os.path.splitdrive(str(Path(os.path.realpath(os.path.expanduser(file_path)))))
        return bool(drive) and not rest.strip("\\/")
    except Exception:
        return False


def is_code_root_path(file_path: str) -> bool:
    """是否落在代码库根及其子/父级内 —— 判定单源, 各层只调用"""
    try:
        from app.config import get_code_root  # 延迟导入: utils 不反向依赖 app.config
        code_root = get_code_root()
        if not code_root:
            return False
        cr_lower = str(Path(os.path.realpath(code_root))).lower()
        p_lower = str(Path(os.path.realpath(os.path.expanduser(file_path)))).lower()
        return (p_lower == cr_lower
                or p_lower.startswith(cr_lower + os.sep)
                or p_lower.startswith(cr_lower + "/"))
    except Exception:
        return False


def get_allowed_roots(extra_roots: Optional[Iterable[str]] = None) -> list:
    r"""允许根集合 = 项目根 + 授权目录 [+ 调用方传入的会话工作区] — **判定单源, 各层只调用**

    2026-10-15 北京老陈裁定(DRY 收敛): 此前 delete_safety._get_allowed_roots /
    path_safe_check 的白名单构建 / 本文件 _get_protected_roots 三处各写一份同义逻辑,
    且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现收于本函数, 三处统一调用。

    extra_roots 参数化(去反向依赖): 会话工作区快照在 app/tools/context.py, 属上层。
      若本函数直接 import 即构成「utils 反向依赖上层」(架构守护测试 test_utils_does_not_depend_on_upper_layers 红)。
      改为由调用方传入 —— safety 层与 tools 层**均可** import app.tools.context
      (铁律只禁 tools→services/safety, safety→tools 本就合法; tools→tools 同层更合法),
      故此拆分**不损失任何保护**, 仅解开 utils 的分层依赖。

    失败语义(fail-closed): config 来源读取异常即整体抛 RuntimeError, 不用空列表静默降级 ——
    空列表会让"是否在允许根内"恒为 False, 把全部路径误判成区外, 属安全侧最坏的静默失败。
    """
    from app.config import get_config  # 延迟导入: utils 不反向依赖 app.config

    roots: list = []
    try:
        cfg = get_config()
        roots.append(Path(cfg.get_project_root()).resolve())
        roots.extend(Path(d).resolve() for d in cfg.get_allowed_dirs())
    except Exception as e:
        raise RuntimeError(f"读取允许根失败(config): {e}") from e
    if extra_roots:
        try:
            roots.extend(Path(p).resolve() for p in extra_roots)
        except Exception as e:
            raise RuntimeError(f"读取允许根失败(会话工作区): {e}") from e
    return roots


def is_protected_root_itself(file_path: str, extra_roots: Optional[Iterable[str]] = None) -> Optional[str]:
    r"""是否受保护根**自身**或其上级祖先 —— 判定单源, 各层只调用

    返回禁止原因; 不属于受保护根返回 None。根**内部**的具体文件不拦, 只禁根自己与更上层。
    extra_roots 语义同 get_allowed_roots(会话工作区快照由调用方传入, 见该函数说明)。

    fail-closed: 根集读取异常(get_allowed_roots 抛错)时返回 "protected_root_itself" ——
    读不出根集就无法证明"不是受保护根", 按禁处理, 不得让异常冒泡到消费方(SA8 硬底线会崩而非拦)。
    """
    try:
        p = Path(os.path.realpath(os.path.expanduser(file_path)))
    except Exception:
        return "protected_root_itself"          # fail-closed: 归一化失败亦按禁处理
    try:
        roots = get_allowed_roots(extra_roots)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[path_utils] 读取允许根失败, 按受保护根拒绝: {e}")
        return "protected_root_itself"
    for root in roots:
        try:
            if p == root:
                return "protected_root_itself"
            for ancestor in root.parents:
                if p == ancestor:
                    return "protected_root_ancestor"
        except Exception:
            continue
    return None