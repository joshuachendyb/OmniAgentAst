# -*- coding: utf-8 -*-
"""
GUI操作工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第9章 Tool 92-104 定义

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

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.gui.gui_schema import (
    ClickInput,
    MoveInput,
    ScrollInput,
    TypeTextInput,
    ShortcutInput,
    KeyComboInput,
    ScreenshotInput,
    SnapshotInput,
    ScreenRecordInput,
    FocusWindowInput,
    ResizeWindowInput,
    OcrInput,
    ListWindowsInput,
)


def _check_pyautogui() -> bool:
    try:
        importlib.import_module("pyautogui")
        return True
    except ImportError:
        return False


# ========== 鼠标操作 ==========

@register_tool(
    name="click",
    description="""模拟鼠标点击操作。

使用场景：
- 当用户需要模拟鼠标点击按钮或链接时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要点击特定位置时使用

参数说明：
- x：点击的 X 坐标
- y：点击的 Y 坐标
- button：鼠标按钮（可选），可填 left/right/middle
- click_type：点击类型（可选），可填 single/double

【重要】需要安装 pyautogui 库（pip install pyautogui）""",
    category=ToolCategory.GUI,
    input_model=ClickInput,
    examples=[{"x": 500, "y": 300}, {"x": 500, "y": 300, "click_type": "double"}]
)
def click(
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
        return {"code": "SUCCESS", "data": {"x": x, "y": y, "button": button, "click_type": click_type}, "message": f"点击完成: ({x}, {y}) {button} {click_type}"}
    except Exception as e:
        return {"code": "ERR_CLICK", "data": None, "message": f"点击失败: {str(e)}"}


@register_tool(
    name="move",
    description="""移动鼠标到指定位置。

使用场景：
- 当用户需要移动鼠标到特定位置时使用
- 当用户需要进行桌面自动化操作时使用
- 当用户需要将鼠标悬停在特定元素上时使用

【重要】需要安装 pyautogui 库""",
    category=ToolCategory.GUI,
    input_model=MoveInput,
    examples=[{"x": 500, "y": 300}, {"x": 500, "y": 300, "duration": 1.5}]
)
def move(x: int, y: int, duration: float = 0) -> Dict[str, Any]:
    """移动鼠标到指定位置 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        pyautogui.moveTo(x, y, duration=duration)
        return {"code": "SUCCESS", "data": {"x": x, "y": y}, "message": f"鼠标移动到: ({x}, {y})"}
    except Exception as e:
        return {"code": "ERR_MOVE", "data": None, "message": f"移动失败: {str(e)}"}


@register_tool(
    name="scroll",
    description="""模拟鼠标滚轮滚动。

使用场景：
- 当用户需要滚动页面或文档时使用
- 当用户需要向下滚动查看更多内容时使用

参数说明：
- direction：滚动方向，可选 up/down
- amount：滚动单位数量（可选）

【重要】需要安装 pyautogui 库""",
    category=ToolCategory.GUI,
    input_model=ScrollInput,
    examples=[{"direction": "down"}, {"direction": "up", "amount": 10}]
)
def scroll(direction: str, amount: int = 3) -> Dict[str, Any]:
    """模拟鼠标滚轮滚动 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        scroll_amount = amount if direction == "down" else -amount
        pyautogui.scroll(scroll_amount)
        return {"code": "SUCCESS", "data": {"direction": direction, "amount": amount}, "message": f"滚动完成: {direction} {amount}单位"}
    except Exception as e:
        return {"code": "ERR_SCROLL", "data": None, "message": f"滚动失败: {str(e)}"}


# ========== 键盘操作 ==========

@register_tool(
    name="type_text",
    description="""模拟键盘输入文本。

使用场景：
- 当用户需要在输入框中输入文本时使用
- 当用户需要进行表单填写自动化时使用

参数说明：
- text：要输入的文本
- interval：每个字符间隔（秒）（可选）

【重要】需要安装 pyautogui 库""",
    category=ToolCategory.GUI,
    input_model=TypeTextInput,
    examples=[{"text": "Hello World"}, {"text": "Hello", "interval": 0.1}]
)
def type_text(text: str, interval: float = 0) -> Dict[str, Any]:
    """模拟键盘输入文本 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=interval) if text.isascii() else pyautogui.write(text)
        return {"code": "SUCCESS", "data": {"text_length": len(text)}, "message": f"输入文本完成: {len(text)}个字符"}
    except Exception as e:
        return {"code": "ERR_TYPE_TEXT", "data": None, "message": f"输入文本失败: {str(e)}"}


@register_tool(
    name="shortcut",
    description="""执行键盘快捷键组合。

使用场景：
- 当用户需要执行快捷键操作时使用
- 当用户需要进行复制粘贴、保存等快捷操作时使用

参数说明：
- keys：快捷键组合（如 "ctrl+c", "alt+tab"）

【重要】需要安装 pyautogui 库""",
    category=ToolCategory.GUI,
    input_model=ShortcutInput,
    examples=[{"keys": "ctrl+c"}, {"keys": "alt+tab"}]
)
def shortcut(keys: str) -> Dict[str, Any]:
    """执行键盘快捷键组合 - 小沈 2026-05-02"""
    if not _check_pyautogui():
        return {"code": "ERR_NO_PYAUTOGUI", "data": None, "message": "pyautogui库未安装"}
    try:
        import pyautogui
        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return {"code": "SUCCESS", "data": {"keys": keys}, "message": f"快捷键执行完成: {keys}"}
    except Exception as e:
        return {"code": "ERR_SHORTCUT", "data": None, "message": f"快捷键执行失败: {str(e)}"}


@register_tool(
    name="key_combo",
    description="""按住多个键后释放。

使用场景：
- 当用户需要按住多个键执行组合操作时使用
- 当用户需要精确控制按键按下和释放顺序时使用

参数说明：
- keys：要按住的键数组
- action：操作，可选 press/hold/release

【重要】需要安装 pyautogui 库""",
    category=ToolCategory.GUI,
    input_model=KeyComboInput,
    examples=[{"keys": ["ctrl", "c"], "action": "press"}, {"keys": ["ctrl", "shift"], "action": "hold"}]
)
def key_combo(keys: List[str], action: str = "press") -> Dict[str, Any]:
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
        return {"code": "SUCCESS", "data": {"keys": keys, "action": action}, "message": f"按键操作完成: {keys} {action}"}
    except Exception as e:
        return {"code": "ERR_KEY_COMBO", "data": None, "message": f"按键操作失败: {str(e)}"}


# ========== 屏幕操作 ==========

@register_tool(
    name="screenshot",
    description="""截取屏幕截图。

使用场景：
- 当用户需要截取当前屏幕画面时使用
- 当用户需要保存屏幕截图作为记录时使用

参数说明：
- output_path：输出文件路径（可选）
- region：截取区域 {x, y, width, height}

【重要】需要安装 pyautogui 或 PIL 库""",
    category=ToolCategory.GUI,
    input_model=ScreenshotInput,
    examples=[{}, {"output_path": "D:/output/region.png", "region": {"x": 0, "y": 0, "width": 800, "height": 600}}]
)
def screenshot(output_path: str = None, region: Dict[str, int] = None) -> Dict[str, Any]:
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
        return {"code": "SUCCESS", "data": output_path, "message": f"截图保存到: {output_path}"}
    except Exception as e:
        return {"code": "ERR_SCREENSHOT", "data": None, "message": f"截图失败: {str(e)}"}


@register_tool(
    name="snapshot",
    description="""获取完整桌面状态快照。

使用场景：
- 当用户需要获取当前桌面完整状态时使用
- 当用户需要进行桌面状态分析时使用

参数说明：
- display：显示器编号（可选）

【重要】需要安装 mss 或 PIL 库""",
    category=ToolCategory.GUI,
    input_model=SnapshotInput,
    examples=[{}, {"display": 2}]
)
def snapshot(display: int = 1) -> Dict[str, Any]:
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
            return {"code": "SUCCESS", "data": {"image_path": output_path, "display": display}, "message": f"快照保存到: {output_path}"}
        except ImportError:
            return {"code": "ERR_NO_SCREENSHOT_LIB", "data": None, "message": "需要安装 mss 或 pyautogui 库"}
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(tempfile.gettempdir(), f"snapshot_{timestamp}.png")
        with mss.mss() as sct:
            monitors = sct.monitors
            mon_index = min(display, len(monitors) - 1) if display < len(monitors) else 1
            img = sct.grab(monitors[mon_index])
            from PIL import Image
            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
            pil_img.save(output_path)
        return {"code": "SUCCESS", "data": {"image_path": output_path, "display": display, "monitors": len(monitors) - 1}, "message": f"快照保存到: {output_path}"}
    except Exception as e:
        return {"code": "ERR_SNAPSHOT", "data": None, "message": f"快照失败: {str(e)}"}


@register_tool(
    name="screen_record",
    description="""录制屏幕视频。

使用场景：
- 当用户需要录制屏幕操作过程时使用
- 当用户需要制作操作教程或演示视频时使用

参数说明：
- duration：录制时长（秒）
- output_path：输出文件路径（可选）
- fps：帧率（可选）

【重要】需要安装屏幕录制库（mss + PIL）""",
    category=ToolCategory.GUI,
    input_model=ScreenRecordInput,
    examples=[{"duration": 30}, {"duration": 60, "output_path": "D:/output/demo.mp4", "fps": 30}]
)
def screen_record(duration: int, output_path: str = None, fps: int = 15) -> Dict[str, Any]:
    """录制屏幕视频 - 小沈 2026-05-02"""
    try:
        import mss
        from PIL import Image
    except ImportError:
        return {"code": "ERR_NO_RECORD_LIB", "data": None, "message": "需要安装 mss 和 PIL 库"}
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

            try:
                import numpy
            except ImportError:
                return {"code": "ERR_NO_NUMPY", "data": None, "message": "需要安装 numpy 库"}

            imageio.mimwrite(output_path, frames, fps=fps)

        return {"code": "SUCCESS", "data": {"output_path": output_path, "duration": duration, "fps": fps}, "message": f"录制完成: {output_path}"}
    except Exception as e:
        return {"code": "ERR_SCREEN_RECORD", "data": None, "message": f"录制失败: {str(e)}"}


# ========== 窗口操作 ==========

@register_tool(
    name="list_windows",
    description="""获取所有打开的窗口列表。

使用场景：
- 当用户需要查看当前打开的所有窗口时使用
- 当用户需要查找特定窗口时使用

参数说明：
- filter：窗口标题过滤

【重要】需要安装 pywin32 库（Windows）""",
    category=ToolCategory.GUI,
    input_model=ListWindowsInput,
    examples=[{}, {"filter": "Chrome"}]
)
def list_windows(filter: str = None) -> Dict[str, Any]:
    """获取所有打开的窗口列表 - 小沈 2026-05-02"""
    try:
        import win32gui
    except ImportError:
        return {"code": "ERR_NO_WIN32GUI", "data": None, "message": "需要安装 pywin32 库: pip install pywin32"}
    try:
        windows = []
        def _enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    if filter is None or filter.lower() in title.lower():
                        windows.append({"hwnd": hwnd, "title": title})
        win32gui.EnumWindows(_enum_cb, None)
        return {"code": "SUCCESS", "data": {"windows": windows, "count": len(windows)}, "message": f"找到 {len(windows)} 个窗口"}
    except Exception as e:
        return {"code": "ERR_LIST_WINDOWS", "data": None, "message": f"获取窗口列表失败: {str(e)}"}


@register_tool(
    name="focus_window",
    description="""聚焦指定窗口。

使用场景：
- 当用户需要将特定窗口置为前台时使用
- 当用户需要激活某个窗口进行操作时使用

参数说明：
- title：窗口标题

【重要】需要安装 pywin32 库""",
    category=ToolCategory.GUI,
    input_model=FocusWindowInput,
    examples=[{"title": "Chrome"}]
)
def focus_window(title: str) -> Dict[str, Any]:
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
        win32gui.EnumWindows(_enum_cb, None)

        if target_hwnd:
            win32gui.SetForegroundWindow(target_hwnd)
            return {"code": "SUCCESS", "data": {"title": title, "hwnd": target_hwnd}, "message": f"窗口已聚焦: {title}"}
        else:
            return {"code": "ERR_WINDOW_NOT_FOUND", "data": None, "message": f"未找到窗口: {title}"}
    except Exception as e:
        return {"code": "ERR_FOCUS_WINDOW", "data": None, "message": f"聚焦窗口失败: {str(e)}"}


@register_tool(
    name="resize_window",
    description="""调整窗口大小。

使用场景：
- 当用户需要调整窗口大小时使用
- 当用户需要将窗口设置为特定尺寸时使用

参数说明：
- title：窗口标题
- width：宽度
- height：高度

【重要】需要安装 pywin32 库""",
    category=ToolCategory.GUI,
    input_model=ResizeWindowInput,
    examples=[{"title": "Chrome", "width": 1920, "height": 1080}]
)
def resize_window(title: str, width: int = None, height: int = None) -> Dict[str, Any]:
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
        win32gui.EnumWindows(_enum_cb, None)

        if not target_hwnd:
            return {"code": "ERR_WINDOW_NOT_FOUND", "data": None, "message": f"未找到窗口: {title}"}

        left, top, right, bottom = win32gui.GetWindowRect(target_hwnd)
        curr_width = right - left
        curr_height = bottom - top

        new_width = width if width else curr_width
        new_height = height if height else curr_height

        win32gui.MoveWindow(target_hwnd, left, top, new_width, new_height, True)
        return {"code": "SUCCESS", "data": {"title": title, "width": new_width, "height": new_height}, "message": f"窗口大小调整完成: {new_width}x{new_height}"}
    except Exception as e:
        return {"code": "ERR_RESIZE_WINDOW", "data": None, "message": f"调整窗口大小失败: {str(e)}"}


# ========== OCR操作 ==========

@register_tool(
    name="ocr",
    description="""从图片中识别文字。

使用场景：
- 当用户需要从图片中提取文字内容时使用
- 当用户需要进行图片文字识别（OCR）时使用

参数说明：
- image_path：图片文件路径
- language：识别语言，可选 eng/chi_sim/eng+chi_sim

【重要】需要安装 pytesseract 库和 Tesseract OCR 引擎""",
    category=ToolCategory.GUI,
    input_model=OcrInput,
    examples=[{"image_path": "D:/images/screenshot.png"}, {"image_path": "D:/images/screenshot.png", "language": "chi_sim"}]
)
def ocr(image_path: str, language: str = "eng") -> Dict[str, Any]:
    """从图片中识别文字 - 小沈 2026-05-02"""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"code": "ERR_NO_TESSERACT", "data": None, "message": "需要安装 pytesseract 和 PIL 库: pip install pytesseract Pillow"}
    try:
        path = Path(image_path)
        if not path.exists():
            return {"code": "ERR_OCR", "data": None, "message": f"图片文件不存在: {image_path}"}

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang=language)
        return {"code": "SUCCESS", "data": {"text": text, "language": language, "char_count": len(text)}, "message": f"OCR识别完成: {len(text)}个字符"}
    except Exception as e:
        return {"code": "ERR_OCR", "data": None, "message": f"OCR识别失败: {str(e)}"}
