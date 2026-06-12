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

