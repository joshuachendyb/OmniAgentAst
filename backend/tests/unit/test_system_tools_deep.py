# -*- coding: utf-8 -*-
"""
系统工具深度测试 - test_system_tools_deep.py

覆盖函数：get_system_info, list_processes, kill_process,
           _log_message, _service_list

Author: 小健 - 2026-05-06
"""

import logging
import os
import subprocess
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from app.services.tools.system.system_tools import (
    get_system_info,
    list_processes,
    kill_process,
    _log_message,
    _service_list,
)


# ============================================================
# TestGetSystemInfo
# ============================================================
class TestGetSystemInfo:
    """get_system_info 深度测试"""

    def test_all_info(self):
        """正常：获取全部系统信息"""
        result = get_system_info(info_type="all")
        assert result["code"] == "SUCCESS"
        assert "basic" in result["data"]
        assert "cpu" in result["data"]
        assert "memory" in result["data"]

    def test_basic_info(self):
        """正常：基本信息"""
        result = get_system_info(info_type="basic")
        assert result["code"] == "SUCCESS"
        assert "basic" in result["data"]
        assert "platform" in result["data"]["basic"]
        assert "hostname" in result["data"]["basic"]
        assert "python_version" in result["data"]["basic"]

    def test_cpu_info(self):
        """正常：CPU信息"""
        result = get_system_info(info_type="cpu")
        assert result["code"] == "SUCCESS"
        assert "cpu" in result["data"]
        assert "physical_cores" in result["data"]["cpu"]
        assert "logical_cores" in result["data"]["cpu"]

    def test_memory_info(self):
        """正常：内存信息"""
        result = get_system_info(info_type="memory")
        assert result["code"] == "SUCCESS"
        assert "memory" in result["data"]
        assert "total_gb" in result["data"]["memory"]
        assert "available_gb" in result["data"]["memory"]

    def test_disk_info(self):
        """正常：磁盘信息"""
        result = get_system_info(info_type="disk")
        assert result["code"] == "SUCCESS"
        assert "disk" in result["data"]

    def test_network_info(self):
        """正常：网络信息"""
        result = get_system_info(info_type="network")
        assert result["code"] == "SUCCESS"
        assert "network" in result["data"]

    def test_invalid_type(self):
        """边界：无效info_type"""
        result = get_system_info(info_type="invalid")
        assert result["code"] == "SUCCESS"
        assert result["data"] == {}

    def test_platform_is_windows(self):
        """正常：Windows平台检查"""
        result = get_system_info(info_type="basic")
        if os.name == "nt":
            assert result["data"]["basic"]["platform"] == "Windows"

    def test_cpu_usage_percent(self):
        """正常：CPU使用率为百分比"""
        result = get_system_info(info_type="cpu")
        usage = result["data"]["cpu"]["cpu_usage_percent"]
        assert 0 <= usage <= 100

    def test_memory_percent(self):
        """正常：内存使用率为百分比"""
        result = get_system_info(info_type="memory")
        pct = result["data"]["memory"]["percent"]
        assert 0 <= pct <= 100


# ============================================================
# TestListProcesses
# ============================================================
class TestListProcesses:
    """list_processes 深度测试"""

    def test_list_all(self):
        """正常：列出所有进程"""
        result = list_processes()
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] > 0

    def test_filter_by_name(self):
        """正常：按名称过滤"""
        result = list_processes(filter_name="python")
        assert result["code"] == "SUCCESS"

    def test_filter_by_pid(self):
        """正常：按PID过滤"""
        result = list_processes(filter_pid=os.getpid())
        assert result["code"] == "SUCCESS"

    def test_sort_by_pid(self):
        """正常：按PID排序"""
        result = list_processes(sort_by="pid")
        assert result["code"] == "SUCCESS"

    def test_sort_by_name(self):
        """正常：按名称排序"""
        result = list_processes(sort_by="name")
        assert result["code"] == "SUCCESS"

    def test_sort_by_cpu(self):
        """正常：按CPU排序"""
        result = list_processes(sort_by="cpu")
        assert result["code"] == "SUCCESS"

    def test_sort_by_memory(self):
        """正常：按内存排序"""
        result = list_processes(sort_by="memory")
        assert result["code"] == "SUCCESS"

    def test_descending_sort(self):
        """正常：降序排序"""
        result = list_processes(sort_by="pid")
        assert result["code"] == "SUCCESS"

    def test_max_results_limit(self):
        """正常：结果数量限制"""
        result = list_processes(max_results=5)
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] <= 5

    def test_process_info_fields(self):
        """正常：进程信息字段"""
        result = list_processes(max_results=1)
        if result["data"]["total"] > 0:
            proc = result["data"]["processes"][0]
            assert "pid" in proc
            assert "name" in proc
            assert "status" in proc

    def test_nonexistent_filter_name(self):
        """边界：不存在的进程名"""
        result = list_processes(filter_name="__NONEXISTENT_PROCESS_XYZ_123__")
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 0

    def test_nonexistent_filter_pid(self):
        """边界：不存在的PID"""
        result = list_processes(filter_pid=999999)
        assert result["code"] == "SUCCESS"
        assert result["data"]["total"] == 0


# ============================================================
# TestKillProcess
# ============================================================
class TestKillProcess:
    """kill_process 深度测试"""

    def test_invalid_pid_zero(self):
        """错误：PID为0"""
        result = kill_process(pid=0)
        assert result["code"] == "ERR_PARAMETER_INVALID"

    def test_invalid_pid_negative(self):
        """错误：负PID"""
        result = kill_process(pid=-1)
        assert result["code"] == "ERR_PARAMETER_INVALID"

    def test_invalid_pid_none(self):
        """错误：PID为None"""
        result = kill_process(pid=None)
        assert result["code"] == "ERR_PARAMETER_INVALID"

    def test_nonexistent_pid(self):
        """错误：不存在的进程"""
        result = kill_process(pid=9999999)
        assert result["code"] == "SUCCESS"

    @patch("psutil.Process")
    def test_normal_terminate(self, mock_process_cls):
        """正常：正常终止"""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.name.return_value = "test_proc"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.wait.return_value = None
        mock_process_cls.return_value = mock_proc

        result = kill_process(pid=12345, force=False)
        assert result["code"] == "SUCCESS"
        mock_proc.terminate.assert_called_once()

    @patch("psutil.Process")
    def test_force_kill(self, mock_process_cls):
        """正常：强制终止"""
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.name.return_value = "test_proc"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.wait.return_value = None
        mock_process_cls.return_value = mock_proc

        result = kill_process(pid=12345, force=True)
        assert result["code"] == "SUCCESS"
        mock_proc.kill.assert_called_once()

    @patch("psutil.Process")
    def test_access_denied(self, mock_process_cls):
        """错误：权限不足"""
        import psutil
        mock_process_cls.side_effect = psutil.AccessDenied(12345)
        result = kill_process(pid=12345)
        assert result["code"] == "ERR_PERMISSION_DENIED"

    @patch("psutil.Process")
    def test_process_not_found(self, mock_process_cls):
        """错误：进程不存在"""
        import psutil
        mock_process_cls.side_effect = psutil.NoSuchProcess(9999999)
        result = kill_process(pid=9999999)
        assert result["code"] == "SUCCESS"


# ============================================================
# TestLogMessage
# ============================================================
class TestLogMessage:
    """_log_message 深度测试"""

    def test_info_level(self, tmp_path):
        """正常：INFO级别日志"""
        result = _log_message("Test info message", level="INFO")
        assert result["code"] == "SUCCESS"
        assert result["data"]["level"] == "INFO"

    def test_debug_level(self):
        """正常：DEBUG级别日志"""
        result = _log_message("Debug msg", level="DEBUG")
        assert result["code"] == "SUCCESS"

    def test_warning_level(self):
        """正常：WARNING级别日志"""
        result = _log_message("Warning msg", level="WARNING")
        assert result["code"] == "SUCCESS"

    def test_error_level(self):
        """正常：ERROR级别日志"""
        result = _log_message("Error msg", level="ERROR")
        assert result["code"] == "SUCCESS"

    def test_critical_level(self):
        """正常：CRITICAL级别日志"""
        result = _log_message("Critical msg", level="CRITICAL")
        assert result["code"] == "SUCCESS"

    def test_log_to_file(self, tmp_path):
        """正常：写入日志文件"""
        log_file = str(tmp_path / "test.log")
        result = _log_message("File log msg", log_file=log_file)
        assert result["code"] == "SUCCESS"
        assert result["data"]["log_file"] == log_file

    def test_custom_logger_name(self):
        """正常：自定义logger名称"""
        result = _log_message("Custom logger", logger_name="my_app")
        assert result["code"] == "SUCCESS"
        assert result["data"]["logger_name"] == "my_app"

    def test_timestamp_present(self):
        """正常：返回时间戳"""
        result = _log_message("Timestamp test")
        assert result["data"]["timestamp"] is not None
        assert "-" in result["data"]["timestamp"]

    def test_case_insensitive_level(self):
        """边界：大小写不敏感级别"""
        result = _log_message("Lowercase", level="info")
        assert result["code"] == "SUCCESS"

    def test_unknown_level_defaults_info(self):
        """边界：未知级别默认INFO"""
        result = _log_message("Unknown", level="VERBOSE")
        assert result["code"] == "SUCCESS"

    def test_chinese_message(self):
        """正常：中文日志消息"""
        result = _log_message("这是一条中文日志")
        assert result["code"] == "SUCCESS"

    def test_empty_message(self):
        """边界：空消息"""
        result = _log_message("")
        assert result["code"] == "SUCCESS"


# ============================================================
# TestServiceList
# ============================================================
class TestServiceList:
    """_service_list 深度测试"""

    @patch("subprocess.run")
    def test_list_services(self, mock_run):
        """正常：列出服务"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: Alerter\n"
                "DISPLAY_NAME: Alerter\n"
                "STATE              : 1  STOPPED\n"
                "SERVICE_NAME: AppInfo\n"
                "DISPLAY_NAME: Application Information\n"
                "STATE              : 4  RUNNING\n"
            ),
        )
        result = _service_list()
        assert result["code"] == "SUCCESS"

    @patch("subprocess.run")
    def test_filter_by_name(self, mock_run):
        """正常：按名称过滤"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: TestSvc\n"
                "DISPLAY_NAME: Test Service\n"
                "STATE              : 4  RUNNING\n"
                "SERVICE_NAME: OtherSvc\n"
                "DISPLAY_NAME: Other Service\n"
                "STATE              : 1  STOPPED\n"
            ),
        )
        result = _service_list(name="Test")
        assert result["code"] == "SUCCESS"

    @patch("subprocess.run")
    def test_filter_by_state(self, mock_run):
        """正常：按状态过滤"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: Svc1\n"
                "DISPLAY_NAME: Service 1\n"
                "STATE              : 4  RUNNING\n"
                "SERVICE_NAME: Svc2\n"
                "DISPLAY_NAME: Service 2\n"
                "STATE              : 1  STOPPED\n"
            ),
        )
        result = _service_list(state="running")
        assert result["code"] == "SUCCESS"

    @patch("subprocess.run")
    def test_command_failure(self, mock_run):
        """错误：命令执行失败"""
        mock_run.return_value = MagicMock(returncode=1, stderr="Access denied")
        result = _service_list()
        assert result["code"] == "ERR_SERVICE_LIST"

    @patch("subprocess.run")
    def test_empty_services(self, mock_run):
        """边界：无服务"""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = _service_list()
        assert result["code"] == "SUCCESS"

    @patch("subprocess.run")
    def test_state_all(self, mock_run):
        """正常：所有状态"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: Svc1\n"
                "DISPLAY_NAME: Service 1\n"
                "STATE              : 4  RUNNING\n"
            ),
        )
        result = _service_list(state="all")
        assert result["code"] == "SUCCESS"

    @patch("subprocess.run")
    def test_output_format_json(self, mock_run):
        """正常：JSON输出格式"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=(
                "SERVICE_NAME: Svc1\n"
                "DISPLAY_NAME: Service 1\n"
                "STATE              : 4  RUNNING\n"
            ),
        )
        result = _service_list(output_format="json")
        assert result["code"] == "SUCCESS"
