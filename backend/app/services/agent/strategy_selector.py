"""
LLM 策略选择器实现

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.3节

功能：
1. StrategySelector 类 - 根据 LLM 能力自动选择最佳策略
2. SelectedStrategy 数据类 - 选中的策略
"""

from dataclasses import dataclass

from app.services.agent.capability import LLMCapability, LLMFeature


class StrategySelector:
    """
    策略选择器
    
    根据 LLM 能力自动选择最佳策略
    """
    
    @staticmethod
    def select(feature: LLMFeature) -> "SelectedStrategy":
        """
        根据能力选择最佳策略
        
        策略优先级：tools > response_format > text
        - tools: Function Calling，LLM通过API调用工具（约50个模型支持）
        - response_format: 结构化输出，LLM返回JSON格式（约45个模型支持）
        - text: 纯文本模式，工具Schema注入Prompt（所有模型支持）
        
        【注意】reasoning是附加能力，不影响策略选择
        - reasoning=True表示模型有思考链（如DeepSeek的reasoning_content）
        - 可以与任何策略组合使用
        
        Args:
            feature: LLM 能力特征
        
        Returns:
            SelectedStrategy: 选中的策略
        """
        if feature.supports_tools:
            return SelectedStrategy(
                method="tools",
                capability=LLMCapability.TOOLS,
                description="Function Calling（约50个模型支持）"
            )
        
        if feature.supports_response_format:
            return SelectedStrategy(
                method="response_format",
                capability=LLMCapability.RESPONSE_FORMAT,
                description="结构化输出（约45个模型支持）"
            )
        
        return SelectedStrategy(
            method="text",
            capability=LLMCapability.NONE,
            description="纯文本模式（所有模型支持）"
        )


@dataclass
class SelectedStrategy:
    """
    选中的策略
    """
    method: str  # "response_format", "tools", "text"
    capability: LLMCapability
    description: str


# 导出
__all__ = ["StrategySelector", "SelectedStrategy"]
