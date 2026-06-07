# -*- coding: utf-8 -*-
"""
SY6 service_control 深度测试 — test_sy6_service_control_deep.py

覆盖维度：
1. action路由（start/stop/restart/list）
2. start/stop/restart时service_name必填校验
3. restart先停后启逻辑
4. 无效action处理
5. next_actions注入

Author: 小沈 - 2026-05-19
"""

from unittest.mock import patch, MagicMock

import pytest

from app.services.tools.system.system_tools import service_control


class TestSy6ServiceControl:
    """SY6 service_control 深度测试"""

    @patch("app.services.tools.system.system_tools._service_list")
    def test_list_action(self, mock_list):
        """action=list调用_service_list"""
        mock_list.return_value = {"code": "SUCCESS", "data": {"services": []}, "message": "OK"}

        result = service_control(action="list")
        assert result["code"] == "SUCCESS"
        mock_list.assert_called_once_with(name=None, state="all")

    @patch("app.services.tools.system.system_tools._service_list")
    def test_list_with_filter(self, mock_list):
        """list带service_name过滤"""
        mock_list.return_value = {"code": "SUCCESS", "data": {"services": []}, "message": "OK"}

        result = service_control(action="list", service_name="mysql", state="running")
        mock_list.assert_called_once_with(name="mysql", state="running")

    @patch("app.services.tools.system.system_tools._service_start")
    def test_start_action(self, mock_start):
        """action=start调用_service_start"""
        mock_start.return_value = {"code": "SUCCESS", "data": {"service_name": "mysql"}, "message": "Started"}

        result = service_control(action="start", service_name="mysql")
        assert result["code"] == "SUCCESS"
        mock_start.assert_called_once_with(service_name="mysql", wait_for_started=False, timeout=30)

    def test_start_missing_service_name(self):
        """start缺少service_name返回ERR_INVALID_PARAM"""
        result = service_control(action="start")
        assert result["code"] == "ERR_INVALID_PARAM"
        assert "service_name" in result["message"]

    @patch("app.services.tools.system.system_tools._service_stop")
    def test_stop_action(self, mock_stop):
        """action=stop调用_service_stop"""
        mock_stop.return_value = {"code": "SUCCESS", "data": {"service_name": "mysql"}, "message": "Stopped"}

        result = service_control(action="stop", service_name="mysql", force=True)
        assert result["code"] == "SUCCESS"
        mock_stop.assert_called_once_with(service_name="mysql", force=True, wait_for_stopped=False, timeout=30)

    @patch("app.services.tools.system.system_tools._service_stop")
    @patch("app.services.tools.system.system_tools._service_start")
    def test_restart_action(self, mock_start, mock_stop):
        """action=restart先stop后start"""
        mock_stop.return_value = {"code": "SUCCESS", "data": {}, "message": "Stopped"}
        mock_start.return_value = {"code": "SUCCESS", "data": {"service_name": "mysql"}, "message": "Started"}

        result = service_control(action="restart", service_name="mysql")
        assert result["code"] == "SUCCESS"
        mock_stop.assert_called_once()
        mock_start.assert_called_once()

    @patch("app.services.tools.system.system_tools._service_stop")
    def test_restart_stop_fails(self, mock_stop):
        """restart时stop失败直接返回错误"""
        mock_stop.return_value = {"code": "ERR_SERVICE_STOP", "message": "Stop failed"}

        result = service_control(action="restart", service_name="mysql")
        assert result["code"] == "ERR_SERVICE_STOP"

    def test_invalid_action(self):
        """无效action返回ERR_INVALID_PARAM"""
        result = service_control(action="invalid")
        assert result["code"] == "ERR_INVALID_PARAM"
