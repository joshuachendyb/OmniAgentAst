"""
CapabilityDetector 测试 - 小沈

测试LLM能力探测器的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.agent.capability_detector import CapabilityDetector
from app.services.agent.capability import LLMFeature, LLMProbeResult, LLMCapability


class TestCapabilityDetectorInitialization:
    """测试CapabilityDetector初始化"""
    
    def test_detector_initialization(self):
        """测试探测器初始化"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        assert detector.api_base == "http://test.com"
        assert detector.api_key == "test_key"
        assert detector.model == "test_model"
        assert detector._capability_cache is None
    
    def test_detector_has_capability_property(self):
        """测试探测器有capability属性"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        assert detector.capability is None
    
    def test_detector_is_cached_false(self):
        """测试未缓存时is_cached返回False"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        assert detector.is_cached() == False


class TestCapabilityDetectorCaching:
    """测试CapabilityDetector缓存功能"""
    
    @pytest.mark.asyncio
    async def test_detector_caches_result(self):
        """测试探测器缓存结果"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        # 模拟探测成功
        with patch.object(detector, '_probe_tools', return_value={"works": True}):
            with patch.object(detector, '_probe_response_format', return_value={"works": True}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}):
                    result = await detector.detect()
        
        assert result.success == True
        assert detector.is_cached() == True
        assert detector.capability is not None
    
    @pytest.mark.asyncio
    async def test_detector_uses_cached_result(self):
        """测试探测器使用缓存结果"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        # 设置缓存
        cached_feature = LLMFeature(
            capability=LLMCapability.TOOLS,
            supports_tools=True,
            supports_response_format=False,
            detection_method="auto"
        )
        detector._capability_cache = cached_feature
        
        # 再次调用detect应该返回缓存结果
        result = await detector.detect()
        
        assert result.success == True
        assert result.feature == cached_feature


class TestCapabilityDetectorDetect:
    """测试CapabilityDetector探测功能"""
    
    @pytest.mark.asyncio
    async def test_detect_tools_only(self):
        """测试只支持tools的探测"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        with patch.object(detector, '_probe_tools', return_value={"works": True}):
            with patch.object(detector, '_probe_response_format', return_value={"works": False}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}):
                    result = await detector.detect()
        
        assert result.success == True
        assert result.tools_works == True
        assert result.response_format_works == False
        assert result.feature.supports_tools == True
        assert result.feature.supports_response_format == False
    
    @pytest.mark.asyncio
    async def test_detect_response_format_only(self):
        """测试只支持response_format的探测"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        with patch.object(detector, '_probe_tools', return_value={"works": False}):
            with patch.object(detector, '_probe_response_format', return_value={"works": True}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}):
                    result = await detector.detect()
        
        assert result.success == True
        assert result.tools_works == False
        assert result.response_format_works == True
        assert result.feature.supports_tools == False
        assert result.feature.supports_response_format == True
    
    @pytest.mark.asyncio
    async def test_detect_both_supported(self):
        """测试同时支持tools和response_format"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        with patch.object(detector, '_probe_tools', return_value={"works": True}):
            with patch.object(detector, '_probe_response_format', return_value={"works": True}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}):
                    result = await detector.detect()
        
        assert result.success == True
        assert result.tools_works == True
        assert result.response_format_works == True
        assert result.feature.supports_tools == True
        assert result.feature.supports_response_format == True
    
    @pytest.mark.asyncio
    async def test_detect_none_supported(self):
        """测试都不支持的探测"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        with patch.object(detector, '_probe_tools', return_value={"works": False}):
            with patch.object(detector, '_probe_response_format', return_value={"works": False}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}):
                    result = await detector.detect()
        
        assert result.success == True
        assert result.tools_works == False
        assert result.response_format_works == False
        assert result.feature.supports_tools == False
        assert result.feature.supports_response_format == False
    
    @pytest.mark.asyncio
    async def test_detect_with_reasoning(self):
        """测试带reasoning特征的探测"""
        detector = CapabilityDetector(
            api_base="http://test.com",
            api_key="test_key",
            model="test_model"
        )
        
        with patch.object(detector, '_probe_tools', return_value={"works": True}):
            with patch.object(detector, '_probe_response_format', return_value={"works": True}):
                with patch.object(detector, '_probe_reasoning', return_value={"has_reasoning": True, "uses_reasoning_content": True, "uses_outer_content": True}):
                    result = await detector.detect()
        
        assert result.success == True
        assert result.feature.supports_reasoning == True
        assert result.feature.uses_reasoning_content == True
        assert result.feature.uses_outer_content == True
