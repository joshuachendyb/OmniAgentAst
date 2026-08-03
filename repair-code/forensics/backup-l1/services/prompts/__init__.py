"""Prompts 模块 — PromptBuilder + 系统适配器"""

from .system_prompts import PromptBuilder
from .system_adapter import get_system_prompt

__all__ = [
    "PromptBuilder",
    "get_system_prompt",
]
