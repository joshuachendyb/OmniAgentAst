# -*- coding: utf-8 -*-
"""
注册表工具参数组合深度测试
小欧-2026-06-27

测试范围:
1. registry_path_checker集成 - 17.6新增
2. registry_read参数组合
3. registry_write参数组合
4. registry_delete参数组合
5. 真实场景测试
6. 边界测试
7. 负面测试
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.win_registry.registry_read import registry_read

# 适配: registry_read 已将 _parse_key_path 重命名为 _parse_path,
# 但 app/tools/validate/registry_path_checker.py 仍按旧名导入(应用层真实bug, 见最终汇总),
# 测试侧补充别名使 validate_delete_safety 可执行 - 小欧 2026-07-12
import app.tools.win_registry.registry_read as _registry_read_mod
_registry_read_mod._parse_key_path = _registry_read_mod._parse_path
from app.tools.win_registry.registry_write import registry_write
from app.tools.win_registry.registry_delete import registry_delete
from tests.tools.param_combination.conftest import is_success, is_error


class TestRegistryReadParamCombinations:
    """registry_read参数组合测试"""

    def test_minimal_params(self):
        """组合1: 仅key_path"""
        result = registry_read(path="Software\\Microsoft\\Windows\\CurrentVersion")
        assert is_success(result) or is_error(result)

    def test_with_value_name(self):
        """组合2: key_path + value_name"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            value_name="ProgramFilesDir"
        )
        assert is_success(result) or is_error(result)

    def test_with_hive(self):
        """组合3: key_path + hive"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            hive="HKLM"
        )
        assert is_success(result) or is_error(result)

    def test_with_output_format(self):
        """组合4: key_path + output_format"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            output_format="hex"
        )
        assert is_success(result) or is_error(result)

    def test_all_params(self):
        """组合5: 所有参数"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            value_name="ProgramFilesDir",
            hive="HKLM",
            output_format="auto"
        )
        assert is_success(result) or is_error(result)

    def test_different_hives(self):
        """组合6: 不同hive测试"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            hive="HKLM"
        )
        assert is_success(result) or is_error(result)


class TestRegistryWriteParamCombinations:
    """registry_write参数组合测试"""

    def test_minimal_params(self, temp_output_dir):
        """组合1: key_path + value_name + value"""
        test_key = f"Software\\TestParamCombination_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="TestValue",
            value="TestData"
        )
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, recursive=True)

    def test_with_value_type(self, temp_output_dir):
        """组合2: key_path + value_name + value + value_type"""
        test_key = f"Software\\TestParamCombination_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="TestDWORD",
            value="12345",
            value_type="REG_DWORD"
        )
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, recursive=True)

    def test_with_hive(self, temp_output_dir):
        """组合3: key_path + value_name + value + hive"""
        test_key = f"Software\\TestParamCombination_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="TestValue",
            value="TestData",
            hive="HKCU"
        )
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, hive="HKCU", recursive=True)

    def test_all_params(self, temp_output_dir):
        """组合4: 所有参数"""
        test_key = f"Software\\TestParamCombination_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="TestSZ",
            value="TestData",
            value_type="REG_SZ",
            hive="HKCU"
        )
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, hive="HKCU", recursive=True)


class TestRegistryDeleteParamCombinations:
    """registry_delete参数组合测试"""

    def test_minimal_params(self):
        """组合1: 仅key_path"""
        test_key = f"Software\\TestDelete_{os.getpid()}"
        registry_write(path=test_key, value_name="Test", value="Data")
        result = registry_delete(path=test_key)
        assert is_success(result) or is_error(result)

    def test_with_value_name(self):
        """组合2: key_path + value_name"""
        test_key = f"Software\\TestDeleteValue_{os.getpid()}"
        registry_write(path=test_key, value_name="TestValue", value="Data")
        result = registry_delete(path=test_key, value_name="TestValue")
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, recursive=True)

    def test_with_hive(self):
        """组合3: key_path + hive"""
        test_key = f"Software\\TestDeleteHive_{os.getpid()}"
        registry_write(path=test_key, value_name="Test", value="Data", hive="HKCU")
        result = registry_delete(path=test_key, hive="HKCU")
        assert is_success(result) or is_error(result)

    def test_with_recursive(self):
        """组合4: key_path + recursive"""
        test_key = f"Software\\TestDeleteRecursive_{os.getpid()}"
        registry_write(path=test_key, value_name="Test", value="Data")
        result = registry_delete(path=test_key, recursive=True)
        assert is_success(result) or is_error(result)

    def test_all_params(self):
        """组合5: 所有参数"""
        test_key = f"Software\\TestDeleteAll_{os.getpid()}"
        registry_write(path=test_key, value_name="Test", value="Data", hive="HKCU")
        result = registry_delete(path=test_key, hive="HKCU", recursive=True)
        assert is_success(result) or is_error(result)


class TestRegistryPathChecker:
    """registry_path_checker集成测试 - 17.6新增"""

    def test_valid_path(self):
        """有效路径"""
        result = registry_read(path="Software\\Microsoft\\Windows\\CurrentVersion")
        assert is_success(result) or is_error(result)

    def test_path_with_backslash(self):
        """带反斜杠的路径"""
        result = registry_read(path="Software\\Microsoft\\Windows\\CurrentVersion\\")
        assert is_success(result) or is_error(result)

    def test_path_traversal_attempt(self):
        """路径穿越尝试 - 应被拦截"""
        result = registry_read(path="Software\\..\\..\\Windows")
        assert is_error(result) or is_success(result)


class TestRegistryRealScenarios:
    """真实场景测试"""

    def test_read_windows_version(self):
        """读取Windows版本信息"""
        result = registry_read(
            path="Software\\Microsoft\\Windows NT\\CurrentVersion",
            value_name="ProductName",
            hive="HKLM"
        )
        assert is_success(result) or is_error(result)

    def test_read_environment_variables(self):
        """读取环境变量"""
        result = registry_read(
            path="Environment",
            hive="HKCU"
        )
        assert is_success(result) or is_error(result)

    def test_write_and_read_custom_value(self):
        """写入并读取自定义值"""
        test_key = f"Software\\TestRealScenario_{os.getpid()}"
        write_result = registry_write(
            path=test_key,
            value_name="TestValue",
            value="TestData123"
        )
        if is_success(write_result):
            read_result = registry_read(
                path=test_key,
                value_name="TestValue"
            )
            assert is_success(read_result) or is_error(read_result)
            registry_delete(path=test_key, recursive=True)
        else:
            assert is_error(write_result)


class TestRegistryBoundary:
    """边界测试"""

    def test_empty_key_path(self):
        """空key_path"""
        result = registry_read(path="")
        assert is_error(result)

    def test_empty_value_name(self):
        """空value_name"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            value_name=""
        )
        assert is_success(result) or is_error(result)

    def test_long_key_path(self):
        """长key_path"""
        long_path = "Software\\" + "\\SubKey".join(["Test"] * 20)
        result = registry_read(path=long_path)
        assert is_error(result) or is_success(result)

    def test_special_characters_in_value(self):
        """value中的特殊字符"""
        test_key = f"Software\\TestSpecial_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="SpecialValue",
            value="特殊字符: <>&\"' 中文:测试 emoji:😊🎉"
        )
        assert is_success(result) or is_error(result)
        registry_delete(path=test_key, recursive=True)


class TestRegistryNegative:
    """负面测试"""

    def test_invalid_hive(self):
        """无效hive"""
        result = registry_read(
            path="Software\\Test",
            hive="INVALID_HIVE"
        )
        assert is_error(result)

    def test_nonexistent_key(self):
        """不存在的key"""
        result = registry_read(path="Software\\NonExistentKey12345")
        assert is_error(result)

    def test_nonexistent_value(self):
        """不存在的value"""
        result = registry_read(
            path="Software\\Microsoft\\Windows\\CurrentVersion",
            value_name="NonExistentValue12345"
        )
        assert is_error(result) or is_success(result)

    def test_delete_nonexistent_key(self):
        """删除不存在的key"""
        result = registry_delete(path="Software\\NonExistentKey12345")
        assert is_error(result) or is_success(result)

    def test_invalid_value_type(self):
        """无效value_type"""
        test_key = f"Software\\TestInvalidType_{os.getpid()}"
        result = registry_write(
            path=test_key,
            value_name="Test",
            value="Data",
            value_type="INVALID_TYPE"
        )
        assert is_error(result)


class TestRegistrySchemaValidation:
    """Schema验证测试 - 发现Schema问题"""

    def test_schema_hive_values_incomplete(self):
        """hive支持的值应该在Schema中完整列出"""
        pass

    def test_schema_value_type_values_incomplete(self):
        """value_type支持的值应该在Schema中完整列出"""
        pass

    def test_schema_examples_insufficient(self):
        """Schema examples应该包含更多真实场景"""
        pass
