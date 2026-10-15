# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-27 - 小沈 - 创建: tool内部路径业务级检查集中管理，散落校验函数归并统一
# 2026-07-04 - 小欧 - 重构统一入口 + 注释说明
# 2026-07-09 - 北京老陈 - 交叉引用注释统一
# 2026-07-26 - 小欧 - hint_for_read_error加MemoryError分支, OOM时提示分批读取
# 2026-07-26 - 小欧 - 迁移: sql_error_hint/hint_for_data_error从tool_constants迁入(file_path_checker同属检查类)
# 2026-07-26 - 小沈 - 修复: sqlite3/pandas函数级import提升模块级; PermissionError冗余分支删(矫正,确认删除); hint_for_read_error入__all__
# 2026-07-29 - 小欧 - ERR_FILE_READ_FAILED 三堂会审: hint_for_read_error 文件不存在提示改为引导用find/listdir确认存在
# 2026-08-02 - 小欧 - 加固validate_not_system_path: 新增磁盘根目录硬阻断(C:\), 修复盘后单级目录漏网(原path_after_drive无前导斜杠导致C:\\Windows不拦, 现用os.path.splitdrive规范化判断)
# 2026-08-09 - 小欧 - task006 落地(sql_error_hint): 新增多语句识别分支"one statement at a time" → 精准hint"SQLite仅支持单条语句", 打破LLM多语句SQL低效重试循环
# 2026-08-09 - 小欧 - task006 落地(sql_error_hint): 新增 UNIQUE 分支 — "unique constraint"/"is not unique" → 引导查现值再UPDATE/INSERT
#   病根: UNIQUE 约束失败回落"请检查SQL语法", LLM 无法据此自查(日志 `users.id` 重键 253 处), 陷入插重键低效循环
#   方案: 一分支全覆盖 3 个 SQL 工具(execute_sql/query_sql/get_db_schema 共用 sql_error_hint, DRY); 验证不误伤其它6分支
# 2026-08-09 - 小欧 - 三堂会审复审: UNIQUE 匹配词收紧 "unique constraint"→"unique constraint failed" — 原词会误命中
#   "ON CONFLICT clause does not match any PRIMARY KEY or UNIQUE constraint"(LLM写错ON CONFLICT子句), 收紧后精准只匹配
#   sqlite 真实报错 "UNIQUE constraint failed: table.column"
# 2026-08-13 - 小欧 - A5 职责拆分: hint_* 错误提示函数(permission_error_hint/hint_for_write_error/
#   hint_for_read_error/sql_error_hint/hint_for_data_error)整段复制迁入 app/tools/toolhelper/error_hints.py，
#   本文件仅保留路径/参数校验。同步删除 sqlite3/_pd(pandas) 死依赖与 __all__ 中 hint 项。
#   所有调用方导入路径已改 app.tools.toolhelper.error_hints。
# 2026-10-14 - 小欧 - SA8标注: 本文件=权限信任框架SA8(工具体内业务校验validate_path_for_write/delete/overwrite,执行第8步,只判参数合法性不判权限; 硬底线为delete_file._guard_forbidden_delete 镜像A族) — 小欧-2026-10-14
# 2026-10-14 - 小欧 - 系统目录名单归一: WINDOWS_SYSTEM_DIRS 已删除(权限判定移出本层后成死常量), 判定单源见 app/utils/path_utils.py
# 2026-10-14 - 小欧 - 文档[33] 4.12-B: 判定与名单改从 app/utils/path_utils.py 导入(老陈裁定「纯路径工具函数, 独立到 utils」), 解除工具层对安全层依赖; 工具层与安全层同一对象非各自复制
# 2026-10-14 北京老陈裁定(全局收敛) - 本层移除目录权限判定(validate_not_system_path 与 WINDOWS_SYSTEM_DIRS 一并删除):
#   4 类目录权限(系统目录/磁盘根/代码库根/受保护根)统一由 Safety 层单一决策, 硬底线由 delete_file 镜像 A 族。
#   本层只判参数合法性, 原第2层删除后层号顺延为 1/2/3(不留跳号)。
# 2026-10-15 北京老陈裁定(全局收敛·清尾) - validate_path_for_extract 整函数删除, 本层 path_utils 导入整体删除:
#   实测 Safety 对 dest=C:\Windows / C:\ProgramData 均 blocked 硬拦, 该 warning 既不阻断也执行不到, 属纯冗余判权限。
#   本层至此零权限判定, 4 类目录权限 100% 由 Safety 单一决策 + delete 镜像 A 族。
"""
validate/file_path_checker.py — tool内部路径业务级检查（集中管理）

工具层（本文件）：非空/保留字符/保留名/系统目录/存在性+类型/业务警告
[SA8] 权限信任框架第8步(工具体内业务校验, 与delete_file._guard_forbidden_delete并列最后防线) — 小欧-2026-10-14
Safety层（app/safety/tool_safety_checker.py + app/safety/path_guard.py）：
  路径黑名单/白名单/路径穿越/权限校验 — 两层独立运行、互不调用
"""

import logging
import os
import re
import string
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# 2026-10-15 北京老陈裁定: 本层不判权限, path_utils 导入整体删除(权限单源在 Safety 层)。
# 2026-10-15 - 小欧 - 三堂会审(第1、2层抽出): validate_path_layers12 新增, 本文件第1层(格式)第2层(存在/类型)
#   自 validate_path **逐字复制**移入(能复制不重写, 逻辑零改动), validate_path 改为调本函数 + 保留第3层警告。
#   动因: SA1 门前初查只需前两层, 原先整调 validate_path 会连带跑第3层 —— 产出的 warning 全被丢弃,
#   却付出 exists()+stat()/is_dir() 的无谓文件系统 IO。抽出后前门零 IO, 两处共用一份实现(改一处两处齐知)。
#   返回二元组(无 warning 通道): 门前初查只取 (is_valid, err), 第3层语义仍只归 validate_path。

logger = logging.getLogger(__name__)

__all__ = [
    "validate_path_for_write", "validate_path_for_delete", "validate_path_for_overwrite",
    "OpCategory", "validate_path", "validate_str_param",
]

_WINDOWS_RESERVED = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5',
                     'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4',
                     'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}


def _has_windows_reserved_name(file_path: str) -> Optional[str]:
    """检查路径是否包含Windows保留名 — 小欧 2026-07-04"""
    try:
        p = Path(file_path)
        for part in p.parts:
            name = part.split('.')[0].upper()
            if name in _WINDOWS_RESERVED:
                return part
    except Exception:
        pass
    return None


def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入操作的路径业务级检查（适用于write_text_file、edit_text_file及所有写入类工具）
    工具层校验：非空/保留字符/保留名（仅警告，不阻断）
    Safety层（app/safety/path_guard.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名", None
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
    删除操作的路径业务级检查（适用于delete_file）
    工具层校验：非空/保留字符/保留名（仅递归/强制警告）
    Safety层（app/safety/path_guard.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(file_path, str) or not file_path.strip():
        return False, "文件路径不能为空", None
    reserved = _has_windows_reserved_name(file_path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名", None
    if recursive and Path(file_path).is_dir():
        return True, None, "递归删除目录，请确认"
    if force:
        return True, None, "永久删除（绕过回收站），请确认"
    return True, None, None


def validate_path_for_overwrite(source: str, destination: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    覆盖操作的路径业务级检查（适用于move_file、copy_file）
    工具层校验：非空（仅覆盖警告）
    Safety层（app/safety/path_guard.py）独立运行：黑名单/白名单/路径穿越/权限
    
    Returns: (is_valid, error_msg, warning_msg)
    注意：文件存在检查与实际操作之间存在时间窗口（TOCTOU），
    检查结果仅作为参考，不保证操作时的文件状态一致。
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    if not isinstance(source, str) or not source.strip():
        return False, "源路径不能为空", None
    if not isinstance(destination, str) or not destination.strip():
        return False, "目标路径不能为空", None
    if overwrite and Path(destination).exists():
        return True, None, f"覆盖目标文件，请确认"
    return True, None, None





# 2026-10-14 北京老陈裁定: validate_not_system_path / WINDOWS_SYSTEM_DIRS 已删除 ——
#   权限判定收归 Safety 层单一决策, 硬底线由 delete_file._guard_forbidden_delete 镜像 A 族;
#   本层只管参数合法性(格式/存在性/类型/大小/递归)。名单与判定留在本层即是无调用者的死代码(YAGNI)。


from enum import Enum
from typing import Any


class OpCategory(Enum):
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

_WINDOWS_RESERVED_CHARS = '<>:"/\\|?*'


def validate_path_layers12(
    op: OpCategory,
    path: str,
    **options: Any,
) -> Tuple[bool, Optional[str]]:
    """第1层格式 + 第2层存在性/类型 — 小欧 2026-10-15

    自 validate_path 第1、2层**逐字抽出**(能复制不重写), 供两处共用:
      validate_path —— 本入口只在正常跑检查(编排层)
      path_check_entry.precheck_path_legality —— SA1 门前初查(第3层警告不要它)

    第3层(业务警告 content/append/recursive/force/overwrite)只产 warning 不产 error,
    且依赖执行期才拿得全的参数, 故不在本入口内。
    幂等删除(force=True)照搬第2层语义: 不存在即视为已删。
    """
    # 第1层
    if not isinstance(path, str) or not path.strip():
        return False, "路径不能为空"
    # 盘符存在性检查（最先做，最外层的快速否决） — 小欧 2026-07-04
    drive = os.path.splitdrive(path)[0]
    if drive:
        if not os.path.exists(drive + "\\"):
            avail = [f"{l}:" for l in string.ascii_uppercase if os.path.exists(f"{l}:\\")]
            return False, f"驱动器: {drive}不存在。可用驱动器: {', '.join(avail)}"
        # 检测路径中间是否出现多余盘符（如 E:\dir\E:\file）— 小沈 2026-07-08
        _tail = path[len(drive):]
        if re.search(r'[A-Za-z]:', _tail.lstrip("\\/")):
            return False, f"路径: {path}中包含多余的盘符"
    # 只检查文件名部分（Path(...).name），排除路径分隔符和盘符:号 — 小欧 2026-07-04
    _fname = Path(path).name
    if any(c in _fname for c in _WINDOWS_RESERVED_CHARS):
        return False, f"文件: {_fname}名包含Windows保留字符"
    reserved = _has_windows_reserved_name(path)
    if reserved:
        return False, f"文件: {reserved}名包含Windows保留名"

    # 第2层
    rule = _OP_RULES[op]
    if rule["check_exist"]:
        p = Path(path)
        if not p.exists():
            # 幂等删除: force=True 时不存在即视为已删除,不报错(delete 专用) — 北京老陈 2026-07-12
            if op == OpCategory.EXISTS and options.get("force"):
                return True, None
            logger.warning("[TOCTOU] path=%s op=%s drive_exists=%s parent_exists=%s parent_dir=%s",
                           path, op.value,
                           os.path.exists(os.path.splitdrive(path)[0] + "\\") if os.path.splitdrive(path)[0] else "N/A",
                           p.parent.exists(), str(p.parent))
            return False, "路径不存在: " + path
        if rule["must_be"] == "file" and not p.is_file():
            return False, path +"不是文件"
        if rule["must_be"] == "dir" and not p.is_dir():
            return False,  path +"不是目录"
    return True, None


def validate_path(
    op: OpCategory,
    path: str,
    **options: Any,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    统一路径前置校验（编排层，本文件调所有 validate_path_for_*）
    工具层校验：非空/保留字符/保留名/盘符存在性/存在性+类型/业务警告
    2026-10-14 北京老陈裁定: 目录权限(系统目录/磁盘根/代码库根/受保护根)已移出本层 ——
      权限由 Safety 层单一决策, 硬底线由 delete_file._guard_forbidden_delete 镜像 A 族。
    Safety层（app/safety/path_guard.py）后续独立运行：黑名单/白名单/路径穿越/权限校验
    小欧 2026-07-04

    第1层 基础校验（ALL）：非空 + 保留字符 + 保留名 + 盘符存在性
    第2层 存在性+类型（WRITE跳过）：exists / is_file / is_dir
    第3层 业务警告：content/append → write；recursive/force → delete；overwrite+source → overwrite（extract→系统目录警告已删, Safety 硬拦）

    第1、2层本体在 validate_path_layers12(2026-10-15 抽出: 门前初查只需前两层, 逐字复制未改逻辑),
    本函数 = 前两层(单源) + 第3层警告。

    Returns: (is_valid, error_msg, warning_msg)
    """
    # 第1、2层（单一真源: validate_path_layers12）
    ok, err = validate_path_layers12(op, path, **options)
    if not ok:
        return False, err, None

    # 2026-10-14 北京老陈裁定: 本层只判参数合法性(格式/存在性/类型/大小/递归), 不判权限。
    #   目录权限(系统目录/磁盘根/代码库根/受保护根)统一由 Safety 层决策, 硬底线由
    #   delete_file._guard_forbidden_delete 镜像 A 族 —— 权限判定权收敛到唯一一处。

    # 第3层
    warnings = []
    if op == OpCategory.WRITE or "content" in options:
        _, _, w = validate_path_for_write(path, options.get("content", ""), options.get("append", False))
        if w: warnings.append(w)
    if op == OpCategory.EXISTS and (options.get("recursive") or options.get("force")):
        _, _, w = validate_path_for_delete(path, options.get("recursive", False), options.get("force", False))
        if w: warnings.append(w)
    if options.get("overwrite") and "source" in options:
        _, _, w = validate_path_for_overwrite(options["source"], path, True)
        if w: warnings.append(w)

    return True, None, "; ".join(warnings) if warnings else None


def validate_str_param(value: Any, param_name: str) -> Optional[str]:
    """字符串参数基础校验 — 小欧 2026-07-05
    None/非str类型/空串(含全空白) → 返回错误信息
    None=通过, str=错误信息
    """
    if value is None:
        return f"参数 {param_name} 不能为 None"
    if not isinstance(value, str):
        return f"参数 {param_name} 必须为字符串, 实际类型为 {type(value).__name__}"
    if not value.strip():
        return f"参数 {param_name} 不能为空字符串"
    return None
