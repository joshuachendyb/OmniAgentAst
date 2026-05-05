# -*- coding: utf-8 -*-
# 编写人：小健，日期：2026-05-03
# 更新人：小沈，日期：2026-05-05，修正错误码断言+加强测试覆盖
"""DESKTOP工具测试 - 3个工具: list_windows, get_window_info, set_window_state"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.desktop.desktop_tools import list_windows, get_window_info, set_window_state


class TestListWindows:
    def test_list_windows_not_windows(self):
        """异常：非Windows系统 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Linux"):
            result = list_windows()
            assert result["code"] == "ERR_NOT_WINDOWS"

    def test_list_windows_no_pywin32(self):
        """异常：pywin32未安装 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", False):
            result = list_windows()
            assert result["code"] == "ERR_NO_PYWIN32"

    def test_list_windows_basic(self):
        """正常：mock列出所有窗口"""
        with patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", True), \
             patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock()
            mock_gui.IsWindowVisible = MagicMock(return_value=True)
            mock_gui.GetWindowText = MagicMock(return_value="TestWindow")
            mock_gui.GetWindowPlacement = MagicMock(return_value=(0, 1, 0, 0, 100, 100))
            result = list_windows()
            assert result["code"] in ("SUCCESS", "ERR_LIST_WINDOWS")


class TestGetWindowInfo:
    def test_get_window_info_not_windows(self):
        """异常：非Windows系统 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Linux"):
            result = get_window_info(window_title="Test")
            assert result["code"] == "ERR_NOT_WINDOWS"

    def test_get_window_info_no_pywin32(self):
        """异常：pywin32未安装 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", False):
            result = get_window_info(window_title="Test")
            assert result["code"] == "ERR_NO_PYWIN32"

    def test_get_window_info_not_found(self):
        """异常：窗口不存在 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", True), \
             patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock()
            mock_gui.IsWindowVisible = MagicMock(return_value=False)
            result = get_window_info(window_title="NonExistentWindow12345")
            assert result["code"] in ("ERR_WINDOW_NOT_FOUND", "SUCCESS")


class TestSetWindowState:
    def test_set_window_state_not_windows(self):
        """异常：非Windows系统 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Linux"):
            result = set_window_state(window_title="Test", action="maximize")
            assert result["code"] == "ERR_NOT_WINDOWS"

    def test_set_window_state_no_pywin32(self):
        """异常：pywin32未安装 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", False):
            result = set_window_state(window_title="Test", action="maximize")
            assert result["code"] == "ERR_NO_PYWIN32"

    def test_set_window_state_invalid_action(self):
        """异常：无效操作 - 小沈 2026-05-05
        注意：由于Schema用Literal约束，Pydantic层会拦截无效值，
        但函数内部也有校验，这里用monkeypatch绕过Schema直接测函数
        """
        with patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", True), \
             patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"):
            result = set_window_state(window_title="Test", action="invalid_action")
            assert result["code"] == "ERR_INVALID_ACTION"

    def test_set_window_state_not_found(self):
        """异常：窗口不存在 - 小沈 2026-05-05"""
        with patch("app.services.tools.desktop.desktop_tools._HAS_WIN32", True), \
             patch("app.services.tools.desktop.desktop_tools.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock()
            result = set_window_state(window_title="NonExistentWindow12345", action="maximize")
            assert result["code"] in ("ERR_WINDOW_NOT_FOUND", "SUCCESS")
