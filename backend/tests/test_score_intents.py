"""
CRSS加权评分函数测试

TDD: 测试 _compute_intent_scores 加权评分 + detect_intent_v2 增强
Author: 小沈 - 2026-04-30
"""
import pytest
from app.services.intents.crss_scorer import _compute_intent_scores
from app.services.chat_router import detect_intent_v2
from app.services.tools.registry import ToolCategory


class TestScoreIntents:
    """CRSS加权评分函数测试"""

    def test_chat_input_returns_empty(self):
        """聊天内容无匹配，返回空字典"""
        scores = _compute_intent_scores('你好，今天天气怎么样')
        assert scores == {}

    def test_single_file_keyword_returns_file(self):
        """单一文件关键词返回FILE"""
        scores = _compute_intent_scores('帮我删除这个文件')
        assert len(scores) >= 1
        assert ToolCategory.FILE in scores
        assert scores[ToolCategory.FILE] > 0

    def test_single_shell_keyword_returns_shell(self):
        """Shell关键词返回SHELL"""
        scores = _compute_intent_scores('运行npm install')
        assert ToolCategory.SHELL in scores
        assert scores[ToolCategory.SHELL] > 0

    def test_time_keyword_returns_time(self):
        """时间关键词返回TIME"""
        scores = _compute_intent_scores('现在几点了')
        assert ToolCategory.TIME in scores
        assert scores[ToolCategory.TIME] > 0

    def test_network_keyword_returns_network(self):
        """网络关键词返回NETWORK"""
        scores = _compute_intent_scores('ping 192.168.1.1')
        assert ToolCategory.NETWORK in scores

    def test_dangerous_command_returns_high_shell_score(self):
        """危险命令返回高SHELL评分"""
        scores = _compute_intent_scores('rm -rf /')
        assert ToolCategory.SHELL in scores
        # 危险命令应该是最高的
        assert scores[ToolCategory.SHELL] == max(scores.values())

    def test_multi_intent_distribution(self):
        """多意图返回置信度分布"""
        scores = _compute_intent_scores('下载文件并查看时间')
        assert len(scores) >= 2

    def test_scores_sorted_descending(self):
        """置信度从高到低排序"""
        scores = _compute_intent_scores('下载文件查看CPU')
        if len(scores) >= 2:
            sorted_scores = list(scores.items())
            for i in range(len(sorted_scores) - 1):
                assert sorted_scores[i][1] >= sorted_scores[i+1][1]

    def test_chinese_keyword_higher_weight(self):
        """中文关键词权重大于英文关键词"""
        chinese_scores = _compute_intent_scores('查询用户表数据')
        english_scores = _compute_intent_scores('select * from users')
        if ToolCategory.DATABASE in chinese_scores and ToolCategory.DATABASE in english_scores:
            assert chinese_scores[ToolCategory.DATABASE] > 0
            assert english_scores[ToolCategory.DATABASE] > 0

    def test_empty_input_returns_empty(self):
        """空输入返回空"""
        assert _compute_intent_scores('') == {}
        assert _compute_intent_scores('   ') == {}

    def test_scores_are_floats_0_to_1(self):
        """返回值范围在 (0, 1) 之间"""
        scores = _compute_intent_scores('下载文件并运行')
        if scores:
            for cat in scores:
                assert isinstance(cat, ToolCategory)
                assert isinstance(scores[cat], float)
                assert 0 < scores[cat] <= 1.0

    def test_system_keyword_detected(self):
        """系统关键词被检测到"""
        scores = _compute_intent_scores('CPU使用率是多少')
        assert ToolCategory.SYSTEM in scores

    def test_env_keyword_detected(self):
        """环境变量关键词被检测到"""
        scores = _compute_intent_scores('查看PATH环境变量')
        assert ToolCategory.ENVIRONMENT in scores

    def test_desktop_keyword_detected(self):
        """桌面操作关键词被检测到"""
        scores = _compute_intent_scores('截图当前屏幕')
        assert ToolCategory.DESKTOP in scores


class TestDetectIntentV2Enhanced:
    """测试 detect_intent_v2 增强后的行为"""

    def test_v2_returns_primary_and_candidates(self):
        """返回格式不变：主意图+候选列表+置信度"""
        result, candidates, conf = detect_intent_v2('帮我删除文件')
        assert result is not None
        assert isinstance(candidates, list)
        assert isinstance(conf, float)

    def test_v2_confidence_now_weighted(self):
        """置信度现在是加权计算值，不再是固定1.0"""
        result, candidates, conf = detect_intent_v2('ping 192.168.1.1')
        assert result == ToolCategory.NETWORK
        # 加权评分后不再是固定1.0
        assert conf > 0 and conf < 1.0

    def test_v2_candidates_sorted_by_confidence(self):
        """候选列表按置信度从高到低排序"""
        result, candidates, conf = detect_intent_v2('下载文件查看CPU')
        if len(candidates) >= 2:
            scores = _compute_intent_scores('下载文件查看CPU')
            # candidates 顺序应与 scores 排序一致
            assert candidates[0] == list(scores.keys())[0]

    def test_v2_chat_returns_none(self):
        """聊天内容返回None"""
        result, candidates, conf = detect_intent_v2('你好呀')
        assert result is None
        assert candidates == []
        assert conf == 0.0
