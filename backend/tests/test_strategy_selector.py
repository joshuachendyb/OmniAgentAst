"""
StrategySelector 测试 - 小沈

测试LLM策略选择器的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest

from app.services.agent.strategy_selector import StrategySelector, SelectedStrategy
from app.services.agent.capability import LLMFeature, LLMCapability


class TestStrategySelector:
    """测试StrategySelector策略选择"""
    
    def test_select_tools_when_supported(self):
        """测试支持tools时选择tools策略"""
        feature = LLMFeature(
            supports_tools=True,
            supports_response_format=False
        )
        
        strategy = StrategySelector.select(feature)
        
        assert strategy.method == "tools"
        assert strategy.capability == LLMCapability.TOOLS
        assert "tools" in strategy.description.lower()
    
    def test_select_response_format_when_tools_not_supported(self):
        """测试不支持tools但支持response_format时选择response_format策略"""
        feature = LLMFeature(
            supports_tools=False,
            supports_response_format=True
        )
        
        strategy = StrategySelector.select(feature)
        
        assert strategy.method == "response_format"
        assert strategy.capability == LLMCapability.RESPONSE_FORMAT
        assert "response_format" in strategy.description.lower()
    
    def test_select_prompt_when_none_supported(self):
        """测试都不支持时选择prompt策略"""
        feature = LLMFeature(
            supports_tools=False,
            supports_response_format=False
        )
        
        strategy = StrategySelector.select(feature)
        
        assert strategy.method == "prompt"
        assert strategy.capability == LLMCapability.NONE
        assert "prompt" in strategy.description.lower()
    
    def test_select_tools_priority_over_response_format(self):
        """测试tools优先级高于response_format"""
        feature = LLMFeature(
            supports_tools=True,
            supports_response_format=True
        )
        
        strategy = StrategySelector.select(feature)
        
        # 应该选择tools而不是response_format
        assert strategy.method == "tools"
        assert strategy.capability == LLMCapability.TOOLS


class TestSelectedStrategy:
    """测试SelectedStrategy数据类"""
    
    def test_strategy_creation(self):
        """测试策略创建"""
        strategy = SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="使用 tools/function_calling"
        )
        
        assert strategy.method == "tools"
        assert strategy.capability == LLMCapability.TOOLS
        assert strategy.description == "使用 tools/function_calling"
    
    def test_strategy_equality(self):
        """测试策略相等性"""
        strategy1 = SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="使用 tools/function_calling"
        )
        
        strategy2 = SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="使用 tools/function_calling"
        )
        
        assert strategy1 == strategy2
    
    def test_strategy_inequality(self):
        """测试策略不相等"""
        strategy1 = SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="使用 tools/function_calling"
        )
        
        strategy2 = SelectedStrategy(
            method="response_format",
            capability=LLMCapability.RESPONSE_FORMAT,
            description="使用 response_format"
        )
        
        assert strategy1 != strategy2
