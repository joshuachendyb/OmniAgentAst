"""
策略选择器 — 只有text和tools两种

逻辑：模型支持FC → tools，否则 → text
"""

from dataclasses import dataclass
from app.services.agent._deprecated_capability import LLMCapability, LLMFeature


@dataclass
class SelectedStrategy:
    method: str  # "tools" or "text"
    capability: LLMCapability
    description: str


class StrategySelector:
    @staticmethod
    def select(feature: LLMFeature) -> SelectedStrategy:
        if feature.supports_tools:
            return SelectedStrategy(method="tools", capability=LLMCapability.TOOLS, description="Function Calling")
        return StrategySelector.fallback("模型不支持FC，使用text模式")

    @staticmethod
    def fallback(reason: str) -> SelectedStrategy:
        return SelectedStrategy(method="text", capability=LLMCapability.NONE, description=f"降级text: {reason}")


__all__ = ["StrategySelector", "SelectedStrategy"]
