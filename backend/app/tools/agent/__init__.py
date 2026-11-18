# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新建智能体交互工具包(question/schedule); 阶段B接入注册入口导出
"""
agent — 智能体交互工具包(question 阻塞问答 / schedule 计划清单)

注册入口: agent_register._register_agent_tools, 由 CATEGORY_MODULES["agent"] 在启动时调用。
"""
from app.tools.agent.agent_register import _register_agent_tools

__all__ = ["_register_agent_tools"]
