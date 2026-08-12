# tests/validate/test_registry_path_checker.py
# 小沈 2026-06-27
# 2026-07-31 - 小欧 - 新增BugC覆盖: 路径内嵌无效hive前缀(INVALID_HIVE\.../HKEY_XXX\.../被禁简写HKCR\...)拒绝而非静默回退; 中间段HKEY_*子键名不受影响

import pytest
from app.tools.validate.registry_path_checker import (
    validate_registry_key,
    validate_delete_safety,
    _normalize_key_path,
)


# ============================================================
# _normalize_key_path
# ============================================================

class TestNormalizeKeyPath:
    def test_no_hive_prefix(self):
        key_path = r"Software\Microsoft\Windows"
        result_path, result_hive = _normalize_key_path(key_path, "HKCU")
        assert result_path == key_path
        assert result_hive == "HKCU"

    def test_hklm_prefix_shorthand(self):
        key_path = r"HKLM\Software\Microsoft"
        result_path, result_hive = _normalize_key_path(key_path, "HKCU")
        assert result_path == r"Software\Microsoft"
        assert result_hive == "HKLM"

    def test_hkcu_prefix_shorthand(self):
        key_path = r"HKCU\Software\Microsoft"
        result_path, result_hive = _normalize_key_path(key_path, "HKLM")
        assert result_path == r"Software\Microsoft"
        assert result_hive == "HKCU"

    def test_hklm_prefix_full(self):
        key_path = r"HKEY_LOCAL_MACHINE\Software\Microsoft"
        result_path, result_hive = _normalize_key_path(key_path, "HKCU")
        assert result_path == r"Software\Microsoft"
        assert result_hive == "HKLM"

    def test_hkcu_prefix_full(self):
        key_path = r"HKEY_CURRENT_USER\Software\Microsoft"
        result_path, result_hive = _normalize_key_path(key_path, "HKLM")
        assert result_path == r"Software\Microsoft"
        assert result_hive == "HKCU"

    def test_hkey_classes_root_prefix(self):
        key_path = r"HKEY_CLASSES_ROOT\.txt"
        result_path, result_hive = _normalize_key_path(key_path, "HKCU")
        assert result_path == key_path
        assert result_hive == "INVALID"

    def test_hkcu_prefix_forward_slash(self):
        key_path = r"HKCU/Software/Microsoft"
        result_path, result_hive = _normalize_key_path(key_path, "HKLM")
        assert result_path == r"Software/Microsoft"
        assert result_hive == "HKCU"

    def test_invalid_hive_prefix_in_path(self):
        """路径内嵌无效hive前缀(INVALID_HIVE\\...)归一INVALID, 不再静默回退HKCU — 小欧 2026-07-31 BugC"""
        result_path, result_hive = _normalize_key_path(r"INVALID_HIVE\SomeKey", "HKCU")
        assert result_hive == "INVALID"

    def test_unknown_hkey_prefix_in_path(self):
        """路径内嵌未知HKEY_前缀归一INVALID — 小欧 2026-07-31 BugC"""
        result_path, result_hive = _normalize_key_path(r"HKEY_INVALID\SomeKey", "HKCU")
        assert result_hive == "INVALID"

    def test_disallowed_hive_shortcut_in_path(self):
        """路径内嵌被禁简写(HKCR\\...)归一INVALID — 小欧 2026-07-31 BugC"""
        result_path, result_hive = _normalize_key_path(r"HKCR\Software\X", "HKCU")
        assert result_hive == "INVALID"

    def test_middle_hkey_segment_is_normal_subkey(self):
        """中间段HKEY_*是普通子键名, 不受前缀检测影响 — 小欧 2026-07-31 BugC"""
        key_path = r"Software\HKEY_FOO\Bar"
        result_path, result_hive = _normalize_key_path(key_path, "HKCU")
        assert result_path == key_path
        assert result_hive == "HKCU"


# ============================================================
# validate_registry_key
# ============================================================

class TestValidateRegistryKey:
    def test_empty_key_path(self):
        ok, err, warn = validate_registry_key("", "HKCU")
        assert ok is False
        assert err == "key_path不能为空"
        assert warn is None

    def test_invalid_hive(self):
        ok, err, warn = validate_registry_key(r"Software", "HKCR")
        assert ok is False
        assert "不允许的hive" in err
        assert "HKCR" in err
        assert warn is None

    def test_path_traversal(self):
        ok, err, warn = validate_registry_key(r"Software\..\Windows", "HKCU")
        assert ok is False
        assert "key_path包含路径穿越符，禁止访问上级目录" in err
        assert warn is None

    def test_trailing_backslash(self):
        ok, err, warn = validate_registry_key("Software\\Microsoft\\", "HKCU")
        assert ok is False
        assert "key_path不能以\\结尾" in err
        assert warn is None

    def test_hklm_warning(self):
        ok, err, warn = validate_registry_key(r"Software\Microsoft", "HKLM")
        assert ok is True
        assert err is None
        assert warn is not None
        assert "系统级注册表" in warn

    def test_read_does_not_trigger_critical_patterns(self):
        ok, err, warn = validate_registry_key(
            r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU", operation="read"
        )
        assert ok is True
        assert err is None
        # read should NOT produce a warning for critical key patterns
        assert warn is None

    def test_write_triggers_critical_key_warning(self):
        ok, err, warn = validate_registry_key(
            r"\Software\Microsoft\Windows\CurrentVersion\Run", "HKCU", operation="write"
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "写入" in warn
        assert "Run" in warn

    def test_delete_triggers_critical_key_warning(self):
        ok, err, warn = validate_registry_key(
            r"\Software\Microsoft\Windows\CurrentVersion\Run", "HKCU", operation="delete"
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "删除" in warn
        assert "Run" in warn

    def test_valid_hkcu_no_warning(self):
        ok, err, warn = validate_registry_key(r"Software\MyApp", "HKCU")
        assert ok is True
        assert err is None
        assert warn is None

    def test_normalize_strips_hklm_prefix_and_warns(self):
        ok, err, warn = validate_registry_key(
            r"HKLM\Software\MyApp", "HKCU"
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "系统级注册表" in warn

    def test_invalid_hive_from_normalize(self):
        ok, err, warn = validate_registry_key(
            r"HKEY_CLASSES_ROOT\.txt", "HKCU"
        )
        assert ok is False
        assert "不允许的hive" in err
        assert "INVALID" in err
        assert warn is None

    def test_invalid_hive_prefix_in_path_rejected(self):
        """路径内嵌INVALID_HIVE\\... 整体拒绝 — 小欧 2026-07-31 BugC"""
        ok, err, warn = validate_registry_key(
            r"INVALID_HIVE\SomeKey", "HKCU"
        )
        assert ok is False
        assert "不允许的hive" in err
        assert warn is None

    def test_hkcr_prefix_in_path_rejected(self):
        """路径内嵌HKCR\\... 整体拒绝(被禁hive) — 小欧 2026-07-31 BugC"""
        ok, err, warn = validate_registry_key(
            r"HKCR\Software\X", "HKCU"
        )
        assert ok is False
        assert "不允许的hive" in err
        assert warn is None

    def test_hkcu_prefix_is_normalized(self):
        ok, err, warn = validate_registry_key(
            r"HKCU\Software\MyApp", "HKLM"
        )
        assert ok is True
        assert err is None
        assert warn is None

    def test_chrome_critical_key_write(self):
        ok, err, warn = validate_registry_key(
            r"\Software\Google\Chrome\Extensions", "HKCU", operation="write"
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "写入" in warn


# ============================================================
# validate_delete_safety
# ============================================================

class TestValidateDeleteSafety:
    def test_delete_no_value_not_recursive(self):
        # 2026-07-12 对齐: 仅当键确实含子键时才强制 recursive=True; 空键/不存在键允许直接删除
        # 用真实含有子键的键(HKCU\Software)验证安全拦截逻辑
        ok, err, warn = validate_delete_safety(
            r"Software", None, "HKCU", recursive=False
        )
        assert ok is False
        assert "删除整个注册表键必须指定recursive=True" in err
        assert warn is None

    def test_delete_empty_key_not_recursive_allowed(self):
        # 空键/不存在键(无子键)允许不带 recursive 删除 — 2026-07-12 行为变更
        ok, err, warn = validate_delete_safety(
            r"Software\MyApp", None, "HKCU", recursive=False
        )
        assert ok is True
        assert err is None

    def test_hklm_delete_no_value_warning(self):
        ok, err, warn = validate_delete_safety(
            r"Software\MyApp", None, "HKLM", recursive=True
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "删除HKLM" in warn

    def test_normal_delete_with_value_name(self):
        ok, err, warn = validate_delete_safety(
            r"Software\MyApp", "SomeValue", "HKCU", recursive=False
        )
        assert ok is True
        assert err is None
        assert warn is None

    def test_delegates_basic_validation(self):
        ok, err, warn = validate_delete_safety(
            r"Software\..\Windows", "SomeValue", "HKCU", recursive=False
        )
        assert ok is False
        assert "key_path包含路径穿越符，禁止访问上级目录" in err
        assert warn is None

    def test_delete_critical_key_warning(self):
        ok, err, warn = validate_delete_safety(
            r"\Software\Microsoft\Windows\CurrentVersion\Run",
            "SomeValue", "HKCU", recursive=False
        )
        assert ok is True
        assert err is None
        assert warn is not None
        assert "删除" in warn
        assert "Run" in warn
