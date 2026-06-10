# -*- coding: utf-8 -*-
"""
DesktopPrompts - 桌面操作 Prompt模板

P1优先级:截图/窗口操作参数特殊

Author: 小健 - 2026-05-06
【2026-05-19 小沈】全面重写:10个精简工具(26→10),工具名/参数名与desktop_schema.py对齐
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from datetime import datetime

from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


class DesktopPrompts(BasePrompts):
    """桌面操作 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_prompt_string(include_commands=False)
        tools = [
            "window_info", "window_control", "mouse_control",
            "keyboard_control", "screen_capture", "clipboard_control",
            "screen_record", "ocr", "send_notification",
        ]
        tool_descriptions = self.build_tool_descriptions(tools, category_label="DESKTOP")
        return f"""{system_info}
You are a professional desktop operations assistant. You help users manage windows, control mouse/keyboard, capture screens, use clipboard, and interact with the GUI.

【Available DESKTOP Tools】:
{tool_descriptions}

【Tool Call Examples】:
Example 1: 列出窗口
{{"thought": "用户要查看所有打开的窗口", "reasoning": "使用window_info列出窗口", "tool_name": "window_info", "tool_params": {{"action": "list"}}}}

Example 2: 最大化窗口
{{"thought": "用户要最大化记事本", "reasoning": "使用window_control设置窗口状态", "tool_name": "window_control", "tool_params": {{"window_title": "Notepad", "action": "maximize"}}}}

Example 3: 截图
{{"thought": "用户要截取屏幕", "reasoning": "使用screen_capture", "tool_name": "screen_capture", "tool_params": {{}}}}

Example 4: 任务完成
{{"thought": "桌面操作已完成", "reasoning": "操作成功", "tool_name": "finish", "tool_params": {{"result": "已最大化Notepad窗口"}}}}
"""
    

    def _get_domain_name(self) -> str:
        return "桌面操作"

    def _get_domain_steps(self) -> str:
        return "1. 识别目标窗口或应用\n2. 使用合适的桌面工具\n3. 用中文确认桌面操作结果"

    def get_safety_reminder(self) -> str:
        return "⚠️ Desktop Safety: Only interact with visible windows. Do NOT attempt to access system-level windows."
