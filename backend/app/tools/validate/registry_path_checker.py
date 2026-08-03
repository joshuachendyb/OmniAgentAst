# validate/registry_path_checker.py — 注册表路径业务级安全检查（集中管理）
# 小沈 2026-06-27
# 2026-07-31 - 小欧 - Bug修复: (1)恢复严格hive白名单{HKCU,HKLM}(撤销d1236eaa1对HKCR/HKU/HKCC的放行, 属安全回退, 修复test_registry_path_checker 3项既有失败); (2)路径内嵌"类hive前缀"但无效(INVALID_HIVE\.../HKEY_XXX\...)返回INVALID, 严禁静默回退HKCU | py_compile ✓

from typing import Optional, Tuple

import winreg


ALLOWED_HIVES = {"HKCU", "HKLM"}

# 已知hive简写全集(含被禁止的), 用于检测路径内嵌类hive前缀 — 小欧 2026-07-31
_KNOWN_HIVE_SHORTS = {"HKCU", "HKLM", "HKCR", "HKU", "HKCC"}

# Hive全名→简写映射(None=已知但禁止, 归一为INVALID)
HIVE_FULL_TO_SHORT = {
    "HKEY_LOCAL_MACHINE": "HKLM",
    "HKEY_CURRENT_USER": "HKCU",
    "HKEY_CLASSES_ROOT": None,
    "HKEY_USERS": None,
    "HKEY_CURRENT_CONFIG": None,
}

CRITICAL_KEY_PATTERNS = (
    r"\Software\Microsoft\Windows\CurrentVersion\Run",
    r"\Software\Microsoft\Windows\CurrentVersion\RunOnce",
    r"\Software\Microsoft\Windows\CurrentVersion\RunServices",
    r"\Software\Microsoft\Windows\CurrentVersion\RunServicesOnce",
    r"\Software\Microsoft\Windows\CurrentVersion\Policies",
    r"\Software\Microsoft\Windows\CurrentVersion\Security",
    r"\System\CurrentControlSet\Services",
    r"\Software\Microsoft\Windows NT\CurrentVersion\Winlogon",
    r"\Software\Microsoft\Internet Explorer",
    r"\Software\Google\Chrome",
)


def _normalize_key_path(key_path: str, hive: str) -> Tuple[str, str]:
    """
    规范化key_path：剥离key_path中可能带有的hive前缀，返回(key_path_clean, hive)。
    小欧 2026-07-04 修复: 增加None/类型校验
    """
    if not isinstance(key_path, str) or not key_path.strip():
        return "", hive
    path_upper = key_path.upper()
    for prefix in ALLOWED_HIVES:
        if path_upper.startswith(prefix + "\\") or path_upper.startswith(prefix + "/"):
            return key_path[len(prefix) + 1:], prefix
    for full, short in HIVE_FULL_TO_SHORT.items():
        if path_upper.startswith(full + "\\") or path_upper.startswith(full + "/"):
            if short is None:
                return key_path, "INVALID"
            return key_path[len(full) + 1:], short
    # 2026-07-31 小欧: Bug修复 — 路径内嵌"类hive前缀"但无效(已知但被禁的简写/未知HKEY_*/结尾_HIVE)归一为INVALID, 严禁静默回退HKCU导致写错位置
    first_segment = path_upper.split("\\", 1)[0].split("/", 1)[0]
    if (first_segment in _KNOWN_HIVE_SHORTS and first_segment not in ALLOWED_HIVES) \
            or first_segment.startswith("HKEY_") or first_segment.endswith("_HIVE"):
        return key_path, "INVALID"
    return key_path, hive


def validate_registry_key(key_path: str, hive: str, operation: str = "read") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    注册表路径业务级安全检查（适用于registry_read、registry_write、registry_delete）
    
    检查内容：
    1. key_path不能为空
    2. key_path不能包含路径穿越（..）
    3. key_path不能以\\结尾
    4. hive必须在白名单内（支持HKCU/HKLM简写和HKEY_*全名；HKCR/HKU/HKCC等已知hive一律拒绝）— 2026-07-31 小欧恢复严格白名单
    5. HKLM hive需要WARNING（系统级影响）
    6. 写入/删除关键键需要WARNING
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not key_path or not isinstance(key_path, str):
        return False, "key_path不能为空", None
    
    clean_key_path, resolved_hive = _normalize_key_path(key_path, hive)
    key_path = clean_key_path
    hive = resolved_hive
    
    hive_upper = hive.upper() if hive else "HKCU"
    if hive_upper not in ALLOWED_HIVES:
        return False, f"不允许的hive: {hive_upper}（仅允许HKCU/HKLM/HKCR/HKU/HKCC）", None
    
    # 检查路径穿越 — 小沈 2026-06-28
    if ".." in key_path:
        return False, "key_path包含路径穿越符，禁止访问上级目录", None

    if key_path.endswith("\\") or key_path.endswith("/"):
        return False, "key_path不能以\\结尾", None
    
    warnings = []
    if hive_upper == "HKLM":
        warnings.append(f"{hive_upper}涉及系统级注册表，请确认")
    
    if operation in ("write", "delete"):
        for pattern in CRITICAL_KEY_PATTERNS:
            if pattern.lower() in key_path.lower():
                _op = "写入" if operation == "write" else "删除"
                warnings.append(f"{_op}关键注册表键: {pattern}，请确认")
                break
    
    warning_msg = "；".join(warnings) if warnings else None
    return True, None, warning_msg


def validate_delete_safety(key_path: str, value_name: Optional[str],
                           hive: str, recursive: bool) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    注册表删除操作的安全检查（适用于registry_delete）
    """
    is_valid, error_msg, warning_msg = validate_registry_key(
        key_path, hive, operation="delete"
    )
    if not is_valid:
        return is_valid, error_msg, warning_msg
    
    hive_upper = hive.upper() if hive else "HKCU"

    if value_name is None and not recursive:
        # 仅当键确实含子键时才强制 recursive=True; 空键(仅值或无内容)允许直接删除 — 小欧 2026-07-12
        if _key_has_subkeys(key_path, hive):
            return False, "删除整个注册表键必须指定recursive=True", None
        return True, None, warning_msg

    if hive_upper == "HKLM" and not value_name:
        return True, None, "删除HKLM下的整个键，请确认"

    return True, None, warning_msg


def _key_has_subkeys(key_path: str, hive: str) -> bool:
    """判断注册表键是否含子键(不含值) — 小欧 2026-07-12"""
    from app.tools.win_registry.registry_read import ROOT_KEY_MAP, _parse_path
    try:
        full_root_key, sub_key = _parse_path(key_path, hive=hive)
        hkey = ROOT_KEY_MAP.get(full_root_key)
        if hkey is None:
            return False
        with winreg.OpenKey(hkey, sub_key, 0, winreg.KEY_READ) as key:
            try:
                winreg.EnumKey(key, 0)
                return True
            except OSError:
                return False
    except (FileNotFoundError, OSError):
        return False
