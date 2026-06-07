# -*- coding: utf-8 -*-
"""
SY5 kill_process 深度测试 — test_sy5_kill_process_deep.py

覆盖维度：
1. 参数校验（pid必须>0）
2. 正常终止（SIGTERM→wait）
3. 强制终止（SIGKILL）
4. 超时后自动SIGKILL
5. 幂等性（进程不存在返回SUCCESS）
6. 权限拒绝

Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest
import psutil

from app.services.tools.system.system_tools import kill_process


class TestSy5KillProcess:
    """SY5 kill_process 深度测试"""

    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_normal_terminate(self, mock_process_cls):
        """正常终止流程"""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "test.exe"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_process_cls.return_value = mock_proc

        result = kill_process(pid=1234, force=False)
        assert result["code"] == "SUCCESS"
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_force_kill(self, mock_process_cls):
        """强制终止"""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "test.exe"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_process_cls.return_value = mock_proc

        result = kill_process(pid=1234, force=True)
        assert result["code"] == "SUCCESS"
        mock_proc.kill.assert_called_once()

    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_timeout_then_kill(self, mock_process_cls):
        """超时后自动SIGKILL"""
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.name.return_value = "test.exe"
        mock_proc.status.return_value = "running"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.wait.side_effect = [psutil.TimeoutExpired(1), None]  # 第一次超时，第二次成功
        mock_process_cls.return_value = mock_proc

        result = kill_process(pid=1234, force=False, timeout=1)
        assert result["code"] == "SUCCESS"
        assert mock_proc.kill.called  # 超时后调用了kill

    def test_invalid_pid_zero(self):
        """pid=0返回参数错误"""
        result = kill_process(pid=0)
        assert result["code"] == "ERR_INVALID_PARAM"

    def test_invalid_pid_negative(self):
        """pid=-1返回参数错误"""
        result = kill_process(pid=-1)
        assert result["code"] == "ERR_INVALID_PARAM"

    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_idempotent_no_such_process(self, mock_process_cls):
        """进程不存在时幂等返回SUCCESS"""
        mock_process_cls.side_effect = psutil.NoSuchProcess(1234)

        result = kill_process(pid=1234)
        assert result["code"] == "SUCCESS"
        assert result["data"]["idempotent"] is True

    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_access_denied(self, mock_process_cls):
        """权限不足"""
        mock_process_cls.side_effect = psutil.AccessDenied("Permission denied")

        result = kill_process(pid=1234)
        assert result["code"] == "ERR_PERMISSION_DENIED"
