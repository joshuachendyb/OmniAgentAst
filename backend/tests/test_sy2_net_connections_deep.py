# -*- coding: utf-8 -*-
"""
SY2 net_connections 深度测试 — test_sy2_net_connections_deep.py

覆盖维度：
1. kind过滤(tcp/udp)
2. state过滤
3. filter_port过滤
4. process_info获取进程名
5. 最多200条限制
6. AccessDenied异常处理

【规范】本测试为SY2专用深度测试，一个tool一个文件
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest
import socket
import psutil

from app.services.tools.system.system_tools import net_connections


class TestSy2NetConnections:
    """SY2 net_connections 深度测试"""

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    def test_kind_tcp_filter(self, mock_net_conn):
        """kind=tcp只返回TCP连接"""
        mock_net_conn.return_value = [
            MagicMock(fd=1, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="127.0.0.1", port=8080),
                     raddr=MagicMock(ip="192.168.1.1", port=443),
                     status="ESTABLISHED", pid=1234),
            MagicMock(fd=2, family=socket.AF_INET, type=socket.SOCK_DGRAM,
                     laddr=MagicMock(ip="0.0.0.0", port=53),
                     raddr=None,
                     status="NONE", pid=5678),
        ]

        result = net_connections(kind="tcp")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["connections"]) == 1
        assert result["data"]["connections"][0]["type"] == "TCP"

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    def test_state_filter(self, mock_net_conn):
        """state过滤生效"""
        mock_net_conn.return_value = [
            MagicMock(fd=1, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="0.0.0.0", port=80),
                     raddr=None,
                     status="LISTEN", pid=1234),
            MagicMock(fd=2, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="127.0.0.1", port=8080),
                     raddr=MagicMock(ip="192.168.1.1", port=443),
                     status="ESTABLISHED", pid=5678),
        ]

        result = net_connections(kind="inet", state="listen")
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["connections"]) == 1
        assert "LISTEN" in result["data"]["connections"][0]["status"]

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    def test_filter_port(self, mock_net_conn):
        """filter_port过滤指定端口"""
        mock_net_conn.return_value = [
            MagicMock(fd=1, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="0.0.0.0", port=80),
                     raddr=None,
                     status="LISTEN", pid=1234),
            MagicMock(fd=2, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="0.0.0.0", port=8080),
                     raddr=None,
                     status="LISTEN", pid=5678),
        ]

        result = net_connections(filter_port=8080)
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["connections"]) == 1
        assert ":8080" in result["data"]["connections"][0]["local_address"]

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    def test_max_200_limit(self, mock_net_conn):
        """最多返回200条连接"""
        mock_net_conn.return_value = [
            MagicMock(fd=i, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="127.0.0.1", port=1000+i),
                     raddr=None,
                     status="LISTEN", pid=1000+i)
            for i in range(250)
        ]

        result = net_connections()
        assert result["code"] == "SUCCESS"
        assert len(result["data"]["connections"]) == 200

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    def test_access_denied(self, mock_net_conn):
        """权限不足返回ERR_PERMISSION_DENIED"""
        mock_net_conn.side_effect = psutil.AccessDenied("Permission denied")

        result = net_connections()
        assert result["code"] == "ERR_PERMISSION_DENIED"

    @patch("app.services.tools.system.system_tools.psutil.net_connections")
    @patch("app.services.tools.system.system_tools.psutil.Process")
    def test_process_info(self, mock_process, mock_net_conn):
        """process=True时获取进程名"""
        mock_net_conn.return_value = [
            MagicMock(fd=1, family=socket.AF_INET, type=socket.SOCK_STREAM,
                     laddr=MagicMock(ip="0.0.0.0", port=80),
                     raddr=None,
                     status="LISTEN", pid=1234),
        ]
        mock_proc = MagicMock()
        mock_proc.name.return_value = "nginx"
        mock_proc.exe.return_value = "/usr/sbin/nginx"
        mock_process.return_value = mock_proc

        result = net_connections(process_info=True)
        assert result["code"] == "SUCCESS"
        assert result["data"]["connections"][0]["process_name"] == "nginx"
