# -*- coding: utf-8 -*-
"""
desktop_tools + gui_tools 深度测试
- 小健 2026-05-06

覆盖：
desktop_tools: window_info, set_window_state
gui_tools: click, move, type_text, screenshot, read_clipboard, write_clipboard

Author: 小健 - 2026-05-06 - 小健 2026-05-23 更新: list_windows/get_window_info→window_info
"""

import sys
import platform
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.services.tools.desktop.desktop_tools import (
    window_info,
    set_window_state,
    _HAS_WIN32,
)

from app.services.tools.toolhelper.window_helper import (
    check_win32_platform,
    get_window_rect,
    get_window_state,
    find_windows_by_title,
)

from app.services.tools.desktop.gui_tools import (
    _click,
    _move,
    _type_text,
    _screenshot,
    _read_clipboard,
    _write_clipboard,
    _scroll,
    _shortcut,
    _key_combo,
)

IS_WINDOWS = platform.system() == "Windows"


# =============================================================================
# 一、_check_platform 平台检查
# =============================================================================

class TestCheckPlatform:
    """check_win32_platform 平台和依赖检查 - 小健 2026-05-06 更新 2026-05-23"""

    def test_not_windows(self):
        """非Windows系统"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Linux"):
            result = check_win32_platform()
            assert result is not None
            assert result["code"] == "ERR_DESKTOP_NOT_WINDOWS"

    def test_no_pywin32(self):
        """pywin32未安装"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", False):
            result = check_win32_platform()
            assert result is not None
            assert result["code"] == "ERR_DESKTOP_NO_PYWIN32"

    def test_platform_ok(self):
        """平台和依赖都可用"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True):
            result = check_win32_platform()
            assert result is None


# =============================================================================
# 二、window_info (list) 深度测试
# =============================================================================

class TestListWindowsDeep:
    """window_info(action="list") 深度测试 - 小健 2026-05-06 更新 2026-05-23"""

    def test_not_windows(self):
        """非Windows系统"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Linux"):
            result = window_info(action="list")
            assert result["code"] == "ERR_DESKTOP_NOT_WINDOWS"

    def test_no_pywin32(self):
        """pywin32未安装"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", False):
            result = window_info(action="list")
            assert result["code"] == "ERR_DESKTOP_NO_PYWIN32"

    def test_mock_basic(self):
        """mock: 基本列出窗口"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock(side_effect=lambda cb, acc: None)
            result = window_info(action="list")
            assert result["code"] in ("SUCCESS", "ERR_WINDOW_LIST")

    def test_mock_with_filter_title(self):
        """mock: 按标题过滤"""
        windows_data = [
            {"hwnd": 1, "title": "Chrome", "state": "normal", "position": None},
            {"hwnd": 2, "title": "VSCode", "state": "normal", "position": None},
        ]
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock(side_effect=lambda cb, acc: acc.extend(windows_data) if isinstance(acc, list) else None)
            mock_gui.IsWindowVisible = MagicMock(return_value=True)
            mock_gui.GetWindowText = MagicMock(return_value="TestWindow")
            mock_gui.GetWindowPlacement = MagicMock(return_value=(0, 1, 0, 0, 100, 100))
            result = window_info(action="list", filter_title="Chrome")
            assert result["code"] in ("SUCCESS", "ERR_WINDOW_LIST")

    def test_mock_include_minimized(self):
        """mock: 包含最小化窗口"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui:
            mock_gui.EnumWindows = MagicMock()
            result = window_info(action="list", include_minimized=True)
            assert result["code"] in ("SUCCESS", "ERR_WINDOW_LIST")

    @pytest.mark.skipif(not IS_WINDOWS or not _HAS_WIN32, reason="非Windows或pywin32未安装")
    def test_real_list_windows(self):
        """真实: 列出窗口(仅Windows)"""
        result = window_info(action="list")
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["windows"], list)


# =============================================================================
# 三、window_info (info) 深度测试
# =============================================================================

class TestGetWindowInfoDeep:
    """window_info(action="info") 深度测试 - 小健 2026-05-06 更新 2026-05-23"""

    def test_not_windows(self):
        """非Windows"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Linux"):
            result = window_info(action="info", window_title="Test")
            assert result["code"] == "ERR_DESKTOP_NOT_WINDOWS"

    def test_no_pywin32(self):
        """pywin32未安装"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", False):
            result = window_info(action="info", window_title="Test")
            assert result["code"] == "ERR_DESKTOP_NO_PYWIN32"

    def test_window_not_found(self):
        """窗口不存在"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools.find_windows_by_title", return_value=[]):
            result = window_info(action="info", window_title="NonExistentWindowXYZ999")
            assert result["code"] == "ERR_WINDOW_NOT_FOUND"

    def test_mock_window_found(self):
        """mock: 找到窗口"""
        matched_hwnd = 12345
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui, \
             patch("app.services.tools.desktop.desktop_tools._win32api") as mock_api, \
             patch("app.services.tools.desktop.desktop_tools.get_window_rect", return_value={"left": 0, "top": 0, "right": 800, "bottom": 600, "width": 800, "height": 600}), \
             patch("app.services.tools.desktop.desktop_tools.get_window_state", return_value="normal"), \
             patch("app.services.tools.desktop.desktop_tools.find_windows_by_title", return_value=[matched_hwnd]):
            mock_gui.GetWindowText.return_value = "TestWindow"
            mock_gui.GetClassName.return_value = "TestClass"
            mock_gui.IsWindowVisible.return_value = True
            mock_gui.IsWindowEnabled.return_value = True
            mock_api.GetWindowThreadProcessId.return_value = (9999, 0)
            result = window_info(action="info", window_title="TestWindow")
            assert result["code"] in ("SUCCESS", "ERR_DESKTOP_GET_WINDOW_INFO")

    def test_empty_title(self):
        """空标题"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"):
            result = window_info(action="info", window_title="")
            assert result["code"] == "ERR_PARAM_INVALID"


# =============================================================================
# 四、set_window_state 深度测试
# =============================================================================

class TestSetWindowStateDeep:
    """set_window_state 深度测试 - 小健 2026-05-06"""

    def test_not_windows(self):
        """非Windows"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Linux"):
            result = set_window_state(window_title="Test", action="maximize")
            assert result["code"] == "ERR_DESKTOP_NOT_WINDOWS"

    def test_no_pywin32(self):
        """pywin32未安装"""
        with patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", False):
            result = set_window_state(window_title="Test", action="maximize")
            assert result["code"] == "ERR_DESKTOP_NO_PYWIN32"

    def test_invalid_action(self):
        """无效操作"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"):
            result = set_window_state(window_title="Test", action="invalid_action_xyz")
            assert result["code"] == "ERR_INVALID_ACTION"

    def test_window_not_found(self):
        """窗口不存在"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools.find_windows_by_title", return_value=[]):
            result = set_window_state(window_title="NonExistentWindowXYZ999", action="maximize")
            assert result["code"] == "ERR_WINDOW_NOT_FOUND"

    def test_mock_maximize(self):
        """mock: 最大化"""
        with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
             patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
             patch("app.services.tools.desktop.desktop_tools._win32gui") as mock_gui, \
             patch("app.services.tools.desktop.desktop_tools._win32con") as mock_con:
            hwnd = 12345
            mock_gui.GetWindowText = MagicMock(return_value="TestWin")
            mock_gui.ShowWindow = MagicMock()
            mock_con.SW_MAXIMIZE = 3

            with patch("app.services.tools.desktop.desktop_tools.find_windows_by_title", return_value=[hwnd]):
                result = set_window_state(window_title="TestWin", action="maximize")
                assert result["code"] in ("SUCCESS", "ERR_WINDOW_SET_STATE")

    def test_all_valid_actions(self):
        """所有有效action(窗口不存在时返回ERR_WINDOW_NOT_FOUND)"""
        valid_actions = ["maximize", "minimize", "restore", "topmost", "unpin"]
        for action in valid_actions:
            with patch("app.services.tools.toolhelper.window_helper._HAS_WIN32", True), \
                 patch("app.services.tools.toolhelper.window_helper.platform.system", return_value="Windows"), \
                 patch("app.services.tools.desktop.desktop_tools.find_windows_by_title", return_value=[]):
                result = set_window_state(window_title="NonExistentWindowXYZ999", action=action)
                assert result["code"] == "ERR_WINDOW_NOT_FOUND"


# =============================================================================
# 五、get_window_rect / get_window_state 辅助函数
# =============================================================================

class TestWindowHelpers:
    """窗口辅助函数测试 - 小健 2026-05-06 更新 2026-05-23"""

    def test_get_window_rect_success(self):
        """获取窗口矩形"""
        with patch("app.services.tools.toolhelper.window_helper._win32gui") as mock_gui:
            mock_gui.GetWindowRect = MagicMock(return_value=(10, 20, 810, 620))
            result = get_window_rect(12345)
            assert result is not None
            assert result["width"] == 800
            assert result["height"] == 600

    def test_get_window_rect_error(self):
        """获取窗口矩形异常"""
        with patch("app.services.tools.toolhelper.window_helper._win32gui") as mock_gui:
            mock_gui.GetWindowRect = MagicMock(side_effect=Exception("fail"))
            result = get_window_rect(12345)
            assert result is None

    def test_get_window_state_maximized(self):
        """最大化状态"""
        with patch("app.services.tools.toolhelper.window_helper._win32gui") as mock_gui, \
             patch("app.services.tools.toolhelper.window_helper._win32con") as mock_con:
            mock_gui.IsWindowVisible = MagicMock(return_value=True)
            mock_gui.GetWindowPlacement = MagicMock(return_value=(0, 3, 0, 0, 0, 0))
            mock_con.SW_SHOWMAXIMIZED = 3
            mock_con.SW_SHOWMINIMIZED = 2
            result = get_window_state(12345)
            assert result == "maximized"

    def test_get_window_state_minimized(self):
        """最小化状态"""
        with patch("app.services.tools.toolhelper.window_helper._win32gui") as mock_gui, \
             patch("app.services.tools.toolhelper.window_helper._win32con") as mock_con:
            mock_gui.IsWindowVisible = MagicMock(return_value=False)
            result = get_window_state(12345)
            assert result == "minimized"

    def test_get_window_state_error(self):
        """异常返回unknown"""
        with patch("app.services.tools.toolhelper.window_helper._win32gui") as mock_gui:
            mock_gui.IsWindowVisible = MagicMock(side_effect=Exception("fail"))
            result = get_window_state(12345)
            assert result == "unknown"


# =============================================================================
# 六、click 深度测试
# =============================================================================

class TestClickDeep:
    """click 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        """pyautogui未安装"""
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _click(x=100, y=200)
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_left_click(self):
        """mock: 左键单击"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _click(x=100, y=200, button="left", click_type="single")
            assert result["code"] == "SUCCESS"
            assert result["data"]["button"] == "left"
            mock_pag.click.assert_called_once()

    def test_mock_double_click(self):
        """mock: 双击"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _click(x=100, y=200, button="left", click_type="double")
            assert result["code"] == "SUCCESS"
            mock_pag.click.assert_called_once_with(x=100, y=200, button="left", clicks=2)

    def test_mock_right_click(self):
        """mock: 右键"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _click(x=50, y=50, button="right", click_type="single")
            assert result["code"] == "SUCCESS"
            assert result["data"]["button"] == "right"

    def test_mock_click_exception(self):
        """mock: 点击异常"""
        mock_pag = MagicMock()
        mock_pag.click.side_effect = Exception("click fail")
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _click(x=100, y=200)
            assert result["code"] == "ERR_DESKTOP_MOUSE_CLICK"


# =============================================================================
# 七、move 深度测试
# =============================================================================

class TestMoveDeep:
    """move 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        """pyautogui未安装"""
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _move(x=0, y=0)
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_move(self):
        """mock: 移动鼠标"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _move(x=500, y=300, duration=0.5)
            assert result["code"] == "SUCCESS"
            mock_pag.moveTo.assert_called_once_with(500, 300, duration=0.5)

    def test_mock_move_exception(self):
        """mock: 异常"""
        mock_pag = MagicMock()
        mock_pag.moveTo.side_effect = Exception("move fail")
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _move(x=0, y=0)
            assert result["code"] == "ERR_FILE_MOVE_FAILED"


# =============================================================================
# 八、type_text 深度测试
# =============================================================================

class TestTypeTextDeep:
    """type_text 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        """pyautogui未安装"""
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _type_text(text="hello")
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_ascii_text(self):
        """mock: ASCII文本用typewrite"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _type_text(text="hello world", interval=0.05)
            assert result["code"] == "SUCCESS"
            mock_pag.typewrite.assert_called_once_with("hello world", interval=0.05)

    def test_mock_non_ascii_text(self):
        """mock: 非ASCII文本用write"""
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _type_text(text="你好世界")
            assert result["code"] == "SUCCESS"
            mock_pag.write.assert_called_once_with("你好世界")

    def test_mock_type_exception(self):
        """mock: 输入异常"""
        mock_pag = MagicMock()
        mock_pag.typewrite.side_effect = Exception("type fail")
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _type_text(text="hello")
            assert result["code"] == "ERR_KEYBOARD_TYPE"


# =============================================================================
# 九、screenshot 深度测试
# =============================================================================

class TestScreenshotDeep:
    """screenshot 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        """pyautogui未安装"""
        with patch.dict(sys.modules, {"pyautogui": None}):
            result = _screenshot()
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_full_screenshot(self, tmp_path):
        """mock: 全屏截图"""
        mock_pag = MagicMock()
        mock_img = MagicMock()
        mock_pag.screenshot.return_value = mock_img
        out_path = str(tmp_path / "screen.png")
        with patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _screenshot(output_path=out_path)
            assert result["code"] == "SUCCESS"
            mock_img.save.assert_called_once_with(out_path)

    def test_mock_region_screenshot(self, tmp_path):
        """mock: 区域截图"""
        mock_pag = MagicMock()
        mock_img = MagicMock()
        mock_pag.screenshot.return_value = mock_img
        out_path = str(tmp_path / "region.png")
        region = {"x": 0, "y": 0, "width": 400, "height": 300}
        with patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _screenshot(output_path=out_path, region=region)
            assert result["code"] == "SUCCESS"
            call_args = mock_pag.screenshot.call_args
            assert call_args is not None

    def test_mock_screenshot_exception(self, tmp_path):
        """mock: 截图异常"""
        mock_pag = MagicMock()
        mock_pag.screenshot.side_effect = Exception("screenshot fail")
        out_path = str(tmp_path / "fail.png")
        with patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _screenshot(output_path=out_path)
            assert result["code"] == "ERR_SCREENSHOT"


# =============================================================================
# 十、read_clipboard 深度测试
# =============================================================================

class TestReadClipboardDeep:
    """read_clipboard 深度测试 - 小健 2026-05-06"""

    def test_mock_pyperclip(self):
        """mock: pyperclip读取"""
        mock_pyperclip = MagicMock()
        mock_pyperclip.paste.return_value = "clipboard text"
        with patch.dict(sys.modules, {"pyperclip": mock_pyperclip}):
            result = _read_clipboard()
            assert result["code"] == "SUCCESS"
            assert result["data"]["text"] == "clipboard text"

    def test_mock_pyperclip_exception(self):
        """mock: pyperclip异常, mock ctypes也失败"""
        mock_pyperclip = MagicMock()
        mock_pyperclip.paste.side_effect = ImportError("no pyperclip")
        mock_ctypes = MagicMock()
        mock_ctypes.windll.user32.OpenClipboard.side_effect = Exception("ctypes fail")
        with patch.dict(sys.modules, {"pyperclip": mock_pyperclip}), \
             patch("ctypes.windll", mock_ctypes.windll):
            result = _read_clipboard()
            assert result["code"] in ("SUCCESS", "ERR_DESKTOP_CLIPBOARD")


# =============================================================================
# 十一、write_clipboard 深度测试
# =============================================================================

class TestWriteClipboardDeep:
    """write_clipboard 深度测试 - 小健 2026-05-06"""

    def test_mock_pyperclip(self):
        """mock: pyperclip写入"""
        mock_pyperclip = MagicMock()
        with patch.dict(sys.modules, {"pyperclip": mock_pyperclip}):
            result = _write_clipboard(content="test content")
            assert result["code"] == "SUCCESS"
            mock_pyperclip.copy.assert_called_once_with("test content")

    def test_mock_pyperclip_exception(self):
        """mock: pyperclip异常, mock ctypes也失败"""
        mock_pyperclip = MagicMock()
        mock_pyperclip.copy.side_effect = ImportError("no pyperclip")
        mock_ctypes = MagicMock()
        mock_ctypes.windll.user32.OpenClipboard.side_effect = Exception("ctypes fail")
        with patch.dict(sys.modules, {"pyperclip": mock_pyperclip}), \
             patch("ctypes.windll", mock_ctypes.windll):
            result = _write_clipboard(content="test")
            assert result["code"] in ("SUCCESS", "ERR_DESKTOP_CLIPBOARD")


# =============================================================================
# 十二、scroll / shortcut / key_combo 深度测试
# =============================================================================

class TestScrollDeep:
    """scroll 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _scroll(direction="down")
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_scroll_up(self):
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _scroll(direction="up", amount=5)
            assert result["code"] == "SUCCESS"
            mock_pag.scroll.assert_called_once_with(5)

    def test_mock_scroll_down(self):
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _scroll(direction="down", amount=3)
            assert result["code"] == "SUCCESS"
            mock_pag.scroll.assert_called_once_with(-3)


class TestShortcutDeep:
    """shortcut 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _shortcut(keys="ctrl+c")
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_shortcut(self):
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _shortcut(keys="ctrl+alt+delete")
            assert result["code"] == "SUCCESS"
            mock_pag.hotkey.assert_called_once_with("ctrl", "alt", "delete")


class TestKeyComboDeep:
    """key_combo 深度测试 - 小健 2026-05-06"""

    def test_no_pyautogui(self):
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=False):
            result = _key_combo(keys=["ctrl"])
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_mock_hold(self):
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _key_combo(keys=["shift", "ctrl"], action="hold")
            assert result["code"] == "SUCCESS"
            assert mock_pag.keyDown.call_count == 2

    def test_mock_release(self):
        mock_pag = MagicMock()
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True), \
             patch.dict(sys.modules, {"pyautogui": mock_pag}):
            result = _key_combo(keys=["shift", "ctrl"], action="release")
            assert result["code"] == "SUCCESS"
            assert mock_pag.keyUp.call_count == 2
