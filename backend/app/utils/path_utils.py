
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 三堂会审复核落地: 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
# 2026-10-15 北京老陈裁定(DRY) - 4 类目录判定收敛为 utils 唯一实现; _get_protected_roots 提为公开单源:
#   原根集合在 delete_safety._get_allowed_roots / path_safe_check 白名单构建 / 本文件三处各写一份同义逻辑,
#   且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现三处统一调用本函数; 失败语义改 fail-closed。
# 2026-10-15 小欧 - 文档[35] 阶段五: SYSTEM_PROTECTED_DIR_NAMES / is_system_protected_path / is_disk_root /
#   is_code_root_path / is_allowed_root_itself 五符号迁往 app/safety/path_classify_category.py(职责回归安全域)。
#   本文件不再持有任何安全判定, 只剩长路径与允许根两项通用工具; 旧名不保留转发(禁止 backward).
# 2026-10-16 - 小欧 - tool去检查化: 纯内存路径格式原子(保留字符/保留名/多余盘符)下沉至此。
#   口径: 纯拼写判定, 无IO、无白名单、无授权语义, 故不是"安全判定", tools/safety 均可导入;
#   tools 禁 import safety, 故 tool 内派生路径检查只能调本层。
# 2026-10-17 北京老陈裁定 - 迁入 check_path_syntax_and_exists(自 path_1st_legality_check)与 check_preconditions(自 path_check_common);
#   新增 reject_reason_empty_path(空值唯一真源)与 check_path_five_level(tool 专用五级总入口, delete/move/copy 共用; ⑤禁区判定受 logging.debug 门控)。
#   ★更正上方 10-16 记载: 按 B 方案本模块已可引用 app.safety.path_classify_category(仅转发禁区判据, 不持名单)。
# 2026-10-17 北京老陈裁定 - 迁入 check_path_syntax_and_exists 与 check_preconditions, 新增空值原子 reject_reason_empty_path 与 tool 专用五级总入口 check_path_five_level
# 2026-10-17 - 小欧 - check_path_five_level 第⑤级内联禁区判据改调 delete_path_check.guard_forbidden_delete(硬底线单源,
#   惰性导入避免顶层循环); 本层不再自持禁区判据代码, 只编排。
"""
path_utils — 路径处理通用工具

职责: Windows 长路径支持、允许根集合构建、纯内存路径格式原子判定。
不含任何安全判定 —— 目录属性判定见 app/safety/path_classify_category.py(2026-10-15 迁出)；
本文件格式原子只判拼写(保留字符/保留名/多余盘符)，不判允许/禁区/授权。

小欧 2026-08-11 建 / 2026-10-15 小欧 收敛
"""
import os
import re
import string
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from app.logger import logger  # check_path_syntax_and_exists 的 TOCTOU 留痕 / check_preconditions 异常留痕

# 2026-10-06 小欧 - 从 path_safe_check.validate_path 函数体内提到模块级(常量归位): 原先定义在函数里,
#   每次调用重建一遍 frozenset; 展示层(security_docs)拿不到, 只能硬编码 \ProgramData 等 3 条。
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


# —— 纯内存路径格式原子(2026-10-16 小欧, 自 file_path_checker 逐字迁入) ——
# 单一真源: safety 门前初查 layers12 与 tool 内派生路径检查共用; 改一处两处齐知。
_WINDOWS_RESERVED_CHARS = '<>:"/\\|?*'
_WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
                     'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
                     'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}


def path_has_reserved_char(basename: str) -> Optional[str]:
    """文件名含 Windows 保留字符则返回该字符, 否则 None — 小欧 2026-10-16

    纯拼写判定(调用方保证传入的已是 basename, 盘符/分隔符不在检查范围)。
    """
    for c in basename or "":
        if c in _WINDOWS_RESERVED_CHARS:
            return c
    return None


def path_has_reserved_name(file_path: str) -> Optional[str]:
    """路径任一分段是 Windows 保留名则返回该分段, 否则 None — 小欧 2026-07-04(迁入未改逻辑)"""
    try:
        for part in Path(file_path).parts:
            if part.split('.')[0].upper() in _WINDOWS_RESERVED:
                return part
    except Exception:
        pass
    return None


def path_has_extra_drive(file_path: str) -> Optional[str]:
    """路径尾部含多余盘符(如 E:\\dir\\E:\\file)则返回原因, 否则 None — 小沈 2026-07-08(迁入未改逻辑)"""
    drive = os.path.splitdrive(file_path or "")[0]
    if drive:
        tail = file_path[len(drive):].lstrip("\\/")
        if re.search(r'[A-Za-z]:', tail):
            return f"路径: {file_path}中包含多余的盘符"
    return None


# ── 业务提示语(迁自 app/tools/validate/file_path_checker.py, 2026-10-16 老陈裁定) ──
#   三者皆为**纯警告**函数: 恒返 (True, None, warn|None), 只产一句提示语,
#   不判参数合法性、不判权限(合法性归 safety/path_precheck + path_legality_router, 权限归 safety 三线)。
def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入业务警告（适用于write_text_file、edit_text_file、generate_chart、screen_capture、download_file）
    纯警告函数: 恒返 (True, None, warn|None)，不判合法性不判权限

    Returns: (is_valid, error_message, warning_msg)
    """
    path = Path(file_path)
    try:
        if path.exists() and path.is_file():
            if not append:
                old_size = path.stat().st_size
                if old_size > 1024 * 1024:
                    return True, None, f"覆盖大文件({old_size}字节)，请确认"
            else:
                old_size = path.stat().st_size
                if old_size > 100 * 1024 * 1024:
                    return True, None, f"追加到超大文件({old_size}字节)，请确认"
    except PermissionError:
        return False, f"无权限访问文件: {file_path}", None
    return True, None, None


def validate_path_for_delete(file_path: str, recursive: bool = False, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    删除业务警告（适用于delete_file）
    纯警告函数: 恒返 (True, None, warn|None)，不判合法性不判权限

    Returns: (is_valid, error_msg, warning_msg)
    """
    if recursive and Path(file_path).is_dir():
        return True, None, "递归删除目录，请确认"
    if force:
        return True, None, "永久删除（绕过回收站），请确认"
    return True, None, None


def validate_path_for_overwrite(source: str, destination: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    覆盖业务警告（适用于move_file、copy_file）
    纯警告函数: 恒返 (True, None, warn|None)，不判合法性不判权限

    Returns: (is_valid, error_msg, warning_msg)
    注意：文件存在检查与实际操作之间存在时间窗口（TOCTOU），
    检查结果仅作为参考，不保证操作时的文件状态一致。
    """
    if overwrite and Path(destination).exists():
        return True, None, f"覆盖目标文件，请确认"
    return True, None, None


def validate_str_param(value, param_name: str) -> Optional[str]:
    """字符串参数基础校验 — 小欧 2026-07-05(2026-10-17 北京老陈裁定: 恢复三档专属文案, 不调 reject_reason_empty_path)
    非路径通用参数用(窗口标题/通知/host/任务名等); 路径参数非空由 safety 门前初查覆盖。
    None/非str类型/空串(含全空白) → 返回对应错误文案; None=通过。
    """
    if value is None:
        return f"参数 {param_name} 不能为 None"
    if not isinstance(value, str):
        return f"参数 {param_name} 必须为字符串, 实际类型为 {type(value).__name__}"
    if not value.strip():
        return f"参数 {param_name} 不能为空字符串"
    return None


def reject_reason_empty_path(path) -> Optional[str]:
    """路径空值/类型判定【底层原子】 — 小欧 2026-10-17(空路径必须硬拒: Path("")=="cwd", 2026-10-17 事故即由此搬走整个 backend)"""
    if not isinstance(path, str) or not path.strip():
        return f"路径不能为空(实收 {type(path).__name__}: {path!r})"
    return None


class OpCategory(Enum):
    """操作类别 → 存在性/类型要求(check_path_syntax_and_exists 的规则来源) — 小欧 2026-10-15"""
    WRITE     = "write"
    READ_FILE = "read_file"
    LIST_DIR  = "list_dir"
    EXISTS    = "exists"


_OP_RULES: Dict[OpCategory, Dict[str, Any]] = {
    OpCategory.WRITE:     {"check_exist": False, "must_be": None},
    OpCategory.READ_FILE: {"check_exist": True,  "must_be": "file"},
    OpCategory.LIST_DIR:  {"check_exist": True,  "must_be": "dir"},
    OpCategory.EXISTS:    {"check_exist": True,  "must_be": None},
}


def check_path_syntax_and_exists(
    op: OpCategory,
    path: str,
    **options: Any,
) -> Tuple[bool, Optional[str]]:
    """拼写 + 存在性/类型 判定 — 小欧 2026-07-05 建, 2026-10-17 自 path_1st_legality_check 迁入本模块
    (空值真源是 reject_reason_empty_path, 调用方须先过原子; 本函数包 try 兜底, 非法类型 fail-closed 不崩栈)"""
    try:
        return _syntax_exists_check(op, path, **options)
    except Exception as e:                      # fail-closed: 非法输入返回错误, 不冒泡崩栈
        logger.warning("[syntax_exists] 路径校验异常: %r (%s)", path, e)
        return False, f"路径校验异常: {path}"


def _syntax_exists_check(op: OpCategory, path: str, **options: Any) -> Tuple[bool, Optional[str]]:
    """拼写 + 存在性/类型 判定实体 — 2026-10-17 小欧(供上层 try 包裹)"""
    # 第1层: 格式与拼写
    drive = os.path.splitdrive(path)[0]
    if drive and not drive.startswith("\\\\"):
        if not os.path.exists(drive + "\\"):
            avail = [f"{l}:" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")]
            return False, f"驱动器: {drive}不存在。可用驱动器: {', '.join(avail)}"
    if drive:
        extra = path_has_extra_drive(path)   # 纯内存拼写检查, UNC 同样适用
        if extra:
            return False, extra
    # 只检查文件名部分(Path(...).name), 排除路径分隔符与盘符冒号
    _fname = Path(path).name
    bad = path_has_reserved_char(_fname)
    if bad:
        return False, f"文件: {_fname}名包含Windows保留字符"
    reserved = path_has_reserved_name(path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名"

    # 第2层: 存在性与类型
    rule = _OP_RULES[op]
    if rule["check_exist"]:
        p = Path(path)
        if not p.exists():
            # 允许不存在时直接过(删除幂等) —— 北京老陈 2026-07-12; allow_missing 专表此意, force 保留旧义不破坏既有调用方
            if op == OpCategory.EXISTS and (options.get("allow_missing") or options.get("force")):
                return True, None
            logger.warning("[TOCTOU] path=%s op=%s drive_exists=%s parent_exists=%s parent_dir=%s",
                           path, op.value,
                           os.path.exists(os.path.splitdrive(path)[0] + "\\") if os.path.splitdrive(path)[0] else "N/A",
                           p.parent.exists(), str(p.parent))
            return False, "路径不存在: " + path
        if rule["must_be"] == "file" and not p.is_file():
            return False, path + "不是文件"
        if rule["must_be"] == "dir" and not p.is_dir():
            return False, path + "不是目录"
    return True, None


def check_preconditions(file_path: str) -> Optional[Tuple[bool, Optional[str], Optional[str]]]:
    """空路径 / 路径穿越判定 — 小欧 2026-10-15 建, 2026-10-17 自 path_check_common 迁入本模块。
    空值判定不在本函数(唯一真源 = reject_reason_empty_path), 调用方须先过原子再调本函数。命中返回 (False, msg, "system")。
    """
    try:
        if ".." in Path(file_path).parts:          # 原始串含 .. 直接拒 — 小欧 2026-06-25
            return False, f"路径包含..,禁止路径穿越: {file_path}", "system"
        resolved = os.path.realpath(file_path)     # 再查绝对路径里的 ..(realpath 后与原串不符)
        original_resolved = os.path.realpath(os.path.dirname(file_path))
        if not resolved.startswith(original_resolved) and file_path != resolved:
            return False, f"路径穿越检测: {file_path} 解析为 {resolved}", "system"
    except Exception as e:
        logger.warning(f"[path_utils] 路径校验异常: {file_path}: {e}")
        return False, f"路径校验异常: {file_path}", "system"
    return None


def check_path_five_level(
    path: str,
    op: OpCategory = OpCategory.EXISTS,
    *,
    allow_missing: bool = False,
    enforce_zone: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    """【tool 专用】路径五级检查总入口 — 小欧 2026-10-17(仅供 delete/move/copy; 只编排不重判)
    ①空值 ②拼写 ③存在性/类型 ④穿越 四级恒生效; ⑤禁区身份本函数内联, 受 logging.debug 门控(enforce_zone 可覆盖)。
    allow_missing=True 时"不存在即已删"(删除幂等, 与工具 force 语义无关); op 定存在性口径(源 EXISTS/目标 WRITE)。
    """
    # 第1级: 空值 —— 交底层原子
    _empty = reject_reason_empty_path(path)
    if _empty:
        return False, _empty
    # 第2-3级: 拼写 + 存在性/类型 —— 恒生效
    ok, err = check_path_syntax_and_exists(op, path, allow_missing=allow_missing)
    if not ok:
        return False, err
    # 第4级: 路径穿越 —— 恒生效
    pre = check_preconditions(path)
    if pre is not None:
        return False, pre[1]
    # 第5级: 禁区身份 —— 判据委托 path_classify_category 单一真源, 本处不持名单
    #   2026-10-17 小欧 - 内联判据改调 delete_path_check.guard_forbidden_delete(硬底线单源),
    #     本处只编排; 惰性导入避免 path_utils ↔ delete_path_check 顶层循环导入。
    if enforce_zone is None:
        from app.config import get_config
        enforce_zone = bool(get_config().get("logging.debug", False))
    if enforce_zone:
        from app.safety.delete_path_check import guard_forbidden_delete
        _reason = guard_forbidden_delete(path)
        if _reason:
            return False, _reason
    return True, None


__all__ = ["to_win_long_path", "get_allowed_roots",
           "path_has_reserved_char", "path_has_reserved_name", "path_has_extra_drive",
           "validate_str_param",
           "OpCategory", "check_path_syntax_and_exists", "check_preconditions",
           "reject_reason_empty_path", "check_path_five_level"]
