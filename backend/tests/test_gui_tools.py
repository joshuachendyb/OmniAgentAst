# -*- coding: utf-8 -*-
"""
GUI操作工具测试模块

【创建时间】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.gui.gui_tools import (
    click, move, scroll,
    type_text, shortcut, key_combo,
    screenshot, snapshot, screen_record,
    list_windows, focus_window, resize_window,
    ocr,
)


class TestMouseOps:
    """鼠标操作测试 - 小沈 2026-05-02"""

    def test_click_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = click(x=100, y=100)
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_move_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = move(x=100, y=100)
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_scroll_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = scroll(direction="down")
            assert result["code"] == "ERR_NO_PYAUTOGUI"


class TestKeyboardOps:
    """键盘操作测试 - 小沈 2026-05-02"""

    def test_type_text_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = type_text(text="hello")
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_shortcut_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = shortcut(keys="ctrl+c")
            assert result["code"] == "ERR_NO_PYAUTOGUI"

    def test_key_combo_no_pyautogui(self):
        try:
            import pyautogui
            pytest.skip("pyautogui installed")
        except ImportError:
            result = key_combo(keys=["ctrl", "c"])
            assert result["code"] == "ERR_NO_PYAUTOGUI"


class TestScreenOps:
    """屏幕操作测试 - 小沈 2026-05-02"""

    def test_screenshot(self):
        try:
            import pyautogui
        except ImportError:
            pytest.skip("pyautogui not installed")
        result = screenshot()
        assert result["code"] == "SUCCESS"
        assert result["data"].endswith(".png")
        if os.path.exists(result["data"]):
            os.unlink(result["data"])


class TestWindowOps:
    """窗口操作测试 - 小沈 2026-05-02"""

    def test_list_windows(self):
        try:
            import win32gui
        except ImportError:
            pytest.skip("pywin32 not installed")
        result = list_windows()
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["windows"], list)

    def test_focus_window_not_found(self):
        try:
            import win32gui
        except ImportError:
            pytest.skip("pywin32 not installed")
        result = focus_window(title="NonExistentWindowXYZ123")
        assert result["code"] == "ERR_WINDOW_NOT_FOUND"


class TestOcr:
    """OCR测试 - 小沈 2026-05-02"""

    def test_ocr_no_lib(self):
        try:
            import pytesseract
            from PIL import Image
            pytest.skip("pytesseract and PIL installed")
        except ImportError:
            result = ocr(image_path="D:/nonexistent.png")
            assert result["code"] == "ERR_NO_TESSERACT"

    def test_ocr_file_not_exists(self):
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            pytest.skip("pytesseract not installed")
        result = ocr(image_path="D:/nonexistent_ocr.png")
        assert result["code"] == "ERR_OCR"
