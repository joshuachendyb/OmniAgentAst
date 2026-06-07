"""
desktop类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
import os
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty, TEMP_DIR

TOOL = ToolClient()


class TestListWindows:
    """list_windows 多场景测试"""

    def test_list_all(self):
        r = TOOL.call("list_windows", {})
        assert_success(r)

    def test_list_with_filter(self):
        r = TOOL.call("list_windows", {"filter_title": "python"})
        assert_success(r)


class TestGetWindowInfo:
    """get_window_info 多场景测试"""

    def test_get_existing_window(self):
        list_r = TOOL.call("list_windows", {})
        data = list_r.get("data", {})
        windows = data.get("windows", data.get("list", []))
        if windows and isinstance(windows, list):
            title = windows[0].get("title", "")
            if title:
                r = TOOL.call("get_window_info", {"window_title": title})
                assert_success(r)
        else:
            pytest.skip("没有可用窗口")


class TestScreenCapture:
    """screen_capture 多场景测试"""

    def test_capture_full(self):
        r = TOOL.call("screen_capture", {})
        assert_success(r)
        data = r.get("data", {})
        assert isinstance(data, dict), f"screen_capture应返回dict data (Bug #7), 实际: {type(data)}"
        assert "image_path" in data, f"data应包含image_path (Bug #7), 实际keys: {list(data.keys())}"

    def test_capture_with_path(self):
        fp = str(TEMP_DIR / "capture_test.png")
        r = TOOL.call("screen_capture", {"output_path": fp})
        assert_success(r)


class TestClipboardControl:
    """clipboard_control 多场景测试"""

    def test_set_and_get(self):
        set_r = TOOL.call("clipboard_control", {"action": "write", "content": "test_clipboard_value"})
        assert_success(set_r)
        get_r = TOOL.call("clipboard_control", {"action": "read"})
        assert_success(get_r)


class TestSendNotification:
    """send_notification 多场景测试"""

    def test_send(self):
        r = TOOL.call("send_notification", {"title": "测试通知", "message": "集成测试通知", "duration": 2})
        code = r.get("code", "")
        assert code in ("SUCCESS", "ERR_NO_WIN10TOAST"), f"send_notification应成功或缺依赖, 实际: {code}"


class TestKeyboardControl:
    """keyboard_control - 仅验证接口可调用"""

    def test_type_text(self):
        r = TOOL.call("keyboard_control", {"action": "type", "text_or_keys": "test"})
        assert_success(r)


class TestMouseControl:
    """mouse_control - 仅验证接口可调用"""

    def test_move(self):
        r = TOOL.call("mouse_control", {"action": "move", "x": 100, "y": 100})
        assert_success(r)
