# -*- coding: utf-8 -*-
"""get_system_info参数组合测试 - 小欧 2026-07-04

测试系统信息工具的各种info_type参数组合、返回值结构验证
"""

import pytest
from app.tools.tool_response import is_success, is_error


class TestSysinfoNormal:
    """正常参数组合"""

    def test_default_all(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo()
        assert is_success(result)
        data = result["data"]
        assert "basic" in data
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "network" in data

    def test_info_type_basic(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="basic")
        assert is_success(result)
        data = result["data"]
        assert "basic" in data
        assert "cpu" not in data
        assert "memory" not in data
        assert "disk" not in data
        assert "network" not in data

    def test_info_type_cpu(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="cpu")
        assert is_success(result)
        data = result["data"]
        assert "cpu" in data
        cpu = data["cpu"]
        assert "physical_cores" in cpu
        assert "logical_cores" in cpu
        assert "cpu_usage_percent" in cpu

    def test_info_type_memory(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="memory")
        assert is_success(result)
        data = result["data"]
        assert "memory" in data
        mem = data["memory"]
        assert "total_gb" in mem
        assert "available_gb" in mem
        assert "used_gb" in mem
        assert "percent" in mem

    def test_info_type_disk(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="disk")
        assert is_success(result)
        data = result["data"]
        assert "disk" in data
        assert isinstance(data["disk"], list)
        if data["disk"]:
            disk = data["disk"][0]
            assert "device" in disk
            assert "total_gb" in disk
            assert "used_gb" in disk

    def test_info_type_network(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="network")
        assert is_success(result)
        data = result["data"]
        assert "network" in data
        net = data["network"]
        assert "bytes_sent_mb" in net
        assert "bytes_recv_mb" in net

    def test_info_type_all_explicit(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="all")
        assert is_success(result)
        data = result["data"]
        assert "basic" in data
        assert "cpu" in data
        assert "memory" in data
        assert "disk" in data
        assert "network" in data


class TestSysinfoReturnValue:
    """返回值内容验证"""

    def test_basic_contains_hostname(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="basic")
        basic = result["data"]["basic"]
        assert "hostname" in basic
        assert "platform" in basic
        assert "architecture" in basic

    def test_cpu_cores_positive(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="cpu")
        cpu = result["data"]["cpu"]
        assert cpu["physical_cores"] >= 1
        assert cpu["logical_cores"] >= 1

    def test_memory_values_reasonable(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="memory")
        mem = result["data"]["memory"]
        assert mem["total_gb"] > 0
        assert 0 <= mem["percent"] <= 100

    def test_multiple_calls_consistent(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        r1 = sysinfo(info_type="basic")
        r2 = sysinfo(info_type="basic")
        assert r1["data"]["basic"]["platform"] == r2["data"]["basic"]["platform"]


class TestSysinfoEdgeCases:
    """边界情况"""

    def test_invalid_info_type(self):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="invalid")
        assert is_error(result)
        assert "无效的info_type" in result["llm_data"]["status"]["detail"]

    def test_empty_string_type(self):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="")
        assert is_error(result)

    def test_case_sensitivity(self):
        from app.tools.fundamental.get_system_info import sysinfo
        result = sysinfo(info_type="CPU")
        assert is_error(result)

    def test_all_valid_types(self, temp_output_dir):
        from app.tools.fundamental.get_system_info import sysinfo
        valid_types = ["basic", "cpu", "memory", "disk", "network", "all"]
        for t in valid_types:
            result = sysinfo(info_type=t)
            assert is_success(result), f"{t}应该是有效类型"
