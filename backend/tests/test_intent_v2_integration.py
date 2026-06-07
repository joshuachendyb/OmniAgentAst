"""
ChatRouter 阶段2集成测试：detect_intent_v2 接入 + LLM兜底

TDD: RED阶段 - 测试新功能尚未实现而失败
Author: 小沈 - 2026-04-30
"""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.tools.registry import ToolCategory
from app.api.v1.chat import detect_intent_v2


class TestIntentV2RouterIntegration:
    """测试detect_intent_v2接入路由层"""

    def test_v2_output_can_drive_agent_selection(self):
        """detect_intent_v2 的返回值可以驱动Agent选择"""
        result, candidates, conf = detect_intent_v2('帮我删除这个文件')
        assert result is not None
        intent_str = result.value
        assert intent_str in ["file", "system", "network", "desktop", "document"]

    def test_v2_returns_shell_for_dangerous_commands(self):
        """危险命令→SHELL(合并到SYSTEM)→可以用react_sse_wrapper处理"""
        result, candidates, conf = detect_intent_v2('rm -rf /')
        assert result == ToolCategory.SYSTEM
        assert conf >= 0.3

    def test_v2_returns_none_for_chat(self):
        """聊天内容返回None，需要LLM兜底"""
        result, candidates, conf = detect_intent_v2('你好，今天天气怎么样')
        assert result is None
        assert conf == 0.0

    def test_v2_returns_time_for_time_query(self):
        """时间查询→TIME(合并到SYSTEM)→走动作意图"""
        result, candidates, conf = detect_intent_v2('现在几点了')
        assert result == ToolCategory.SYSTEM
        assert conf >= 0.3

    def test_v2_confidence_for_single_match(self):
        """单一匹配返回置信度（加权计算）"""
        result, candidates, conf = detect_intent_v2('ping 192.168.1.1')
        assert result == ToolCategory.NETWORK
        assert conf > 0  # 加权评分: 1个英文命中=1, 归一化=0.5

    def test_v2_confidence_for_multiple_matches(self):
        """多匹配返回各意图置信度分布"""
        result, candidates, conf = detect_intent_v2('下载文件并查看时间')
        assert conf > 0
        assert len(candidates) >= 2

    def test_v2_candidates_contain_all_matches(self):
        """candidates列表包含所有匹配的分类"""
        result, candidates, conf = detect_intent_v2(
            '下载文件查看CPU使用率'
        )
        # 应该匹配到NETWORK(下载)和SYSTEM(CPU)
        matched_values = [c.value for c in candidates]
        assert 'network' in matched_values or 'file' in matched_values
        assert 'system' in matched_values

    def test_llm_fallback_needed_when_v2_returns_none(self):
        """CRSS无匹配时，需要LLM兜底"""
        result, candidates, conf = detect_intent_v2('帮我看看这个有趣的事情')
        assert result is None
        # 验证需要进入LLM兜底阶段
        needs_llm_fallback = (result is None)
        assert needs_llm_fallback


# TestLLMFallbackPhase 已删除 —— Mock掩盖真实LLM调用，无保留价值
# TODO: 用 respx/httpx_mock 新增真实集成测试，拦截httpx调用验证完整路径
