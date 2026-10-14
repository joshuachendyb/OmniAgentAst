
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-11 - 小欧 - 创建文件: 长路径工具 to_win_long_path, 从 operation_backup._win_long_path 提为全局公用,
#   解决深嵌套目录(递归自复制套娃)备份/清理时 WinError 206 路径超长整体失败的历史事故闭环
#   (备份长路径已支持, 清理链路 operation_cleanup 同样需长路径, 否则超长备份永远清不掉→回收站永久膨胀)
# 2026-08-11 - 小欧 - 三堂会审复核落地: 补 is_absolute() 前置守卫, 相对路径不加 \\?\ 前缀,
#   与docstring"非绝对路径保持原样"承诺对齐(原代码相对路径会生成非法 \\?\relative 路径)
# 2026-10-14 - 小欧 - 文档[33] 4.12-B: 迁入 SYSTEM_PROTECTED_DIR_NAMES 与 is_system_protected_path(老陈裁定「纯路径工具函数, 独立到 utils」); 名单与判定同处一地以免 utils 反向依赖 app.tools
"""
path_utils — 路径处理工具

职责: Windows 长路径支持、系统保护目录判定等路径相关公共函数

2026-10-14 小欧 - 文档[33] 4.12-B: SYSTEM_PROTECTED_DIR_NAMES 与 is_system_protected_path 由
tool_constants / security.path_safe_check 一并下沉(老陈裁定「纯路径工具函数, 独立到 utils」)。
名单与判定必须同处一地: 名单留上层则 utils 要 import app.tools, 即分层倒挂。
"""
import os
from pathlib import Path

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


def is_system_protected_path(file_path: str) -> bool:
    r"""路径是否落在 Windows 系统保护目录下(判定**单源**, 全仓共用) — 小欧 2026-10-14

    判定法: 展开(`expanduser` → `realpath`)后取**盘符后的第一段**(`parts[1]`), 比对
    SYSTEM_PROTECTED_DIR_NAMES(大小写不敏感)。异常不静默放行, 一律判为受保护。

    2026-10-14 北京老陈裁定「必须是同一个逻辑」: 此前安全层与工具层各判各的、各持一份名单,
    结论相反(C:\system32 安全层放行/工具层拒绝)。现消费方两处:
      ① 安全层 `path_safe_check._is_forbidden_path`(SA5 判权限)
      ② 工具层 `file_path_checker.validate_not_system_path`(绕过 Safety 直调工具的最后防线)
    单源落 utils 而非安全层: 「最后防线不能依赖前面的防线」, 且 tools→safety 越层不可清(文档[33] 4.12-B)。
    """
    try:
        parts = Path(os.path.realpath(os.path.expanduser(file_path))).parts
        return len(parts) > 1 and parts[1].lower() in SYSTEM_PROTECTED_DIR_NAMES
    except Exception:
        # 异常不静默放行: 判定为受保护(调用方据此硬拦), 与 _is_forbidden_path 异常口径一致
        return True
