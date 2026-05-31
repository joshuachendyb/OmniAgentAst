# -*- coding: utf-8 -*-
"""
base_react 模块 — 从 base_react.py 拆出的职责

- agent_initializer: Agent初始化逻辑
- tool_manager: 工具加载和管理
- step_emitter: 步骤发射和Task追踪
- _core: BaseAgent 核心类
"""

from app.services.agent.base_react.base_react import BaseAgent
from app.services.agent.types import AgentStatus

__all__ = ["BaseAgent", "AgentStatus"]
