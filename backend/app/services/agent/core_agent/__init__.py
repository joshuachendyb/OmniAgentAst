# -*- coding: utf-8 -*-
"""
core_agent 模块 — Agent核心架构

- base_agent.py: Agent类骨架
- react_loop.py: ReAct循环核心算法
- agent_initializer.py: Agent初始化逻辑
- tool_manager.py: 工具加载和管理
- step_emitter.py: 步骤发射和Task追踪
- initialize_run_state.py: 运行状态初始化

Author: 小沈 - 2026-06-08
"""
from .base_agent import BaseAgent
from .react_cycle import run_stream

__all__ = ["BaseAgent", "run_stream"]
