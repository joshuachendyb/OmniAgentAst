"""
LLM 策略选择器实现

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.3节

功能：
1. StrategySelector 类 - 根据 LLM 能力自动选择最佳策略
2. SelectedStrategy 数据类 - 选中的策略
"""

from dataclasses import dataclass

from app.services.file_operations.capability import LLMCapability, LLMFeature


class StrategySelector:
    """
    策略选择器
    
    根据 LLM 能力自动选择最佳策略
    """
    
    @staticmethod
    def select(feature: LLMFeature) -> "SelectedStrategy":
        """
        根据能力选择最佳策略
        
        Args:
            feature: LLM 能力特征
        
        Returns:
            SelectedStrategy: 选中的策略
        """
        # ✅ 优先级修正：tools > response_format > prompt
        # 原因：根据实测，tools 模式支持约50个模型，response_format 约45个
        
        if feature.supports_tools:
            return SelectedStrategy(
                method="tools",
                capability=LLMCapability.TOOLS,
                description="使用 tools/function_calling（支持最广，约50个模型）"
            )
        
        if feature.supports_response_format:
            return SelectedStrategy(
                method="response_format",
                capability=LLMCapability.RESPONSE_FORMAT,
                description="使用 response_format（约45个模型）"
            )
        
        return SelectedStrategy(
            method="prompt",
            capability=LLMCapability.NONE,
            description="降级到 Prompt 方式（所有模型都支持）"
        )


@dataclass
class SelectedStrategy:
    """
    选中的策略
    """
    method: str  # "response_format", "tools", "prompt"
    capability: LLMCapability
    description: str


# 导出
__all__ = ["StrategySelector", "SelectedStrategy"]
