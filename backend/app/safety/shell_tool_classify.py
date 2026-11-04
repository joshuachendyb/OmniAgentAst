# -*- coding: utf-8 -*-
"""shell_tool_classify — shell 工具分类与注册表键探测(单一职责 · 零状态) — 小欧 2026-10-18

职责: 判断某工具名是否 shell 命令类工具(executor 预检按此分流 file_op / shell);
      只读探测注册表键是否存在(registry 静态分析, 不做任何写/删)。
      **只做分类与只读探测, 不判动作、不判权限。**

编辑历史:
2026-10-18 - 小欧 - 新建(SRP): 自 shell_command_process.py 拆出"工具分类"单一关注点。

分层: 仅依赖 app.tools.tools_alias_mapper(契约) + 标准库; 不 import 上层。
"""
from app.tools.tools_alias_mapper import normalize_tool_name


def is_shell_tool(tool_name: str) -> bool:
    """是否 shell 命令类工具(executor 预检按此分流 file_op / shell) — 小欧 2026-10-10

    迁自 executor.py:70。调用期依赖 normalize_tool_name 已在文件头显式导入,
    杜绝「import 通过但调用 NameError」。
    """
    _shell = frozenset({"bash"})  # 2026-10-02 小欧 - 随注册名改名
    return normalize_tool_name(tool_name) in _shell


def shell_registry_key_exists(reg_path: str) -> bool:
    """registry 静态分析: winreg 标准库只读探测键存在性, 不做任何写/删。

    2026-10-16 小欧: 根键名归一去冒号, 兼容 `HKLM:\\Software`(PowerShell 冒号形态)与 `HKLM\\Software`(reg.exe 形态)。
    """
    try:
        import winreg
    except ImportError:
        return False
    parts = reg_path.replace("/", "\\").split("\\")
    root_map = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER,
                "HKCR": winreg.HKEY_CLASSES_ROOT, "HKU": winreg.HKEY_USERS,
                "HKCC": winreg.HKEY_CURRENT_CONFIG}
    root = root_map.get(parts[0].upper().rstrip(":"))
    if root is None or len(parts) < 2:
        return False
    try:
        with winreg.OpenKey(root, parts[1].lstrip("\\")):
            return True
    except OSError:
        return False


__all__ = ["is_shell_tool", "shell_registry_key_exists"]
