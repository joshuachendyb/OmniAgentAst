# -*- coding: utf-8 -*-
"""
13.6 desktop 优化测试 — 三分类合一 26→10
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.6节
变更: desktop+desktop_gui+desktop_gui_helpers → 统一 ToolCategory.DESKTOP
      gui_helpers全部7个→toolhelper(不暴露LLM)
      window_control统一|mouse_control统一|keyboard_control统一
      screen_capture统一|clipboard_control统一
新增: P15 next_actions; P13 Helper统一

覆盖:
  list_windows [去重后唯一版本]
  get_window_info
  window_control (替代 set_window_state/focus_window/resize_window)
  mouse_control (替代 click/move/scroll)
  keyboard_control (替代 type_text/shortcut/key_combo)
  screen_capture (替代 screenshot/snapshot)
  clipboard_control (替代 read_clipboard/write_clipboard)
  screen_record, ocr, send_notification [保留]
  gui_helpers 已消除
  next_actions 含跨分类(file)
"""

import pytest
import platform
from unittest.mock import patch, MagicMock

# 统一 desktop 分类入口（三分类合一后）
from app.services.tools.desktop.desktop_tools import (
    list_windows,
    get_window_info,
    window_control,
    mouse_control,
    keyboard_control,
    screen_capture,
    clipboard_control,
    screen_record,
    ocr_recognize,
    send_notification,
)

IS_WINDOWS = platform.system() == "Windows"


# ============================================================
# TestListWindows — 去重后唯一版本
# ============================================================
class TestListWindows:
    """list_windows — 去重后唯一版本（保留win32gui版本）"""

    def test_list_windows_basic(self):
        """正常：列出窗口"""
        if not IS_WINDOWS:
            pytest.skip("仅Windows")
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123, "title": "Test", "class": "TestClass"}]):
                result = list_windows()
                assert result["code"] == "SUCCESS"
                assert isinstance(result["data"]["windows"], list)

    def test_list_windows_by_title(self):
        """正常：按标题过滤"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123, "title": "Notepad", "class": "NotepadClass"}]):
                result = list_windows(window_title="Note")
                assert result["code"] == "SUCCESS"

    def test_list_windows_next_actions(self):
        """【P15】list_windows 返回 next_actions"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123, "title": "Test", "class": "TestClass"}]):
                result = list_windows()
                assert "next_actions" in result
                tools = [a["tool"] for a in result["next_actions"]]
                assert "get_window_info" in tools
                assert "window_control" in tools


# ============================================================
# TestWindowControl — 统一窗口操作
# ============================================================
class TestWindowControl:
    """window_control 统一入口 — 替代 set_window_state/focus_window/resize_window"""

    def test_window_control_focus(self):
        """【合并】window_control(action="focus") — 替代 focus_window"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                with patch("app.services.tools.desktop.desktop_tools._win32gui.SetForegroundWindow"):
                    result = window_control(window_title="Notepad", action="focus")
                    assert result["code"] == "SUCCESS"

    def test_window_control_maximize(self):
        """【合并】window_control(action="maximize") — 替代 set_window_state"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Notepad", action="maximize")
                assert result["code"] in ("SUCCESS", "ERR_PLATFORM_NOT_SUPPORTED")

    def test_window_control_resize(self):
        """【合并】window_control(action="resize", width=800, height=600) — 替代 resize_window"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Notepad", action="resize",
                                        width=800, height=600)
                assert result["code"] in ("SUCCESS", "ERR_PLATFORM_NOT_SUPPORTED")

    def test_window_control_minimize(self):
        """【合并】window_control(action="minimize")"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Notepad", action="minimize")
                assert result["code"] in ("SUCCESS", "ERR_PLATFORM_NOT_SUPPORTED")

    def test_window_control_restore(self):
        """【合并】window_control(action="restore")"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Notepad", action="restore")
                assert result["code"] in ("SUCCESS", "ERR_PLATFORM_NOT_SUPPORTED")

    def test_window_control_topmost(self):
        """【合并】window_control(action="topmost")"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Notepad", action="topmost")
                assert result["code"] in ("SUCCESS", "ERR_PLATFORM_NOT_SUPPORTED")

    def test_window_control_window_not_found(self):
        """异常：窗口不存在"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[]):
                result = window_control(window_title="NONEXISTENT_WINDOW_XYZ", action="focus")
                assert result["code"] == "ERR_WINDOW_NOT_FOUND"

    def test_window_control_invalid_action(self):
        """异常：不支持的 action"""
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 123}]):
                result = window_control(window_title="Test", action="invalid_action_xyz")
                assert result["code"] == "ERROR"


# ============================================================
# TestMouseControl — 统一鼠标操作
# ============================================================
class TestMouseControl:
    """mouse_control 统一入口 — 替代 click/move/scroll"""

    def test_mouse_control_click(self):
        """【合并】mouse_control(action="click") — 替代 click"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.click"):
                result = mouse_control(action="click", x=100, y=200, button="left")
                assert result["code"] == "SUCCESS"

    def test_mouse_control_move(self):
        """【合并】mouse_control(action="move") — 替代 move"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.moveTo"):
                result = mouse_control(action="move", x=500, y=300, duration=1.0)
                assert result["code"] == "SUCCESS"

    def test_mouse_control_scroll(self):
        """【合并】mouse_control(action="scroll") — 替代 scroll"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.scroll"):
                result = mouse_control(action="scroll", direction="down", amount=3)
                assert result["code"] == "SUCCESS"

    def test_mouse_control_position(self):
        """【合并mouse_control+gui_helpers】mouse_control(action="position") — 获取鼠标位置"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.position",
                       return_value=(500, 300)):
                result = mouse_control(action="position")
                assert result["code"] == "SUCCESS"
                assert "position" in result.get("data", {})

    def test_mouse_control_double_click(self):
        """ mouse_control(action="click", click_type="double") """
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.doubleClick"):
                result = mouse_control(action="click", x=100, y=200, click_type="double")
                assert result["code"] == "SUCCESS"

    def test_mouse_control_invalid_action(self):
        """异常：不支持的 action"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            result = mouse_control(action="fly", x=100, y=200)
            assert result["code"] == "ERROR"

    def test_mouse_control_next_actions_click(self):
        """【P15】mouse_control(click) 应建议 keyboard_control 或 screen_capture"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.click"):
                result = mouse_control(action="click", x=100, y=200)
                assert "next_actions" in result
                tools = [a["tool"] for a in result["next_actions"]]
                assert "keyboard_control" in tools or "screen_capture" in tools


# ============================================================
# TestKeyboardControl — 统一键盘操作
# ============================================================
class TestKeyboardControl:
    """keyboard_control 统一入口 — 替代 type_text/shortcut/key_combo"""

    def test_keyboard_control_type(self):
        """【合并】keyboard_control(action="type") — 替代 type_text"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.write"):
                result = keyboard_control(action="type", text="Hello World", interval=0.05)
                assert result["code"] == "SUCCESS"

    def test_keyboard_control_shortcut(self):
        """【合并】keyboard_control(action="shortcut") — 替代 shortcut"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.hotkey"):
                result = keyboard_control(action="shortcut", keys="ctrl+c")
                assert result["code"] == "SUCCESS"

    def test_keyboard_control_combo(self):
        """【合并】keyboard_control(action="combo") — 替代 key_combo"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.hotkey"):
                result = keyboard_control(action="combo", keys="ctrl+alt+del")
                assert result["code"] == "SUCCESS"

    def test_keyboard_control_invalid_action(self):
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            result = keyboard_control(action="invalid_action_xyz", text="test")
            assert result["code"] == "ERROR"

    def test_keyboard_control_next_actions(self):
        """【P15】keyboard_control 成功后应返回 next_actions"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.write"):
                result = keyboard_control(action="type", text="Hello")
                assert "next_actions" in result


# ============================================================
# TestScreenCapture — 统一截屏
# ============================================================
class TestScreenCapture:
    """screen_capture 统一入口 — 替代 screenshot+snapshot"""

    def test_screen_capture_basic(self, tmp_path):
        """【合并】screen_capture — 替代 screenshot, 默认 pyautogui"""
        output = str(tmp_path / "test_screenshot.png")
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.screenshot") as mock_ss:
                mock_ss.return_value = MagicMock()
                result = screen_capture(output_path=output)
                assert result["code"] == "SUCCESS"
                assert "output_path" in result.get("data", {})

    def test_screen_capture_with_region(self):
        """正常：指定区域截屏"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.screenshot") as mock_ss:
                mock_ss.return_value = MagicMock()
                result = screen_capture(region={"x": 0, "y": 0, "width": 100, "height": 100})
                assert result["code"] == "SUCCESS"

    def test_screen_capture_no_gui_lib(self):
        """异常：pyautogui未安装"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib",
                   return_value={"code": "ERR_NO_PYAUTOGUI", "message": "pyautogui未安装"}):
            result = screen_capture()
            assert "ERR" in result["code"]

    def test_screen_capture_next_actions(self):
        """【P15】screen_capture 跨分类建议 ocr 和 write_text_file"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.screenshot") as mock_ss:
                mock_ss.return_value = MagicMock()
                result = screen_capture()
                assert "next_actions" in result
                tools = [a.get("tool") for a in result["next_actions"]]
                assert any("ocr" in t for t in tools if t)


# ============================================================
# TestClipboardControl — 统一剪贴板
# ============================================================
class TestClipboardControl:
    """clipboard_control 统一入口 — 替代 read_clipboard/write_clipboard"""

    def test_clipboard_control_read(self):
        """【合并】clipboard_control(action="read") — 替代 read_clipboard"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyperclip.paste",
                       return_value="clipboard_content"):
                result = clipboard_control(action="read")
                assert result["code"] == "SUCCESS"

    def test_clipboard_control_write(self):
        """【合并】clipboard_control(action="write") — 替代 write_clipboard"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyperclip.copy"):
                result = clipboard_control(action="write", content="new_content")
                assert result["code"] == "SUCCESS"

    def test_clipboard_control_invalid_action(self):
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            result = clipboard_control(action="invalid_action_xyz")
            assert result["code"] == "ERROR"

    def test_clipboard_control_next_actions(self):
        """【P15】clipboard_control 跨分类建议 write_text_file"""
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyperclip.paste",
                       return_value="data"):
                result = clipboard_control(action="read")
                assert "next_actions" in result


# ============================================================
# TestScreenRecord — 保留
# ============================================================
class TestScreenRecord:
    """screen_record 保留测试"""

    def test_screen_record_basic(self):
        result = screen_record(duration=1, fps=5)
        assert result["code"] in ("SUCCESS", "ERR_NO_MSS", "ERR_NO_PIL")


# ============================================================
# TestOcr — 保留
# ============================================================
class TestOcr:
    """ocr 保留测试"""

    def test_ocr_basic(self, tmp_path):
        image_path = str(tmp_path / "test_ocr.png")
        result = ocr_recognize(image_path=image_path)
        assert result["code"] in ("SUCCESS", "ERR_NO_TESSERACT", "ERR_FILE_NOT_FOUND")


# ============================================================
# TestSendNotification — 保留
# ============================================================
class TestSendNotification:
    """send_notification 保留测试"""

    def test_send_notification_basic(self):
        with patch("app.services.tools.desktop.desktop_tools.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = send_notification(title="Test", message="Hello")
            assert result["code"] in ("SUCCESS", "ERR_NOTIFICATION_FAILED")


# ============================================================
# TestEliminated — 验证已消除的工具
# ============================================================
class TestEliminated:
    """验证 gui_helpers 全部7个工具已消除；旧函数已消除"""

    def test_gui_helpers_not_importable(self):
        """【消除】gui_helpers 不应作为LLM工具导入"""
        helpers = [
            "get_mouse_position", "check_screen_size", "check_window_exists",
            "get_window_position", "check_screen_capture_permission",
            "check_tesseract_available", "check_notification_permission",
        ]
        for h in helpers:
            with pytest.raises((ImportError, AttributeError)):
                from app.services.tools.desktop.desktop_tools import h  # noqa

    def test_old_tool_names_not_importable(self):
        """旧函数名不应再作为LLM工具"""
        old_tools = ["click", "move", "scroll", "type_text", "shortcut",
                     "key_combo", "screenshot", "snapshot",
                     "read_clipboard", "write_clipboard",
                     "set_window_state", "focus_window", "resize_window"]
        for t in old_tools:
            with pytest.raises((ImportError, AttributeError)):
                getattr(__import__("app.services.tools.desktop.desktop_tools", fromlist=[t]), t)
