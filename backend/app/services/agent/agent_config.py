# -*- coding: utf-8 -*-
"""
Agent 配置注册表 — 声明式定义

Author: 小沈 - 2026-06-07
"""
from dataclasses import dataclass, field
from typing import Type, List, Optional, Any

from app.services.prompts.base_prompt_template import BasePrompts


_DEFAULT_AGENT_MODULE = "app.services.agent.universal_agent"
_DEFAULT_AGENT_CLASS = "UniversalAgent"


@dataclass
class AgentConfig:
    """Agent 配置项"""
    prompt_module: str = "app.services.prompts.system.system_prompts"
    prompt_class_name: str = "SystemPrompts"
    category_display_name: str = "通用助手"
    agent_module: str = _DEFAULT_AGENT_MODULE
    agent_class_name: str = _DEFAULT_AGENT_CLASS
    rollback_enabled: bool = False
    max_steps: int = 100

    _prompt_class: Optional[Type[BasePrompts]] = field(default=None, repr=False)
    _agent_class: Optional[Any] = field(default=None, repr=False)

    @property
    def prompt_class(self) -> Type[BasePrompts]:
        if self._prompt_class is None:
            import importlib
            module = importlib.import_module(self.prompt_module)
            self._prompt_class = getattr(module, self.prompt_class_name)
        return self._prompt_class

    @property
    def agent_class(self) -> Any:
        if self._agent_class is None and self.agent_module:
            import importlib
            module = importlib.import_module(self.agent_module)
            self._agent_class = getattr(module, self.agent_class_name)
        return self._agent_class


DEFAULT_AGENT_CONFIG = AgentConfig()

