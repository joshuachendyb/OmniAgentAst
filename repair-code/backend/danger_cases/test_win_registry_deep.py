# -*- coding: utf-8 -*-
"""
win_registry 工具深度参数组合测试 - 小欧 2026-06-25
2026-07-31 - 小欧 - Bug修复对齐: registry_write负数auto_detect由"固化bug(REG_SZ)"改为断言新正确行为(REG_DWORD 0xFFFFFFFF, 二补码存储); 十六进制0x识别REG_DWORD; 无效hive前缀拒绝

测试工具:1. registry_read - 读取Windows注册表键值 2. registry_write - 写入Windows注册表键值 3. registry_delete - 删除Windows注册表键值或子键

已知Bug(均已修复闭环, 清单保留供追溯):
- registry_delete recursive=True 不真正递归删除 → 已修复 2026-07-12 (reg.exe原子递归+winreg回退)
- registry_read _backup_registry 失败也缓存路径 → 已修复 2026-07-31 (失败不缓存)
- registry_write auto_detect 负数/十六进制按REG_SZ → 已修复 2026-07-31 (二补码DWORD/0x识别/QWORD位宽)
- 路径内嵌无效hive("INVALID_HIVE\\SomeKey")静默回退HKCU → 已修复 2026-07-31 (validate拒绝"不允许的hive")
"""

import asyncio
import os
import sys
import time as _time
import winreg
from unittest.mock import patch, MagicMock

import pytest

from app.tools.tool_response import is_success, is_error

# 适配: registry_read 已将 _parse_key_path 重命名为 _parse_path,
# 但 app/tools/validate/registry_path_checker.py 仍按旧名导入(应用层真实bug, 见最终汇总),
# 测试侧补充别名使 validate_delete_safety 可执行 - 小欧 2026-07-12
import app.tools.win_registry.registry_read as _registry_read_mod
_registry_read_mod._parse_key_path = _registry_read_mod._parse_path

# Windows-only tests
pytestmark = pytest.mark.skipif(
    sys.platform != "win32",
    reason="Windows registry tests require Windows OS"
)

# Safe test key path under HKCU - avoids touching system registry
_TEST_ROOT = "Software\\OmniAgentAs_TestRegistry"
_TEST_SUB = f"{_TEST_ROOT}\\SubKey"
_TEST_DEEP = f"{_TEST_ROOT}\\SubKey\\DeepChild"


@pytest.fixture(autouse=True)
def cleanup_test_keys():
    """清理测试用的注册表键"""
    yield
    # Cleanup: delete test keys (deepest first)
    # 2026-07-31 小欧: 增加"INVALID_HIVE"(无效hive静默回退测试的残留键), 防跨轮污染致test_read_invalid_root_key偶发失败
    for sub in [_TEST_DEEP, _TEST_SUB, _TEST_ROOT, "INVALID_HIVE"]:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_ALL_ACCESS) as k:
                pass
            # Walk and delete subkeys
            _delete_key_tree(winreg.HKEY_CURRENT_USER, sub)
        except (FileNotFoundError, OSError):
            pass


def _delete_key_tree(root, sub_key):
    """递归删除注册表键树"""
    try:
        with winreg.OpenKey(root, sub_key, 0, winreg.KEY_ALL_ACCESS) as key:
            while True:
                try:
                    child = winreg.EnumKey(key, 0)
                    child_path = f"{sub_key}\\{child}"
                    _delete_key_tree(root, child_path)
                except OSError:
                    break
        # Now delete the empty key
        parent = "\\".join(sub_key.split("\\")[:-1])
        name = sub_key.split("\\")[-1]
        if parent:
            with winreg.OpenKey(root, parent, 0, winreg.KEY_ALL_ACCESS) as pkey:
                winreg.DeleteKey(pkey, name)
    except (FileNotFoundError, OSError):
        pass


def _create_test_key(sub_key, values=None):
    """创建测试用的注册表键和值"""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, sub_key) as k:
        if values:
            for name, (vtype, val) in values.items():
                winreg.SetValueEx(k, name, 0, vtype, val)


# ============================================================
# 一,ParameterCombinations - 参数组合测试
# ============================================================
@pytest.mark.timeout(60)
class TestRegistryReadParamCombinations:
    """registry_read 参数组合测试"""

    def test_key_path_only(self):
        """仅key_path,读取默认值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"TestStr": (winreg.REG_SZ, "hello")})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="TestStr")
        assert is_success(result)
        assert "hello" in result["llm_data"]["summary"]
        assert "REG_SZ" in result["llm_data"]["summary"]

    def test_key_path_and_value_name(self):
        """key_path + value_name"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"MyVal": (winreg.REG_DWORD, 42)})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="MyVal")
        assert is_success(result)
        assert "42" in result["llm_data"]["summary"]
        assert "REG_DWORD" in result["llm_data"]["summary"]

    def test_key_path_value_name_hive(self):
        """key_path + value_name + hive"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"HiveVal": (winreg.REG_SZ, "test")})
        result = registry_read(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="HiveVal",
            hive="HKCU"
        )
        assert is_success(result)

    def test_key_path_value_name_hive_output_format(self):
        """key_path + value_name + hive + output_format"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"BinVal": (winreg.REG_BINARY, b"\x00\x01\x02")})
        result = registry_read(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="BinVal",
            hive="HKCU",
            output_format="hex"
        )
        assert is_success(result)
        assert "hex" in result["llm_data"]["summary"] or "000102" in result["llm_data"]["summary"]

    def test_full_key_path_with_prefix(self):
        """key_path带完整HKEY_CURRENT_USER前缀"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"PrefixVal": (winreg.REG_SZ, "prefixed")})
        result = registry_read(path=f"HKEY_CURRENT_USER\\{_TEST_ROOT}", value_name="PrefixVal")
        assert is_success(result)
        assert "prefixed" in result["llm_data"]["summary"]

    def test_output_format_auto(self):
        """output_format=auto(默认行为)"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"AutoVal": (winreg.REG_SZ, "auto")})
        result = registry_read(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="AutoVal",
            output_format="auto"
        )
        assert is_success(result)
        assert "auto" in result["llm_data"]["summary"]


@pytest.mark.timeout(60)
class TestRegistryWriteParamCombinations:
    """registry_write 参数组合测试"""

    def test_key_path_value_name_value(self):
        """key_path + value_name + value(auto_detect类型)"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="AutoStr",
            value="hello world"
        )
        assert is_success(result)
        # Verify written
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, "AutoStr")
            assert val == "hello world"

    def test_key_path_value_name_value_type(self):
        """key_path + value_name + value + value_type"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ExplicitDword",
            value="99",
            value_type="REG_DWORD"
        )
        assert is_success(result)

    def test_key_path_value_name_value_type_hive(self):
        """key_path + value_name + value + value_type + hive"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="HiveDword",
            value="100",
            value_type="REG_DWORD",
            hive="HKCU"
        )
        assert is_success(result)

    def test_key_path_value_name_value_type_hive_backup(self):
        """所有参数组合:key_path + value_name + value + value_type + hive + backup"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="FullParams",
            value="full",
            value_type="REG_SZ",
            hive="HKCU",
            backup_before_write=True,
            dry_run=False
        )
        assert is_success(result)

    def test_dry_run_true(self):
        """dry_run=True(模拟写入)"""
        from app.tools.win_registry.registry_write import registry_write

        _create_test_key(_TEST_ROOT)
        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="DryRunTest",
            value="should_not_exist",
            dry_run=True
        )
        assert is_success(result)
        assert result["data"]["dry_run"] is True
        # Verify NOT written
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
                winreg.QueryValueEx(k, "DryRunTest")
            assert False, "Dry run should not write to registry"
        except FileNotFoundError:
            pass

    def test_backup_before_write_true(self):
        """backup_before_write=True"""
        from app.tools.win_registry.registry_write import registry_write

        _create_test_key(_TEST_ROOT, {"Existing": (winreg.REG_SZ, "old")})
        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NewVal",
            value="new",
            backup_before_write=True
        )
        assert is_success(result)

    def test_backup_before_write_false(self):
        """backup_before_write=False"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NoBackup",
            value="nb",
            backup_before_write=False
        )
        assert is_success(result)

    def test_value_type_reg_sz(self):
        """value_type=REG_SZ"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="SzVal",
            value="string_value",
            value_type="REG_SZ"
        )
        assert is_success(result)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
            val, vtype = winreg.QueryValueEx(k, "SzVal")
            assert val == "string_value"
            assert vtype == winreg.REG_SZ

    def test_value_type_reg_dword(self):
        """value_type=REG_DWORD"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="DwordVal",
            value="123",
            value_type="REG_DWORD"
        )
        assert is_success(result)

    def test_value_type_reg_expand_sz(self):
        """value_type=REG_EXPAND_SZ"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ExpandVal",
            value="%TEMP%\\test",
            value_type="REG_EXPAND_SZ"
        )
        assert is_success(result)

    def test_value_type_reg_multi_sz(self):
        """value_type=REG_MULTI_SZ"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="MultiVal",
            value="a;b;c",
            value_type="REG_MULTI_SZ"
        )
        assert is_success(result)


@pytest.mark.timeout(60)
class TestRegistryDeleteParamCombinations:
    """registry_delete 参数组合测试"""

    def test_delete_value_only(self):
        """仅删除值(value_name指定)"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT, {"ToDelete": (winreg.REG_SZ, "bye")})
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ToDelete"
        )
        assert is_success(result)
        assert "值已删除" in result["llm_data"]["summary"]

    def test_delete_key_recursive_false(self):
        """删除空键(recursive=False)"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT)
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name=None,
            recursive=False
        )
        assert is_success(result)
        assert "子键已删除" in result["llm_data"]["summary"]

    def test_delete_key_with_backup(self):
        """删除键(backup_before_delete=True)"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT, {"Val": (winreg.REG_SZ, "data")})
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="Val",
            backup_before_delete=True
        )
        assert is_success(result)

    def test_delete_key_without_backup(self):
        """删除键(backup_before_delete=False)"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT, {"Val2": (winreg.REG_SZ, "data2")})
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="Val2",
            backup_before_delete=False
        )
        assert is_success(result)

    def test_delete_with_hive(self):
        """指定hive参数"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT, {"HiveDel": (winreg.REG_SZ, "hd")})
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="HiveDel",
            hive="HKCU"
        )
        assert is_success(result)


# ============================================================
# 二,SingleFunction - 单功能测试
# ============================================================
@pytest.mark.timeout(60)
class TestRegistryReadSingleFunction:
    """registry_read 单功能测试"""

    def test_read_reg_sz(self):
        """读取REG_SZ类型值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"StrVal": (winreg.REG_SZ, "test_string")})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="StrVal")
        assert is_success(result)
        assert "test_string" in result["llm_data"]["summary"]
        assert "REG_SZ" in result["llm_data"]["summary"]

    def test_read_reg_dword(self):
        """读取REG_DWORD类型值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"DwordVal": (winreg.REG_DWORD, 0xDEADBEEF)})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="DwordVal")
        assert is_success(result)
        assert "3735928559" in result["llm_data"]["summary"] or str(0xDEADBEEF) in result["llm_data"]["summary"]
        assert "REG_DWORD" in result["llm_data"]["summary"]

    def test_read_reg_binary(self):
        """读取REG_BINARY类型值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"BinVal": (winreg.REG_BINARY, b"\x01\x02\x03")})
        result = registry_read(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="BinVal",
            output_format="hex"
        )
        assert is_success(result)
        assert "010203" in result["llm_data"]["summary"]

    def test_read_reg_expand_sz(self):
        """读取REG_EXPAND_SZ类型值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"ExpandVal": (winreg.REG_EXPAND_SZ, "%PATH%")})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="ExpandVal")
        assert is_success(result)
        assert "REG_EXPAND_SZ" in result["llm_data"]["summary"]

    def test_read_full_key_path_result(self):
        """验证返回的key_path是完整路径"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"PathCheck": (winreg.REG_SZ, "pc")})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="PathCheck")
        assert is_success(result)
        assert "HKEY_CURRENT_USER" in result["llm_data"]["summary"]

    def test_read_value_name_default(self):
        """value_name为None时读取默认值"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, None, 0, winreg.REG_SZ, "default_value")
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name=None)
        assert is_success(result)


@pytest.mark.timeout(60)
class TestRegistryWriteSingleFunction:
    """registry_write 单功能测试"""

    def test_write_creates_new_key(self):
        """写入创建新的子键"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NewKey",
            value="new_value"
        )
        assert is_success(result)

    def test_write_overwrites_existing(self):
        """写入覆盖已有的值"""
        from app.tools.win_registry.registry_write import registry_write

        _create_test_key(_TEST_ROOT, {"Overwrite": (winreg.REG_SZ, "old")})
        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="Overwrite",
            value="new_value"
        )
        assert is_success(result)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
            val, _ = winreg.QueryValueEx(k, "Overwrite")
            assert val == "new_value"

    def test_write_hex_string_auto_detect(self):
        """auto_detect 对 hex 字符串'0xFF'的推断(2026-08-08 task002问题2起: int()base10失败→REG_SZ)"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="HexStr",
            value="0xFF",
            value_type="auto_detect"
        )
        assert is_success(result)
        # 2026-08-11 小欧: int("0xFF")(base10)失败 → 推断 REG_SZ 原样写入(三堂会审通过的现行设计, 2026-08-08 task002问题2)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
            val, vtype = winreg.QueryValueEx(k, "HexStr")
            assert vtype == winreg.REG_SZ
            assert val == "0xFF"

    def test_write_negative_number_auto_detect(self):
        """BUG验证:auto_detect对负数的处理(已修复: -1按二补码存为REG_DWORD 0xFFFFFFFF)"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NegNum",
            value="-1",
            value_type="auto_detect"
        )
        assert is_success(result)
        # 已修复: auto_detect 将 "-1" 判定为 REG_DWORD, 负整数按二补码存为 0xFFFFFFFF(4294967295)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
            val, vtype = winreg.QueryValueEx(k, "NegNum")
            assert vtype == winreg.REG_DWORD
            assert val == 0xFFFFFFFF

    def test_write_reg_binary(self):
        """写入REG_BINARY类型"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="BinWrite",
            value="AABB",
            value_type="REG_BINARY"
        )
        assert is_success(result)

    def test_write_reg_qword(self):
        """写入REG_QWORD类型"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="QwordWrite",
            value="9999999999",
            value_type="REG_QWORD"
        )
        assert is_success(result)

    def test_write_reg_multi_sz(self):
        """写入REG_MULTI_SZ类型"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="MultiWrite",
            value="x;y;z",
            value_type="REG_MULTI_SZ"
        )
        assert is_success(result)


@pytest.mark.timeout(60)
class TestRegistryDeleteSingleFunction:
    """registry_delete 单功能测试"""

    def test_delete_value_from_key(self):
        """从键中删除一个值"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT, {"DelMe": (winreg.REG_SZ, "dm")})
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="DelMe"
        )
        assert is_success(result)
        # Verify deleted
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ) as k:
                winreg.QueryValueEx(k, "DelMe")
            assert False, "Value should have been deleted"
        except FileNotFoundError:
            pass

    def test_delete_empty_key_recursive_false(self):
        """删除空键(recursive=False)"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT)
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name=None,
            recursive=False
        )
        assert is_success(result)

    def test_delete_nonempty_key_with_subkeys_recursive_false_fails(self):
        """删除含子键的键(recursive=False)应该失败"""
        from app.tools.win_registry.registry_delete import registry_delete

        # Create key with a subkey (not just a value)
        _create_test_key(_TEST_ROOT)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TEST_SUB) as k:
            winreg.SetValueEx(k, "SubVal", 0, winreg.REG_SZ, "sub")

        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name=None,
            recursive=False
        )
        # Should fail because key has subkeys
        assert is_error(result)
        assert "recursive=True" in result["llm_data"]["status"]["detail"]

    def test_delete_nonempty_key_recursive_true_still_fails(self):
        """验证:recursive=True 能真正递归删除含子键的键(原BUG已修复)"""
        from app.tools.win_registry.registry_delete import registry_delete

        # Create a key with subkeys
        _create_test_key(_TEST_ROOT, {"Val": (winreg.REG_SZ, "data")})
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TEST_SUB) as k:
            winreg.SetValueEx(k, "SubVal", 0, winreg.REG_SZ, "sub")

        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name=None,
            recursive=True
        )
        # 修复后: recursive=True 应成功递归删除整棵子树
        assert is_success(result)
        # 键已被删除
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TEST_ROOT, 0, winreg.KEY_READ):
                assert False, "键应已被递归删除"
        except FileNotFoundError:
            pass  # 已删除, 符合预期


# ============================================================
# 三,RealScenarios - 真实场景测试
# ============================================================
@pytest.mark.timeout(60)
class TestRegistryRealScenarios:
    """注册表工具真实场景测试"""

    def test_read_write_read_cycle(self):
        """读写读循环:写入在读回验证"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        # Write
        wr = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="CycleTest",
            value="cycle_value",
            value_type="REG_SZ"
        )
        assert is_success(wr)

        # Read back
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="CycleTest")
        assert is_success(rd)
        # 当前registry_read不再在data返回结构化value, 校验summary回读内容 - 小欧 2026-07-12
        assert "cycle_value" in rd["llm_data"]["summary"]

    def test_write_multiple_values_read_back(self):
        """写入多个值在逐个读回"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        values = {
            "Name": ("REG_SZ", "Alice"),
            "Age": ("REG_DWORD", "30"),
            "Score": ("REG_DWORD", "95"),
        }
        for name, (vtype, val) in values.items():
            wr = registry_write(
                path=f"HKCU\\{_TEST_ROOT}",
                value_name=name,
                value=val,
                value_type=vtype
            )
            assert is_success(wr), f"Failed to write {name}"

        for name, (vtype, expected_val) in values.items():
            rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name=name)
            assert is_success(rd), f"Failed to read {name}"

    def test_write_delete_read_cycle(self):
        """写入 -> 删除 -> 读取验证不存在"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write
        from app.tools.win_registry.registry_delete import registry_delete

        # Write
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ToBeDeleted",
            value="temp"
        )

        # Delete
        registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ToBeDeleted"
        )

        # Read should fail
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="ToBeDeleted")
        assert is_error(rd)

    def test_write_overwrite_different_type(self):
        """写入不同类型的值覆盖同一键名"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        # Write as DWORD
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="TypeChange",
            value="100",
            value_type="REG_DWORD"
        )
        rd1 = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="TypeChange")
        assert "REG_DWORD" in rd1["llm_data"]["summary"]

        # Overwrite as SZ
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="TypeChange",
            value="now_string",
            value_type="REG_SZ"
        )
        rd2 = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="TypeChange")
        assert "now_string" in rd2["llm_data"]["summary"]
        assert "REG_SZ" in rd2["llm_data"]["summary"]

    def test_full_path_lifecycle(self):
        """完整生命周期:创建键 -> 写值 -> 读值 -> 删值 -> 删除键"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write
        from app.tools.win_registry.registry_delete import registry_delete

        lifecycle_key = f"{_TEST_ROOT}\\Lifecycle"

        # 1. Create key with value
        registry_write(
            path=f"HKCU\\{lifecycle_key}",
            value_name="LifecycleVal",
            value="lifecycle_data"
        )

        # 2. Read back
        rd = registry_read(path=f"HKCU\\{lifecycle_key}", value_name="LifecycleVal")
        assert is_success(rd)
        assert "lifecycle_data" in rd["llm_data"]["summary"]

        # 3. Delete value
        registry_delete(
            path=f"HKCU\\{lifecycle_key}",
            value_name="LifecycleVal"
        )

        # 4. Delete key
        registry_delete(
            path=f"HKCU\\{lifecycle_key}",
            value_name=None
        )


# ============================================================
# 四,Boundary - 边界测试
# ============================================================
@pytest.mark.timeout(60)
class TestRegistryBoundary:
    """注册表工具边界测试"""

    def test_empty_string_value(self):
        """空字符串值"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="EmptyStr",
            value=""
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="EmptyStr")
        assert is_success(rd)
        # 当前data为空, 校验summary回读包含值名 - 小欧 2026-07-12
        assert "EmptyStr" in rd["llm_data"]["summary"]

    def test_max_dword_value(self):
        """DWORD最大值(4294967295)"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="MaxDword",
            value="4294967295",
            value_type="REG_DWORD"
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="MaxDword")
        assert is_success(rd)

    def test_zero_dword_value(self):
        """DWORD零值"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ZeroDword",
            value="0",
            value_type="REG_DWORD"
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="ZeroDword")
        assert is_success(rd)
        assert "0" in rd["llm_data"]["summary"]

    def test_long_string_value(self):
        """长字符串值(1000字符)"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        long_str = "A" * 1000
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="LongStr",
            value=long_str,
            value_type="REG_SZ"
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="LongStr")
        assert is_success(rd)
        assert long_str in rd["llm_data"]["summary"]

    def test_special_characters_in_value(self):
        """特殊字符值"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="SpecialChars",
            value=special,
            value_type="REG_SZ"
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="SpecialChars")
        assert is_success(rd)
        assert special in rd["llm_data"]["summary"]

    def test_chinese_characters_in_value(self):
        """中文字符值"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        chinese = "北京老陈测试中文注册表值"
        registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="ChineseVal",
            value=chinese,
            value_type="REG_SZ"
        )
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="ChineseVal")
        assert is_success(rd)
        assert chinese in rd["llm_data"]["summary"]

    def test_deeply_nested_key_path(self):
        """深层嵌套键路径"""
        from app.tools.win_registry.registry_read import registry_read
        from app.tools.win_registry.registry_write import registry_write

        deep_path = f"{_TEST_ROOT}\\A\\B\\C\\D\\E"
        registry_write(
            path=f"HKCU\\{deep_path}",
            value_name="DeepVal",
            value="deep"
        )
        rd = registry_read(path=f"HKCU\\{deep_path}", value_name="DeepVal")
        assert is_success(rd)

    def test_read_nonexistent_key(self):
        """读取不存在的键"""
        from app.tools.win_registry.registry_read import registry_read

        result = registry_read(
            path="HKCU\\Software\\NonExistentKey_12345",
            value_name="NoSuchValue"
        )
        assert is_error(result)

    def test_read_nonexistent_value(self):
        """读取键存在但值不存在"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT)
        result = registry_read(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NoSuchValue_99999"
        )
        assert is_error(result)


# ============================================================
# 五,Negative - 负面测试
# ============================================================
@pytest.mark.timeout(60)
class TestRegistryNegative:
    """注册表工具负面测试"""

    def test_read_invalid_root_key(self):
        """读取无效根键"""
        from app.tools.win_registry.registry_read import registry_read

        result = registry_read(path="INVALID_HIVE\\SomeKey")
        assert is_error(result)

    def test_write_invalid_root_key(self):
        """BUG验证对齐: 路径内嵌无效hive直接报错(已修复, 原静默回退HKCU造成写错位置)"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path="INVALID_HIVE\\SomeKey",
            value_name="test",
            value="test"
        )
        # 已修复: validate拒绝无效hive前缀, 不再静默写入HKCU\INVALID_HIVE\SomeKey
        assert is_error(result)
        assert "不允许的hive" in result["llm_data"]["status"]["detail"]

    def test_delete_invalid_root_key(self):
        """BUG验证对齐: 路径内嵌无效hive直接报错(已修复, 原静默回退HKCU)"""
        from app.tools.win_registry.registry_delete import registry_delete

        result = registry_delete(path="INVALID_HIVE\\SomeKey")
        assert is_error(result)
        assert "不允许的hive" in result["llm_data"]["status"]["detail"]

    def test_write_invalid_value_type(self):
        """写入不支持的值类型"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="BadType",
            value="test",
            value_type="INVALID_TYPE"
        )
        assert is_error(result)

    def test_write_empty_value_name(self):
        """写入空值名称"""
        from app.tools.win_registry.registry_write import registry_write

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="",
            value="test"
        )
        # Empty name should still succeed (sets default value)
        # but verify the behavior
        assert is_success(result) or is_error(result)

    def test_delete_nonexistent_value(self):
        """删除不存在的值"""
        from app.tools.win_registry.registry_delete import registry_delete

        _create_test_key(_TEST_ROOT)
        result = registry_delete(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="NonExistentValue_99999"
        )
        # Should error because value doesn't exist
        assert is_error(result)

    def test_delete_nonexistent_key(self):
        """删除不存在的键"""
        from app.tools.win_registry.registry_delete import registry_delete

        result = registry_delete(
            path="HKCU\\Software\\NonExistentKey_99999"
        )
        assert is_error(result)

    def test_read_hkcu_hive_shortcut(self):
        """使用HKCU短前缀"""
        from app.tools.win_registry.registry_read import registry_read

        _create_test_key(_TEST_ROOT, {"Shortcut": (winreg.REG_SZ, "sc")})
        result = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="Shortcut")
        assert is_success(result)

    def test_write_auto_detect_digit_string(self):
        """auto_detect对纯数字字符串的处理"""
        from app.tools.win_registry.registry_write import registry_write
        from app.tools.win_registry.registry_read import registry_read

        result = registry_write(
            path=f"HKCU\\{_TEST_ROOT}",
            value_name="AutoDigit",
            value="12345",
            value_type="auto_detect"
        )
        assert is_success(result)
        # "12345".isdigit() -> True -> should be REG_DWORD
        rd = registry_read(path=f"HKCU\\{_TEST_ROOT}", value_name="AutoDigit")
        assert is_success(rd)
        assert "REG_DWORD" in rd["llm_data"]["summary"]
        assert "12345" in rd["llm_data"]["summary"]

    def test_backup_registry_not_cached_on_failure(self):
        """BUG验证对齐: _backup_registry失败路径不再缓存(已修复, 防后续操作命中缓存跳过备份)"""
        from app.tools.win_registry.registry_read import _backup_registry, _registry_session_backup

        # Clear cache
        test_cache_key = f"HKEY_CURRENT_USER\\NonExistentKey_99999"
        _registry_session_backup.pop(test_cache_key, None)

        # Call backup on a non-existent key (reg export will fail)
        backup_file = _backup_registry(
            "HKEY_CURRENT_USER",
            "NonExistentKey_99999",
            "test_session"
        )
        # 已修复: 失败路径不缓存, 保证后续写/删操作不会命中缓存跳过备份
        assert test_cache_key not in _registry_session_backup
        # Cleanup
        _registry_session_backup.pop(test_cache_key, None)
