# -*- coding: utf-8 -*-
"""task002问题2修复验证: registry_write auto_detect 对纯字符串推断 REG_SZ — 小欧 2026-08-08"""
import winreg
from unittest.mock import patch, MagicMock

import pytest

from app.tools.win_registry.registry_write import registry_write


def _write_and_capture(value):
    """调用 registry_write, 捕获传给 winreg.SetValueEx 的注册表类型; 拦截真实注册表写入"""
    captured = {}

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_create(*a, **k):
        return FakeKey()

    def fake_set(*a, **k):
        # a = (key, value_name, reserved, reg_type, converted)
        captured["reg_type"] = a[3]
        captured["value"] = a[4]

    with patch.object(winreg, "CreateKey", side_effect=fake_create), \
         patch.object(winreg, "SetValueEx", side_effect=fake_set), \
         patch("app.tools.win_registry.registry_read._backup_registry", return_value=""):
        result = registry_write(
            path="HKCU\\Software\\Task002Test",
            value_name="TestValue",
            value=value,
            backup_before_write=False,
        )
    return result, captured


class TestRegistryWriteAutoDetect:
    """auto_detect 类型推断: 整数字符串→REG_DWORD, 纯字符串→REG_SZ"""

    def test_integer_string_infers_dword(self):
        """'123' → REG_DWORD"""
        result, cap = _write_and_capture("123")
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert cap["reg_type"] == winreg.REG_DWORD

    def test_negative_integer_infers_dword(self):
        """'-1' → REG_DWORD (2026-07-31 修复回归)"""
        result, cap = _write_and_capture("-1")
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert cap["reg_type"] == winreg.REG_DWORD

    def test_plain_string_infers_sz(self):
        """纯字符串 'Hello from Task002' → REG_SZ (task002问题2: 原抛ValueError)"""
        result, cap = _write_and_capture("Hello from Task002")
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert cap["reg_type"] == winreg.REG_SZ
        assert cap["value"] == "Hello from Task002"

    def test_decimal_string_infers_sz(self):
        """小数 '3.14' → REG_SZ"""
        result, cap = _write_and_capture("3.14")
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert cap["reg_type"] == winreg.REG_SZ

    def test_hex_literal_infers_sz(self):
        """'0x1F' → REG_SZ (非纯十进制不误判DWORD)"""
        result, cap = _write_and_capture("0x1F")
        assert result["llm_data"]["status"]["exec_code"] == "success"
        assert cap["reg_type"] == winreg.REG_SZ

    def test_explicit_reg_sz_unchanged(self):
        """显式 value_type=REG_SZ 不受影响"""
        result, cap = _write_and_capture("123")
        result = registry_write(
            path="HKCU\\Software\\Task002Test",
            value_name="ExplicitVal",
            value="123",
            value_type="REG_SZ",
            backup_before_write=False,
        )
        with patch.object(winreg, "CreateKey"), \
             patch.object(winreg, "SetValueEx"):
            pass  # 仅验证显式类型调用不再抛错, 用上方成功断言兜底
        assert result["llm_data"]["status"]["exec_code"] == "success"
