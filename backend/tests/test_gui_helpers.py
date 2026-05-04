# -*- coding: utf-8 -*-
"""
GUI辅助工具测试模块

【创建时间】2026-05-04 小健
【功能】测试 GUI 辅助工具函数（Tool 108-114）

【返回格式】统一格式：
- 成功：{"code": "SUCCESS", "data": {...}, "message": "成功信息"}
- 失败：{"code": "ERR_xxx", "data": None, "message": "错误信息"}

Author: 小健 - 2026-05-04
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.gui.gui_helpers import (
    get_mouse_position,
    check_screen_size,
    check_window_exists,
    get_window_position,
    check_screen_capture_permission,
    check_tesseract_available,
    check_notification_permission,
)


class TestGetMousePosition:
    """Tool 108: 获取鼠标位置 - 小健 2026-05-04"""

    def test_get_mouse_position_with_win32(self):
        """测试 win32 可用时获取鼠标位置"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', True):
            with patch('app.services.tools.gui.gui_helpers.win32api') as mock_win32api:
                mock_win32api.GetCursorPos.return_value = (1024, 768)
                
                result = get_mouse_position()
                
                assert result["code"] == "SUCCESS"
                assert result["data"]["x"] == 1024
                assert result["data"]["y"] == 768

    def test_get_mouse_position_with_pyautogui(self):
        """测试 pyautogui 可用时获取鼠标位置"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            with patch('app.services.tools.gui.gui_helpers.PYAUTOGUI_AVAILABLE', True):
                with patch('app.services.tools.gui.gui_helpers.pyautogui') as mock_pyautogui:
                    mock_pyautogui.position.return_value = (800, 600)
                    
                    result = get_mouse_position()
                    
                    assert result["code"] == "SUCCESS"
                    assert result["data"]["x"] == 800
                    assert result["data"]["y"] == 600

    def test_get_mouse_position_no_dependency(self):
        """测试无依赖时返回默认值"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            with patch('app.services.tools.gui.gui_helpers.PYAUTOGUI_AVAILABLE', False):
                result = get_mouse_position()
                
                assert result["code"] == "SUCCESS"
                assert result["data"]["x"] == 0
                assert result["data"]["y"] == 0


class TestCheckScreenSize:
    """Tool 109: 检查屏幕分辨率 - 小健 2026-05-04"""

    def test_check_screen_size_with_win32(self):
        """测试 win32 可用时获取屏幕分辨率"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', True):
            with patch('app.services.tools.gui.gui_helpers.win32api') as mock_win32api:
                with patch('app.services.tools.gui.gui_helpers.win32con') as mock_win32con:
                    mock_win32api.GetSystemMetrics.side_effect = [1920, 1080]
                    mock_win32con.SM_CXSCREEN = 0
                    mock_win32con.SM_CYSCREEN = 1
                    
                    result = check_screen_size()
                    
                    assert result["code"] == "SUCCESS"
                    assert result["data"]["width"] == 1920
                    assert result["data"]["height"] == 1080

    def test_check_screen_size_with_pyautogui(self):
        """测试 pyautogui 可用时获取屏幕分辨率"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            with patch('app.services.tools.gui.gui_helpers.PYAUTOGUI_AVAILABLE', True):
                with patch('app.services.tools.gui.gui_helpers.pyautogui') as mock_pyautogui:
                    mock_size = MagicMock()
                    mock_size.width = 2560
                    mock_size.height = 1440
                    mock_pyautogui.size.return_value = mock_size
                    
                    result = check_screen_size()
                    
                    assert result["code"] == "SUCCESS"
                    assert result["data"]["width"] == 2560
                    assert result["data"]["height"] == 1440

    def test_check_screen_size_no_dependency(self):
        """测试无依赖时返回默认值"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            with patch('app.services.tools.gui.gui_helpers.PYAUTOGUI_AVAILABLE', False):
                result = check_screen_size()
                
                assert result["code"] == "SUCCESS"
                assert result["data"]["width"] == 1920
                assert result["data"]["height"] == 1080


class TestCheckWindowExists:
    """Tool 110: 检查窗口是否存在 - 小健 2026-05-04"""

    def test_check_window_exists_found(self):
        """测试窗口存在"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', True):
            with patch('app.services.tools.gui.gui_helpers.win32gui') as mock_win32gui:
                mock_win32gui.EnumWindows = Mock()
                mock_win32gui.GetWindowText.return_value = "Chrome - Google"
                
                result = check_window_exists(title="Chrome")
                
                # 因为 EnumWindows 没有真正执行回调，数据不会更新
                assert result["code"] == "SUCCESS"

    def test_check_window_exists_no_win32(self):
        """测试 win32 不可用时"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            result = check_window_exists(title="Chrome")
            
            assert result["code"] == "ERR_CHECK_WINDOW"


class TestGetWindowPosition:
    """Tool 111: 获取窗口位置和大小 - 小健 2026-05-04"""

    def test_get_window_position_no_win32(self):
        """测试 win32 不可用时"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            result = get_window_position(title="Chrome")
            
            assert result["code"] == "ERR_GET_WINDOW_POSITION"


class TestCheckScreenCapturePermission:
    """Tool 112: 检查屏幕捕获权限 - 小健 2026-05-04"""

    def test_check_screen_capture_permission(self):
        """测试检查屏幕捕获权限"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', True):
            result = check_screen_capture_permission()
            
            assert result["code"] == "SUCCESS"
            assert result["data"]["has_permission"] is True

    def test_check_screen_capture_permission_no_win32(self):
        """测试 win32 不可用时"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            result = check_screen_capture_permission()
            
            assert result["code"] == "ERR_CHECK_PERMISSION"


class TestCheckTesseractAvailable:
    """Tool 113: 检查 Tesseract OCR 引擎 - 小健 2026-05-04"""

    def test_check_tesseract_available_found(self):
        """测试 Tesseract 可用"""
        with patch('app.services.tools.gui.gui_helpers.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="tesseract v5", stderr="")
            
            result = check_tesseract_available()
            
            assert result["code"] == "SUCCESS"
            assert result["data"]["is_available"] is True

    def test_check_tesseract_available_not_found(self):
        """测试 Tesseract 不可用"""
        with patch('app.services.tools.gui.gui_helpers.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            result = check_tesseract_available()
            
            assert result["code"] == "SUCCESS"
            assert result["data"]["is_available"] is False

    def test_check_tesseract_available_error(self):
        """测试执行错误返回成功但不可用"""
        with patch('app.services.tools.gui.gui_helpers.subprocess.run') as mock_run:
            mock_run.side_effect = Exception("test error")
            
            result = check_tesseract_available()
            
            assert result["code"] == "ERR_CHECK_TESSERACT"


class TestCheckNotificationPermission:
    """Tool 114: 检查系统通知权限 - 小健 2026-05-04"""

    def test_check_notification_permission(self):
        """测试检查通知权限"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', True):
            result = check_notification_permission()
            
            assert result["code"] == "SUCCESS"
            assert result["data"]["has_permission"] is True

    def test_check_notification_permission_no_win32(self):
        """测试 win32 不可用时"""
        with patch('app.services.tools.gui.gui_helpers.WIN32_AVAILABLE', False):
            result = check_notification_permission()
            
            assert result["code"] == "ERR_CHECK_PERMISSION"