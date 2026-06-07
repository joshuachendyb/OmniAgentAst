# -*- coding: utf-8 -*-
"""
N5 network_diagnose 深度测试 — test_n5_network_diagnose_deep.py

覆盖维度：
1. mode=ping分发到_ping
2. mode=port分发到_port_check（检查port必填）
3. 无效mode处理
4. 成功返回注入next_actions
5. _ping和_port_check的错误透传

【规范】本测试为N5专用深度测试
Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.tools.network.network_tools import network_diagnose


# ============================================================
# 1. Ping模式测试
# ============================================================
class TestN5PingMode:
    """N5 ping模式测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_ping_mode_success(self, mock_ping):
        """mode=ping成功调用_ping"""
        mock_ping.return_value = {
            "code": "SUCCESS",
            "data": {"host": "8.8.8.8", "is_reachable": True},
            "message": "Ping成功",
        }
        result = await network_diagnose(host="8.8.8.8", mode="ping")
        assert result["code"] == "SUCCESS"
        mock_ping.assert_called_once_with(host="8.8.8.8", count=4, timeout=5)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_ping_mode_custom_count_timeout(self, mock_ping):
        """mode=ping自定义count和timeout"""
        mock_ping.return_value = {
            "code": "SUCCESS",
            "data": {"host": "baidu.com", "is_reachable": True},
            "message": "Ping成功",
        }
        result = await network_diagnose(host="baidu.com", mode="ping", count=10, timeout=10)
        assert result["code"] == "SUCCESS"
        mock_ping.assert_called_once_with(host="baidu.com", count=10, timeout=10)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_ping_mode_default(self, mock_ping):
        """mode默认值为ping"""
        mock_ping.return_value = {
            "code": "SUCCESS",
            "data": {"host": "127.0.0.1", "is_reachable": True},
            "message": "Ping成功",
        }
        result = await network_diagnose(host="127.0.0.1")
        assert result["code"] == "SUCCESS"
        mock_ping.assert_called_once_with(host="127.0.0.1", count=4, timeout=5)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_ping_mode_ignores_port(self, mock_ping):
        """mode=ping时port参数被忽略"""
        mock_ping.return_value = {
            "code": "SUCCESS",
            "data": {"host": "8.8.8.8", "is_reachable": True},
            "message": "Ping成功",
        }
        result = await network_diagnose(host="8.8.8.8", mode="ping", port=80)
        assert result["code"] == "SUCCESS"
        # _ping不应该接收port参数
        mock_ping.assert_called_once_with(host="8.8.8.8", count=4, timeout=5)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_ping_error_pass_through(self, mock_ping):
        """_ping错误透传"""
        mock_ping.return_value = {
            "code": "ERR_NETWORK_INVALID_HOST",
            "data": None,
            "message": "目标主机地址不能为空",
        }
        result = await network_diagnose(host="", mode="ping")
        assert result["code"] == "ERR_NETWORK_INVALID_HOST"
        assert "next_actions" not in result  # 错误时不应添加next_actions


# ============================================================
# 2. Port模式测试
# ============================================================
class TestN5PortMode:
    """N5 port模式测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._port_check")
    async def test_port_mode_success(self, mock_port_check):
        """mode=port成功调用_port_check"""
        mock_port_check.return_value = {
            "code": "SUCCESS",
            "data": {"host": "8.8.8.8", "port": 53, "is_open": True},
            "message": "端口开放",
        }
        result = await network_diagnose(host="8.8.8.8", mode="port", port=53)
        assert result["code"] == "SUCCESS"
        mock_port_check.assert_called_once_with(host="8.8.8.8", port=53, timeout=5)

    @pytest.mark.asyncio
    async def test_port_mode_missing_port(self):
        """mode=port但port未提供 → ERR_MISSING_PARAM"""
        result = await network_diagnose(host="8.8.8.8", mode="port")
        assert result["code"] == "ERR_MISSING_PARAM"
        assert "port参数必填" in result["message"]

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._port_check")
    async def test_port_mode_custom_timeout(self, mock_port_check):
        """mode=port自定义timeout"""
        mock_port_check.return_value = {
            "code": "SUCCESS",
            "data": {"host": "127.0.0.1", "port": 8000, "is_open": False},
            "message": "端口关闭",
        }
        result = await network_diagnose(host="127.0.0.1", mode="port", port=8000, timeout=10)
        assert result["code"] == "SUCCESS"
        mock_port_check.assert_called_once_with(host="127.0.0.1", port=8000, timeout=10)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._port_check")
    async def test_port_mode_ignores_count(self, mock_port_check):
        """mode=port时count参数被忽略"""
        mock_port_check.return_value = {
            "code": "SUCCESS",
            "data": {"host": "127.0.0.1", "port": 80, "is_open": True},
            "message": "端口开放",
        }
        result = await network_diagnose(host="127.0.0.1", mode="port", port=80, count=10)
        assert result["code"] == "SUCCESS"
        mock_port_check.assert_called_once_with(host="127.0.0.1", port=80, timeout=5)

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._port_check")
    async def test_port_error_pass_through(self, mock_port_check):
        """_port_check错误透传"""
        mock_port_check.return_value = {
            "code": "ERR_NETWORK_INVALID_PORT",
            "data": None,
            "message": "端口号无效",
        }
        result = await network_diagnose(host="127.0.0.1", mode="port", port=70000)
        assert result["code"] == "ERR_NETWORK_INVALID_PORT"
        assert "next_actions" not in result


# ============================================================
# 3. 无效模式测试
# ============================================================
class TestN5InvalidMode:
    """N5 无效模式测试"""

    @pytest.mark.asyncio
    async def test_invalid_mode(self):
        """无效mode → ERR_INVALID_MODE"""
        result = await network_diagnose(host="8.8.8.8", mode="invalid")
        assert result["code"] == "ERR_INVALID_MODE"
        assert "必须是 ping 或 port" in result["message"]


# ============================================================
# 4. next_actions测试
# ============================================================
class TestN5NextActions:
    """N5 next_actions注入测试"""

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._ping")
    async def test_success_adds_next_actions(self, mock_ping):
        """成功时添加next_actions"""
        mock_ping.return_value = {
            "code": "SUCCESS",
            "data": {"host": "8.8.8.8", "is_reachable": True},
            "message": "Ping成功",
        }
        result = await network_diagnose(host="8.8.8.8", mode="ping")
        assert result["code"] == "SUCCESS"
        assert "next_actions" in result
        assert len(result["next_actions"]) > 0

    @pytest.mark.asyncio
    @patch("app.services.tools.network.network_tools._port_check")
    async def test_port_success_adds_next_actions(self, mock_port_check):
        """port模式成功时也添加next_actions"""
        mock_port_check.return_value = {
            "code": "SUCCESS",
            "data": {"host": "8.8.8.8", "port": 53, "is_open": True},
            "message": "端口开放",
        }
        result = await network_diagnose(host="8.8.8.8", mode="port", port=53)
        assert result["code"] == "SUCCESS"
        assert "next_actions" in result
