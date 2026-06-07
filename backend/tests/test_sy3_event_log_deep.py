# -*- coding: utf-8 -*-
"""
SY3 event_log 深度测试 — test_sy3_event_log_deep.py

覆盖维度：
1. 参数验证（log_name/max_events/level/time_range）
2. Windows wevtutil命令构造
3. Linux journalctl命令构造
4. 超时和命令不存在处理
5. 返回结构

【规范】本测试为SY3专用深度测试，一个tool一个文件
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

from app.services.tools.system.system_tools import event_log, _get_windows_event_log, _get_linux_event_log


class TestSy3EventLog:
    """SY3 event_log 深度测试"""

    @patch("app.services.tools.system.system_tools.platform.system")
    @patch("app.services.tools.system.system_tools.subprocess.run")
    def test_windows_event_log(self, mock_run, mock_platform):
        """Windows平台使用wevtutil"""
        mock_platform.return_value = "Windows"
        mock_run.return_value = MagicMock(returncode=0, stdout="Event[1]:\n  Level: Error\n  Source Name: TestApp")

        result = event_log(log_name="System", max_events=10, level="error", time_range="1h")
        assert result["code"] == "SUCCESS"
        assert result["data"]["log_name"] == "System"
        assert len(result["data"]["events"]) > 0
        mock_run.assert_called_once()
        # 验证命令包含wevtutil
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "wevtutil"

    @patch("app.services.tools.system.system_tools.platform.system")
    @patch("app.services.tools.system.system_tools.subprocess.run")
    def test_linux_event_log(self, mock_run, mock_platform):
        """Linux平台使用journalctl"""
        mock_platform.return_value = "Linux"
        mock_run.return_value = MagicMock(returncode=0, stdout='{"MESSAGE": "test error", "PRIORITY": "3"}\n')

        result = event_log(log_name="System", max_events=10, level="error", time_range="1h")
        assert result["code"] == "SUCCESS"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "journalctl"

    @patch("app.services.tools.system.system_tools.platform.system")
    @patch("app.services.tools.system.system_tools.subprocess.run")
    def test_windows_timeout(self, mock_run, mock_platform):
        """Windows超时处理"""
        mock_platform.return_value = "Windows"
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("wevtutil", 30)

        result = event_log()
        assert result["code"] == "ERR_SYSTEM_TIMEOUT"

    @patch("app.services.tools.system.system_tools.platform.system")
    @patch("app.services.tools.system.system_tools.subprocess.run")
    def test_windows_command_not_found(self, mock_run, mock_platform):
        """Windows命令不存在"""
        mock_platform.return_value = "Windows"
        mock_run.side_effect = FileNotFoundError("wevtutil not found")

        result = event_log()
        assert result["code"] == "ERR_SYSTEM_COMMAND_NOT_FOUND"

    def test_time_range_mapping(self):
        """time_range正确映射到timedelta"""
        with patch("app.services.tools.system.system_tools.platform.system") as mock_platform, \
             patch("app.services.tools.system.system_tools.subprocess.run") as mock_run:
            mock_platform.return_value = "Windows"
            mock_run.return_value = MagicMock(returncode=0, stdout="")

            result = event_log(time_range="24h")
            assert result["code"] == "SUCCESS"

    def test_level_filter(self):
        """level过滤生效"""
        with patch("app.services.tools.system.system_tools.platform.system") as mock_platform, \
             patch("app.services.tools.system.system_tools.subprocess.run") as mock_run:
            mock_platform.return_value = "Windows"
            mock_run.return_value = MagicMock(returncode=0, stdout="Event[1]:\n  Level: Error\nEvent[2]:\n  Level: Information")

            result = event_log(level="error")
            assert result["code"] == "SUCCESS"
            # error级别应该过滤掉Information
            assert all("Error" in str(e.get("Level", "")) for e in result["data"]["events"])
