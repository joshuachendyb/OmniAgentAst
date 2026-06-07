# -*- coding: utf-8 -*-
"""
SY1 get_system_info 深度测试 — test_sy1_get_system_info_deep.py

覆盖维度：
1. 各info_type返回正确数据结构
2. 默认all返回全部信息
3. psutil异常处理
4. next_actions注入

【规范】本测试为SY1专用深度测试，一个tool一个文件
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest
import psutil

from app.services.tools.system.system_tools import get_system_info


class TestSy1GetSystemInfo:
    """SY1 get_system_info 深度测试"""

    @patch("app.services.tools.system.system_tools.psutil.cpu_freq")
    @patch("app.services.tools.system.system_tools.psutil.cpu_count")
    @patch("app.services.tools.system.system_tools.psutil.cpu_percent")
    @patch("app.services.tools.system.system_tools.psutil.virtual_memory")
    @patch("app.services.tools.system.system_tools.psutil.disk_partitions")
    @patch("app.services.tools.system.system_tools.psutil.disk_usage")
    @patch("app.services.tools.system.system_tools.psutil.net_io_counters")
    def test_all_info_type(self, mock_net, mock_disk_usage, mock_disk_parts,
                          mock_mem, mock_cpu_percent, mock_cpu_count, mock_cpu_freq):
        """info_type=all返回完整系统信息"""
        mock_cpu_freq.return_value = MagicMock(current=2400.0, min=800.0, max=3200.0)
        mock_cpu_count.side_effect = [4, 8]  # logical=False, logical=True
        mock_cpu_percent.return_value = 25.5
        mock_mem.return_value = MagicMock(total=16*1024**3, available=8*1024**3,
                                          used=8*1024**3, percent=50.0)
        mock_disk_parts.return_value = [
            MagicMock(device="C:", mountpoint="C:", fstype="NTFS")
        ]
        mock_disk_usage.return_value = MagicMock(total=500*1024**3, used=200*1024**3,
                                                free=300*1024**3, percent=40.0)
        mock_net.return_value = MagicMock(bytes_sent=100*1024**2, bytes_recv=200*1024**2,
                                         packets_sent=1000, packets_recv=2000)

        result = get_system_info("all")
        assert result["code"] == "SUCCESS"
        assert "basic" in result["data"]
        assert "cpu" in result["data"]
        assert "memory" in result["data"]
        assert "disk" in result["data"]
        assert "network" in result["data"]
        assert "next_actions" in result

    def test_basic_info_only(self):
        """info_type=basic只返回基础信息"""
        result = get_system_info("basic")
        assert result["code"] == "SUCCESS"
        assert "basic" in result["data"]
        assert "cpu" not in result["data"]
        assert "memory" not in result["data"]

    def test_cpu_info(self):
        """info_type=cpu返回CPU信息"""
        with patch("app.services.tools.system.system_tools.psutil.cpu_freq") as mock_freq, \
             patch("app.services.tools.system.system_tools.psutil.cpu_count") as mock_count, \
             patch("app.services.tools.system.system_tools.psutil.cpu_percent") as mock_percent:
            mock_freq.return_value = MagicMock(current=2400.0, min=800.0, max=3200.0)
            mock_count.side_effect = [4, 8]
            mock_percent.return_value = 30.0

            result = get_system_info("cpu")
            assert result["code"] == "SUCCESS"
            assert "cpu" in result["data"]
            assert result["data"]["cpu"]["physical_cores"] == 4
            assert result["data"]["cpu"]["logical_cores"] == 8

    def test_memory_info(self):
        """info_type=memory返回内存信息"""
        with patch("app.services.tools.system.system_tools.psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(total=16*1024**3, available=8*1024**3,
                                             used=8*1024**3, percent=50.0)
            result = get_system_info("memory")
            assert result["code"] == "SUCCESS"
            assert "memory" in result["data"]
            assert result["data"]["memory"]["total_gb"] == 16.0

    def test_disk_permission_error(self):
        """磁盘读取权限错误时跳过该分区"""
        with patch("app.services.tools.system.system_tools.psutil.disk_partitions") as mock_parts, \
             patch("app.services.tools.system.system_tools.psutil.disk_usage") as mock_usage:
            mock_parts.return_value = [
                MagicMock(device="C:", mountpoint="C:", fstype="NTFS"),
                MagicMock(device="D:", mountpoint="D:", fstype="NTFS")
            ]
            mock_usage.side_effect = [
                MagicMock(total=500*1024**3, used=200*1024**3, free=300*1024**3, percent=40.0),
                PermissionError("Access denied")
            ]

            result = get_system_info("disk")
            assert result["code"] == "SUCCESS"
            assert len(result["data"]["disk"]) == 1

    def test_invalid_info_type(self):
        """无效的info_type返回空数据但不报错"""
        result = get_system_info("invalid")
        assert result["code"] == "SUCCESS"
        assert result["data"] == {}
