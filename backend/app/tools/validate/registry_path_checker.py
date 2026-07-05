# validate/registry_path_checker.py — 注册表路径业务级安全检查（集中管理）
# 小沈 2026-06-27

from typing import Optional, Tuple


ALLOWED_HIVES = {"HKCU", "HKLM"}

# Hive全名→简写映射
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
    return key_path, hive


def validate_registry_key(key_path: str, hive: str, operation: str = "read") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    注册表路径业务级安全检查（适用于registry_read、registry_write、registry_delete）
    
    检查内容：
    1. key_path不能为空
    2. key_path不能包含路径穿越（..）
    3. key_path不能以\\结尾
    4. hive必须在白名单内（支持HKLM/HKCU简写和HKEY_*全名）
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
        return False, f"不允许的hive: {hive_upper}（仅允许HKCU、HKLM）", None
    
    # 检查路径穿越 — 小沈 2026-06-28
    if ".." in key_path:
        return False, "key_path包含路径穿越符，禁止访问上级目录", None

    if key_path.endswith("\\") or key_path.endswith("/"):
        return False, "key_path不能以\\结尾", None
    
    warnings = []
    if hive_upper == "HKLM":
        warnings.append("HKLM涉及系统级注册表，请确认")
    
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
        return False, "删除整个注册表键必须指定recursive=True", None
    
    if hive_upper == "HKLM" and not value_name:
        return True, None, "删除HKLM下的整个键，请确认"
    
    return True, None, warning_msg
