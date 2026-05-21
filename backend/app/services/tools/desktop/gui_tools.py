# -*- coding: utf-8 -*-
"""
GUI操作工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第9章 Tool 92-104 定义

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含12个工具：
- 鼠标: click, move, scroll
- 键盘: type_text, shortcut, key_combo
- 屏幕: screenshot, snapshot, screen_record
- 窗口: list_windows, focus_window, resize_window
- OCR: ocr

Author: 小沈 - 2026-05-02
"""

import os
import importlib
import tempfile
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from app.services.tools.tool_result_utils import build_next_actions, truncate_data_for_frontend, truncate_text  # 小沈 2026-05-20


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


# ========== 鼠标操作 ==========

def _click(
    x: int = None,
    y: int = None,
    button: str = "left",
    click_type: str = "single"
) -> Dict[str, Any]:
    """模拟鼠标点击 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装，请先执行: pip install pyautogui"}
    try:
        import pyautogui
        clicks = 2 if click_type == "double" else 1
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        return {"code": "SUCCESS", "data": {"x": x, "y": y, "button": button, "click_type": click_type}, "message": f"点击完成: ({x}, {y}) {button} {click_type}", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_DESKTOP_MOUSE_CLICK", "data": None, "message": f"点击失败: {str(e)}"}


def _move(x: int, y: int, duration: float = 0) -> Dict[str, Any]:
    """移动鼠标到指定位置 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return {"code": "SUCCESS", "data": {"x": x, "y": y}, "message": f"鼠标移动到: ({x}, {y})", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_FILE_MOVE_FAILED", "data": None, "message": f"移动失败: {str(e)}"}


def _scroll(direction: str, amount: int = 3) -> Dict[str, Any]:
    """模拟鼠标滚轮滚动 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        scroll_amount = -amount if direction == "down" else amount
        pyautogui.scroll(scroll_amount)
        return {"code": "SUCCESS", "data": {"direction": direction, "amount": amount}, "message": f"滚动完成: {direction} {amount}单位", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_DESKTOP_MOUSE_SCROLL", "data": None, "message": f"滚动失败: {str(e)}"}


# ========== 键盘操作 ==========

def _type_text(text: str, interval: float = 0) -> Dict[str, Any]:
    """模拟键盘输入文本 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        # ASCII字符使用typewrite（支持间隔），非ASCII使用write
        if text.isascii():
            pyautogui.typewrite(text, interval=interval)
        else:
            pyautogui.write(text)
        return {"code": "SUCCESS", "data": {"text_length": len(text)}, "message": f"输入文本完成: {len(text)}个字符", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_KEYBOARD_TYPE", "data": None, "message": f"输入文本失败: {str(e)}"}


def _shortcut(keys: str) -> Dict[str, Any]:
    """执行键盘快捷键组合 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return {"code": "SUCCESS", "data": {"keys": keys}, "message": f"快捷键执行完成: {keys}", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_KEYBOARD_SHORTCUT", "data": None, "message": f"快捷键执行失败: {str(e)}"}


def _key_combo(keys: List[str], action: str = "press") -> Dict[str, Any]:
    """按住多个键后释放 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        if action == "press":
            pyautogui.hotkey(*keys)
        elif action == "hold":
            for key in keys:
                pyautogui.keyDown(key)
        elif action == "release":
            for key in keys:
                pyautogui.keyUp(key)
        return {"code": "SUCCESS", "data": {"keys": keys, "action": action}, "message": f"按键操作完成: {keys} {action}", "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_KEY_COMBO", "data": None, "message": f"按键操作失败: {str(e)}"}


# ========== 屏幕操作 ==========

def _screenshot(output_path: str = None, region: Dict[str, int] = None) -> Dict[str, Any]:
    """截取屏幕截图 - 小沈 2026-05-02"""
    try:
        import pyautogui
    except ImportError:
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(tempfile.gettempdir(), f"screenshot_{timestamp}.png")

        if region:
            r = (region.get("x", 0), region.get("y", 0), region.get("width", 800), region.get("height", 600))
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return {"code": "SUCCESS", "data": {"image_path": output_path}, "message": f"截图保存到: {output_path}",
                "capabilities_used": ["pyautogui"]}
    except Exception as e:
        return {"code": "ERR_SCREENSHOT", "data": None, "message": f"截图失败: {str(e)}"}


def _snapshot(display: int = 1) -> Dict[str, Any]:
    """获取完整桌面状态快照 - 小沈 2026-05-02"""
    try:
        import mss
    except ImportError:
        try:
            import pyautogui
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
            img = pyautogui.screenshot()
            img.save(output_path)
            return {"code": "SUCCESS", "data": {"image_path": output_path, "display": display}, "message": f"快照保存到: {output_path}",
                    "capabilities_used": ["pyautogui"], "capabilities_missing": ["mss"]}
        except ImportError:
            return {"code": "ERR_NO_SCREENSHOT_LIB", "data": None, "message": "需要安装 mss 或 pyautogui 库"}
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
        with mss.mss() as sct:
            monitors = sct.monitors
            # display参数：1=主显示器，2=副显示器1，以此类推
            # monitors索引：0=全屏虚拟，1=显示器1，2=显示器2...
            # 无效值fallback到1（主显示器）
            if display < 1 or display >= len(monitors):
                mon_index = 1
            else:
                mon_index = display
            img = sct.grab(monitors[mon_index])
            from PIL import Image
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(output_path)
        return {"code": "SUCCESS", "data": {"image_path": output_path, "display": display, "monitors": len(monitors) - 1}, "message": f"快照保存到: {output_path}",
                "capabilities_used": ["mss", "PIL"]}
    except Exception as e:
        return {"code": "ERR_SCREEN_SNAPSHOT", "data": None, "message": f"快照失败: {str(e)}"}


def screen_record(duration: int, output_path: Optional[str] = None, fps: int = 15) -> Dict[str, Any]:
    """录制屏幕视频 - 小沈 2026-05-02"""
    try:
        import mss
        from PIL import Image
    except ImportError:
        return {"code": "ERR_NO_RECORD_LIB", "data": None, "message": "需要安装 mss 和 PIL 库"}
    try:
        import numpy  # 移到循环前导入 - 小沈 2026-05-04
    except ImportError:
        return {"code": "ERR_NO_NUMPY", "data": None, "message": "需要安装 numpy 库"}
    try:
        import imageio.v2 as imageio
    except ImportError:
        try:
            import imageio
        except ImportError:
            return {"code": "ERR_NO_IMAGEIO", "data": None, "message": "需要安装 imageio 库: pip install imageio imageio-ffmpeg"}
    try:
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(tempfile.gettempdir(), f"screen_record_{timestamp}.mp4")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        import time
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            frames = []
            start_time = time.time()
            interval = 1.0 / fps

            while time.time() - start_time < duration:
                img = sct.grab(monitor)
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                frames.append(numpy.array(pil_img))
                time.sleep(interval)

            imageio.mimwrite(output_path, frames, fps=fps)

        return {"code": "SUCCESS", "data": {"output_path": output_path, "duration": duration, "fps": fps}, "message": f"录制完成: {output_path}",
                "next_actions": build_next_actions([]),
                "capabilities_used": ["mss", "PIL", "numpy", "imageio"]}
    except Exception as e:
        return {"code": "ERR_SCREEN_RECORD", "data": None, "message": f"录制失败: {str(e)}"}


# ========== 窗口操作 ==========
# 【2026-05-19 小沈】list_windows 已删除（desktop_tools.py 中有权威实现）
# gui_tools.py 只保留 screen_record / ocr / send_notification

def _focus_window(title: str) -> Dict[str, Any]:
    """聚焦指定窗口 - 小沈 2026-05-02"""
    try:
        import win32gui
    except ImportError:
        return {"code": "ERR_NO_WIN32GUI", "data": None, "message": "需要安装 pywin32 库"}
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        if target_hwnd:
            win32gui.SetForegroundWindow(target_hwnd)
            return {"code": "SUCCESS", "data": {"title": title, "hwnd": target_hwnd}, "message": f"窗口已聚焦: {title}", "capabilities_used": ["win32gui"]}
        else:
            return {"code": "ERR_WINDOW_NOT_FOUND", "data": None, "message": f"未找到窗口: {title}"}
    except Exception as e:
        return {"code": "ERR_FOCUS_WINDOW", "data": None, "message": f"聚焦窗口失败: {str(e)}"}


def _resize_window(title: str, width: int = None, height: int = None) -> Dict[str, Any]:
    """调整窗口大小 - 小沈 2026-05-02"""
    try:
        import win32gui
    except ImportError:
        return {"code": "ERR_NO_WIN32GUI", "data": None, "message": "需要安装 pywin32 库"}
    try:
        target_hwnd = None
        def _enum_cb(hwnd, _):
            nonlocal target_hwnd
            if win32gui.IsWindowVisible(hwnd):
                win_title = win32gui.GetWindowText(hwnd)
                if title.lower() in win_title.lower():
                    target_hwnd = hwnd
            return True
        win32gui.EnumWindows(_enum_cb, None)

        if not target_hwnd:
            return {"code": "ERR_WINDOW_NOT_FOUND", "data": None, "message": f"未找到窗口: {title}"}

        left, top, right, bottom = win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top

        new_width = width if width else curr_width
        new_height = height if height else curr_height

        win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True)
        return {"code": "SUCCESS", "data": {"title": title, "width": new_width, "height": new_height}, "message": f"窗口大小调整完成: {new_width}x{new_height}", "capabilities_used": ["win32gui"]}
    except Exception as e:
        return {"code": "ERR_WINDOW_RESIZE", "data": None, "message": f"调整窗口大小失败: {str(e)}"}


# ========== OCR操作 ==========

def ocr(image_path: str, language: str = "eng") -> Dict[str, Any]:
    """从图片中识别文字 - 小沈 2026-05-02"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"code": "ERR_NO_TESSERACT", "data": None, "message": "需要安装 pytesseract 和 PIL 库: pip install pytesseract Pillow",
                "capabilities_missing": ["pytesseract"]}
    try:
        path = Path(image_path)
        if not path.exists():
            return {"code": "ERR_OCR", "data": None, "message": f"图片文件不存在: {image_path}"}

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=language)
        _llm_text = text[:5000]
        if len(text) > 5000:
            _llm_text += f"...(原文{len(text)}字符)"
        return {"code": "SUCCESS", "data": truncate_data_for_frontend({"text": text, "language": language, "char_count": len(text)}), "message": f"OCR识别完成: {len(text)}个字符",
                "llm_data": {"字符数": len(text), "语言": language, "文本预览": _llm_text},
                "next_actions": build_next_actions([("screen_capture", "重新截图", "需要识别其他区域时")]),
                "capabilities_used": ["pytesseract", "PIL"]}
    except Exception as e:
        return {"code": "ERR_OCR", "data": None, "message": f"OCR识别失败: {str(e)}"}


# ========== 剪贴板操作（Tool 105-106）==========

def _read_clipboard() -> Dict[str, Any]:
    """读取剪贴板内容 - 按文档9.6节定义"""
    try:
        import pyperclip
        text = pyperclip.paste()
        # 【优化 小沈 2026-05-15】截断过长内容+llm_data精简
        _llm = {"内容": text[:5000]}
        if len(text) > 5000:
            _llm["截断"] = f"原文{len(text)}字符"
        return {"code": "SUCCESS", "data": truncate_data_for_frontend({"text": text}), "message": "剪贴板读取成功", "llm_data": _llm, "capabilities_used": ["pyperclip"]}
    except ImportError:
        try:
            import ctypes
            CF_TEXT = 1
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            user32.OpenClipboard(None)
            try:
                data = user32.GetClipboardData(CF_TEXT)
                text = ctypes.c_char_p(data).value.decode('gbk') if data else ""
            finally:
                user32.CloseClipboard()
            _llm = {"内容": text[:5000]}
            if len(text) > 5000:
                _llm["截断"] = f"原文{len(text)}字符"
            return {"code": "SUCCESS", "data": {"text": text}, "message": "剪贴板读取成功", "llm_data": _llm, "capabilities_used": ["win32.clipboard"], "capabilities_missing": ["pyperclip"]}
        except Exception as e:
            return {"code": "ERR_DESKTOP_CLIPBOARD", "data": None, "message": f"读取剪贴板失败: {str(e)}"}


def _write_clipboard(content: str) -> Dict[str, Any]:
    """写入内容到剪贴板 - 按文档9.6节定义"""
    try:
        import pyperclip  # 修复：正确库名pyperclip - 小沈 2026-05-04
        pyperclip.copy(content)
        return {"code": "SUCCESS", "data": truncate_data_for_frontend({"content": content}), "message": "剪贴板写入成功", "capabilities_used": ["pyperclip"]}
    except ImportError:
        try:
            import ctypes
            CF_TEXT = 1
            GMEM_MOVEABLE = 0x0002
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            text_bytes = content.encode('gbk') + b'\0'
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
            if h_mem == 0:
                return {"code": "ERR_DESKTOP_CLIPBOARD", "data": None, "message": "内存分配失败"}
            p_mem = kernel32.GlobalLock(h_mem)
            if p_mem:
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                user32.OpenClipboard(None)
                user32.EmptyClipboard()
                user32.SetClipboardData(CF_TEXT, h_mem)
                user32.CloseClipboard()
                return {"code": "SUCCESS", "data": {"content": content}, "message": "剪贴板写入成功", "capabilities_used": ["win32.clipboard"], "capabilities_missing": ["pyperclip"]}
            else:
                kernel32.GlobalFree(h_mem)
                return {"code": "ERR_DESKTOP_CLIPBOARD", "data": None, "message": "内存锁定失败"}
        except Exception as e:
            return {"code": "ERR_DESKTOP_CLIPBOARD", "data": None, "message": f"写入剪贴板失败: {str(e)}"}


# ========== 通知操作（Tool 107）==========

def send_notification(title: str, message: str, duration: int = 5) -> Dict[str, Any]:
    """发送系统通知 - 按文档9.7节定义"""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration)
        return {"code": "SUCCESS", "data": {"title": title, "message": message, "duration": duration}, "message": "通知发送成功",
                "next_actions": build_next_actions([]), "capabilities_used": ["win10toast"]}
    except ImportError:
        return {"code": "ERR_NO_WIN10TOAST", "data": None, "message": "需要安装 win10toast 库: pip install win10toast"}
