"""Prompts 模块 - Prompt 模板"""

from .base_prompt_template import BasePrompts
from .system_prompts import SystemPrompts
from .system_adapter import get_system_prompt

__all__ = [
    "BasePrompts",
    "SystemPrompts",
    "get_system_prompt",
]
