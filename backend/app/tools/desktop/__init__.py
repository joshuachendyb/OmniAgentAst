# -*- coding: utf-8 -*-
"""DESKTOP Tools - 桌面工具模块 — 小健 2026-06-22 拆分为16个独立文件"""
# 2026-11-15 小欧 - 星号导入改显式导入: 星号导入下注册入口名来源不可静态判定, 显式导入后来源唯一, 工具注册行为不变

from app.tools.desktop.desktop_register import _register_desktop_tools

__all__ = ["_register_desktop_tools"]
