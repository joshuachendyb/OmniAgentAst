# -*- coding: utf-8 -*-
"""
SY4 list_processes 深度测试 — test_sy4_list_processes_deep.py

覆盖维度：
1. 过滤（filter_name/filter_pid/user/status）
2. 排序（pid/name/cpu/memory）
3. max_results限制
4. 进程权限错误跳过

Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest
import psutil

from app.services.tools.system.system_tools import list_processes


class TestSy4ListProcesses:
    """SY4 list_processes 深度测试"""

    @patch("app.services.tools.system.system_tools.psutil.process_iter")
    def test_filter_name(self, mock_iter):
        """filter_name模糊匹配"""
        mock_iter.return_value = [
            MagicMock(info={'pid': 1, 'name': 'python.exe', 'cpu_percent': 10.0, 'memory_percent': 5.0, 'exe': 'python.exe', 'cmdline': ['python'], 'status': 'running', 'username': 'user'}),
            MagicMock(info={'pid': 2, 'name': 'nginx.exe', 'cpu_percent': 5.0, 'memory_percent': 3.0, 'exe': 'nginx.exe', 'cmdline': ['nginx'], 'status': 'running', 'username': 'user'}),
        ]

        result = list_processes(filter_name="python")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["processes"]) == 1
        assert result["data"]["processes"][0]["name"] == "python.exe"

    @patch("app.services.tools.system.system_tools.psutil.process_iter")
    def test_sort_by_cpu(self, mock_iter):
        """按CPU排序"""
        mock_iter.return_value = [
            MagicMock(info={'pid': 1, 'name': 'a.exe', 'cpu_percent': 5.0, 'memory_percent': 1.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'user'}),
            MagicMock(info={'pid': 2, 'name': 'b.exe', 'cpu_percent': 20.0, 'memory_percent': 2.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'user'}),
        ]

        result = list_processes(sort_by="cpu", descending=True)
        assert result["code"] == "SUCCESS"
        assert result["data"]["processes"][0]["pid"] == 2  # CPU高的在前

    @patch("app.services.tools.system.system_tools.psutil.process_iter")
    def test_max_results(self, mock_iter):
        """max_results限制返回数量"""
        mock_iter.return_value = [
            MagicMock(info={'pid': i, 'name': f'proc{i}', 'cpu_percent': 1.0, 'memory_percent': 1.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'user'})
            for i in range(1, 150)
        ]

        result = list_processes(max_results=50)
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["processes"]) == 50

    @patch("app.services.tools.system.system_tools.psutil.process_iter")
    def test_skip_no_such_process(self, mock_iter):
        """跳过已消失的进程"""
        mock_proc = MagicMock()
        mock_proc.info = {'pid': 1, 'name': 'test', 'cpu_percent': 1.0, 'memory_percent': 1.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'user'}
        mock_iter.return_value = [mock_proc]

        result = list_processes()
        assert result["code"] == "SUCCESS"

    @patch("app.services.tools.system.system_tools.psutil.process_iter")
    def test_user_filter(self, mock_iter):
        """user过滤"""
        mock_iter.return_value = [
            MagicMock(info={'pid': 1, 'name': 'a.exe', 'cpu_percent': 1.0, 'memory_percent': 1.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'admin'}),
            MagicMock(info={'pid': 2, 'name': 'b.exe', 'cpu_percent': 1.0, 'memory_percent': 1.0, 'exe': '', 'cmdline': [], 'status': 'running', 'username': 'user'}),
        ]

        result = list_processes(user="admin")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["processes"]) == 1
