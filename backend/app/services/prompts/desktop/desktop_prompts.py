# -*- coding: utf-8 -*-
"""
DesktopPrompts - 桌面操作 Prompt模板

P1优先级:截图/窗口操作参数特殊

Author: 小健 - 2026-05-06
【2026-05-19 小沈】全面重写:10个精简工具(26→10),工具名/参数名与desktop_schema.py对齐
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from app.services.prompts.base_prompt_template import BasePrompts


class DesktopPrompts(BasePrompts):
    """桌面操作 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "你是一个桌面操作助手,负责窗口管理、鼠标/键盘控制、屏幕截图、剪贴板和GUI交互。"

    def get_tool_details(self) -> str:
        """获取工具描述和示例(FC模式下可选跳过) - 小沈 2026-06-11"""
        tools = [
            "window_info", "window_control", "mouse_control",
            "keyboard_control", "screen_capture", "clipboard_control",
            "screen_record", "ocr", "send_notification",
        ]
        tool_descriptions = self.build_tool_descriptions(tools, category_label="DESKTOP")
        return f"""【Available DESKTOP Tools】:
{tool_descriptions}

【调用决策示例】:
用户: "查看所有打开的窗口"
→ 判断: 窗口列表 → 调用window_info(action="list")

用户: "最大化记事本"
→ 判断: 窗口控制 → 调用window_control(window_title="Notepad", action="maximize")

用户: "截取屏幕"
→ 判断: 屏幕截图 → 调用screen_capture()"""
    

    def _get_domain_name(self) -> str:
        return "桌面操作"

    def _get_domain_steps(self) -> str:
        return "1. 识别目标窗口或应用\n2. 使用合适的桌面工具\n3. 用中文确认桌面操作结果"

