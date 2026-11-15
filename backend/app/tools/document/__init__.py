# -*- coding: utf-8 -*-
"""Document 模块 — 小健 2026-06-22"""
# 2026-11-15 小欧 - 星号导入改显式导入: 星号导入下注册入口名来源不可静态判定, 显式导入后来源唯一, 工具注册行为不变

from app.tools.document.document_register import _register_document_tools

__all__ = ["_register_document_tools"]
