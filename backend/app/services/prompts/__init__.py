"""Prompts 模块 — PromptBuilder + 系统适配器"""

from .system_adapter import get_system_prompt
from .system_prompts import PromptBuilder

__all__ = [
    "PromptBuilder",
    "get_system_prompt",
]
