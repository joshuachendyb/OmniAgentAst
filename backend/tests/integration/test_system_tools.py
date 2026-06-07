"""
system类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty

TOOL = ToolClient()


class TestGetSystemInfo:
    """get_system_info 多场景测试"""

    def test_all(self):
        r = TOOL.call("get_system_info", {"info_type": "all"})
        assert_success(r)
        assert_data_not_empty(r)

    def test_cpu(self):
        r = TOOL.call("get_system_info", {"info_type": "cpu"})
        assert_success(r)

    def test_memory(self):
        r = TOOL.call("get_system_info", {"info_type": "memory"})
        assert_success(r)

    def test_disk(self):
        r = TOOL.call("get_system_info", {"info_type": "disk"})
        assert_success(r)


class TestListProcesses:
    """list_processes 多场景测试"""

    def test_list_all(self):
        r = TOOL.call("list_processes", {})
        assert_success(r)

    def test_filter_by_name(self):
        r = TOOL.call("list_processes", {"filter_name": "python"})
        assert_success(r)


class TestGetEnv:
    """get_env 多场景测试"""

    def test_get_all(self):
        r = TOOL.call("get_env", {"action": "get", "name": "PATH"})
        assert_success(r)

    def test_get_specific(self):
        r = TOOL.call("get_env", {"name": "PATH", "action": "get"})
        assert_success(r)

    def test_get_nonexistent(self):
        r = TOOL.call("get_env", {"name": "NONEXISTENT_VAR_XYZ_12345", "action": "get"})
        assert_success(r)


class TestSetEnv:
    """set_env 多场景测试"""

    def test_set_and_get(self):
        TOOL.call("set_env", {"name": "OMNI_TEST_VAR", "value": "test_value", "action": "set"})
        r = TOOL.call("get_env", {"name": "OMNI_TEST_VAR", "action": "get"})
        assert_success(r)


class TestKillProcess:
    """kill_process - 仅验证接口，不实际kill"""

    def test_kill_nonexistent_pid_idempotent(self):
        """kill_process对不存在的PID返回SUCCESS (幂等设计)"""
        r = TOOL.call("kill_process", {"pid": 999999})
        assert_success(r)
        data = r.get("data", {})
        assert data.get("idempotent") is True or data.get("killed") == []


class TestNetConnections:
    """net_connections 多场景测试"""

    def test_list_inet(self):
        r = TOOL.call("net_connections", {"kind": "inet"})
        assert_success(r)


class TestEventLog:
    """event_log 多场景测试"""

    def test_system_log(self):
        r = TOOL.call("event_log", {"log_name": "System", "max_events": 5})
        assert_success(r)
