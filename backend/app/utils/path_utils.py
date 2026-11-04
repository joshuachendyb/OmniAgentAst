
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 复核落地: 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
# 2026-10-15 小欧(DRY) - 4 类目录判定收敛为 utils 唯一实现; _get_protected_roots 提为公开单源:
#   原根集合在 delete_safety._get_allowed_roots / path_safe_check 白名单构建 / 本文件三处各写一份同义逻辑,
#   且 .resolve() 用法不一致(str/Path 混流, 靠下游 realpath 兜底)。现三处统一调用本函数; 失败语义改 fail-closed。
# 2026-10-15 小欧 - 阶段五: SYSTEM_PROTECTED_DIR_NAMES / is_system_protected_path / is_disk_root /
#   is_code_root_path / is_allowed_root_itself 五符号迁往 app/safety/path_classify_category.py(职责回归安全域)。
#   本文件不再持有任何安全判定, 只剩长路径与允许根两项通用工具; 旧名不保留转发(禁止 backward).
# 2026-10-16 - 小欧 - tool去检查化: 纯内存路径格式原子(保留字符/保留名/多余盘符)下沉至此。
#   口径: 纯拼写判定, 无IO、无白名单、无授权语义, 故不是"安全判定", tools/safety 均可导入;
#   tools 禁 import safety, 故 tool 内派生路径检查只能调本层。
# 2026-10-17 小欧 - 迁入 check_path_syntax_and_exists(自 path_1st_legality_check)与 check_preconditions(自 path_check_common);
#   新增 reject_reason_empty_path(空值唯一真源)与 check_path_five_level(tool 专用五级总入口, delete/move/copy 共用; 禁区判定受 logging.debug 门控)。
#   ★更正上方 10-16 记载: 按 B 方案本模块已可引用 app.safety.path_classify_category(仅转发禁区判据, 不持名单)。
# 2026-10-17 小欧 - 迁入 check_path_syntax_and_exists 与 check_preconditions, 新增空值原子 reject_reason_empty_path 与 tool 专用五级总入口 check_path_five_level
# 2026-10-17 - 小欧 - check_path_five_level 第级内联禁区判据改调 delete_path_check.guard_forbidden_delete(硬底线单源,
#   惰性导入避免顶层循环); 本层不再自持禁区判据代码, 只编排。
# 2026-10-18 小欧 - 撤销第级: check_path_five_level 更名 check_path_four_level, 删 enforce_zone 形参与
#   logging.debug 门控; 本模块回归纯合法性(空/拼写/存在/穿越), 不再持任何安全判定(符本文件章程)。
#   删除硬底线 guard_forbidden_delete 移回 delete_file 工具自持(仍受 logging.debug 门控)。 — 小欧-2026-10-18
# 2026-10-19 小欧 - check_preconditions 返回契约归一: 三元组→Optional[str](违规原因文案 / 通过 None)。
#   原第三元素恒为旧 category 字面量 "system", 目录数组化后它已无对应枚举; 安全三线把"非法输入"一律
#   归 SCOPE_FORBIDDEN_SYSTEM 是各线各自的策略, 不应由本工具函数越位代言。调用方改
#   `reject_reason_empty_path(fp) or check_preconditions(fp)` 组合取原因; 归归属由 safety 层定。
# 2026-10-26 小沈 - 新增has_path_traversal(路径穿越轻量判定,工具层专用,按\和/切分任一段==".."即命中,纯内存不做realpath);
#   新增get_output_dir(输出目录=project_root/output); 汇集散落各处的..穿越检查(DRY)。
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
from typing import Any, Dict, Optional, Tuple

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


def absolutize_path(path: str, base: str) -> str:
    r"""相对路径绝对化(工具层公用) — 小欧 2026-10-19

    绝对路径 → `os.path.abspath(path)`
    相对路径 → `os.path.abspath(os.path.join(base, path.lstrip("/\\")))`
    `base` 由调用方按语义传入(工具工作区 / 下载目录 / 源父目录等), 本函数不内置任何工具专属基准;
    不做路径穿越处理。
    """
    p = str(path)
    if os.path.isabs(p):
        return os.path.abspath(p)
    return os.path.abspath(os.path.join(base, p.lstrip("/\\")))


def get_output_dir() -> str:
    r"""输出目录(工具层公用) — 小沈 2026-10-26

    = `get_config().get_project_root()/output`(未配 project_root 时回落用户主目录)。
    generate_chart 等输出工具共用同一基准(单源), 不各自拼接。
    """
    from app.config import get_config
    return os.path.join(get_config().get_project_root(), "output")


# 2026-10-19 小欧 - 目录名单收口: get_allowed_roots 迁 app/safety/path_dir_lists
#   (_collect_white_list_scope_entries), 本处删除(禁 backward 留转发壳)。路径名单是安全层单源。


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


# ── 业务提示语(迁自 app/tools/validate/file_path_checker.py, 2026-10-16) ──
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
    """字符串参数基础校验 — 小欧 2026-07-05(2026-10-17 小欧: 恢复三档专属文案, 不调 reject_reason_empty_path)
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
            # 允许不存在时直接过(删除幂等) —  2026-07-12; allow_missing 专表此意, force 保留旧义不破坏既有调用方
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


def has_path_traversal(path: str) -> bool:
    """路径穿越轻量判定 — 小沈 2026-10-26

    工具层专用: 统一汇集散落各处的 ".." 分段检查。
    判定逻辑: 路径按 \\ 和 / 切分后任一段 == ".." 即命中。
    与 check_preconditions 区别: 不做 realpath 解析(轻量/纯内存), 适合工具入口快速拦截;
    安全线仍用 check_preconditions(含 realpath 抓符号链接穿越)。

    小沈 2026-10-26
    """
    if not path:
        return False
    return any(p == ".." for p in path.replace("\\", "/").split("/"))


def check_preconditions(file_path: str) -> Optional[str]:
    """路径穿越判定 — 小欧 2026-10-15 建 / 2026-10-17 迁入 / 2026-10-19 返回契约归一

    命中返回违规原因文案, 通过返回 None。空值判定不在本函数(唯一真源 = reject_reason_empty_path),
    调用方须先过该原子再调本函数; 归哪一档归属由 safety 层决定, 本函数只判"是否非法"。
    """
    try:
        if ".." in Path(file_path).parts:          # 原始串含 .. 直接拒 — 小欧 2026-06-25
            return f"路径包含..,禁止路径穿越: {file_path}"
        resolved = os.path.realpath(file_path)     # 再查绝对路径里的 ..(realpath 后与原串不符)
        original_resolved = os.path.realpath(os.path.dirname(file_path))
        if not resolved.startswith(original_resolved) and file_path != resolved:
            return f"路径穿越检测: {file_path} 解析为 {resolved}"
    except Exception as e:
        logger.warning(f"[path_utils] 路径校验异常: {file_path}: {e}")
        return f"路径校验异常: {file_path}"
    return None


def check_path_four_level(
    path: str,
    op: OpCategory = OpCategory.EXISTS,
    *,
    allow_missing: bool = False,
) -> Tuple[bool, Optional[str]]:
    """【tool 专用】路径四级合法性检查总入口 — 小欧 2026-10-17 建(五级) / 2026-10-18 降为四级
    空值 拼写 存在性/类型 穿越 — 四级恒生效, 仅判合法性, 不判任何权限/禁区。
    禁区与权限判定唯一归 safety 层(action_kind 四线); 删除硬底线 guard_forbidden_delete 由 delete 工具自持。
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
        return False, pre
    return True, None


__all__ = ["to_win_long_path", "absolutize_path", "get_output_dir",
           "path_has_reserved_char", "path_has_reserved_name", "path_has_extra_drive",
           "validate_str_param",
           "OpCategory", "check_path_syntax_and_exists", "check_preconditions",
           "reject_reason_empty_path", "check_path_four_level",
           "has_path_traversal"]
