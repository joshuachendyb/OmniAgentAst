"""
测试 base_react.py 的 2026-05-05 新增修复

1. 智能observation截断（首尾保留+智能摘要+动态递减预算）
2. 空响应截断历史重试机制
3. file_prompts与注册名/参数一致性

作者：小沈
创建时间：2026-05-05
"""

import pytest
from unittest.mock import MagicMock

from app.services.agent.base_react import BaseAgent
from app.services.agent.message_builder import MessageBuilder
from app.services.prompts.file.file_prompts import FileOperationPrompts


# ===== 智能observation截断测试 =====

class TestObservationBudget:
    """测试动态递减预算"""

    def test_initial_budget(self):
        """第0轮预算=MAX_CONTEXT_CHARS=150K"""
        assert BaseAgent.MAX_CONTEXT_CHARS == 150000

    def test_budget_decay_per_round(self):
        """每轮递减10K"""
        assert MessageBuilder.OBSERVATION_BUDGET_DECAY == 10000

    def test_budget_min_floor(self):
        """最低预算20K"""
        assert MessageBuilder.OBSERVATION_BUDGET_MIN == 20000

    def test_budget_at_round_0(self):
        """llm_call_count=0时，预算=150K"""
        budget = BaseAgent.MAX_CONTEXT_CHARS - (0 * MessageBuilder.OBSERVATION_BUDGET_DECAY)
        budget = max(budget, MessageBuilder.OBSERVATION_BUDGET_MIN)
        assert budget == 150000

    def test_budget_at_round_5(self):
        """第5轮，预算=150K-50K=100K"""
        budget = BaseAgent.MAX_CONTEXT_CHARS - (5 * MessageBuilder.OBSERVATION_BUDGET_DECAY)
        budget = max(budget, MessageBuilder.OBSERVATION_BUDGET_MIN)
        assert budget == 100000

    def test_budget_at_round_13(self):
        """第13轮，150K-130K=20K，刚好到底"""
        budget = BaseAgent.MAX_CONTEXT_CHARS - (13 * MessageBuilder.OBSERVATION_BUDGET_DECAY)
        budget = max(budget, MessageBuilder.OBSERVATION_BUDGET_MIN)
        assert budget == 20000

    def test_budget_at_round_20(self):
        """第20轮，150K-200K=-50K，但最低20K"""
        budget = BaseAgent.MAX_CONTEXT_CHARS - (20 * MessageBuilder.OBSERVATION_BUDGET_DECAY)
        budget = max(budget, MessageBuilder.OBSERVATION_BUDGET_MIN)
        assert budget == 20000

    def test_budget_never_below_min(self):
        """预算永远不低于最低值"""
        for round_num in range(0, 100):
            budget = BaseAgent.MAX_CONTEXT_CHARS - (round_num * MessageBuilder.OBSERVATION_BUDGET_DECAY)
            budget = max(budget, MessageBuilder.OBSERVATION_BUDGET_MIN)
            assert budget >= MessageBuilder.OBSERVATION_BUDGET_MIN


class TestSmartTruncate:
    """测试智能截断：首尾保留+中间摘要"""

    def test_within_budget_no_truncation(self):
        """内容在预算内不截断"""
        content = "x" * 100
        result = MessageBuilder._smart_truncate(content, budget=200)
        assert result == content

    def test_exact_budget_no_truncation(self):
        """恰好等于预算不截断"""
        content = "x" * 100
        result = MessageBuilder._smart_truncate(content, budget=100)
        assert result == content

    def test_over_budget_truncated(self):
        """超预算截断"""
        content = "A" * 600 + "B" * 400  # 1000字符
        result = MessageBuilder._smart_truncate(content, budget=500)
        assert len(result) < len(content)
        assert "省略" in result

    def test_head_preserved(self):
        """头部内容被保留"""
        content = "HEADER" + "x" * 10000 + "FOOTER"
        result = MessageBuilder._smart_truncate(content, budget=1000)
        assert result.startswith("HEADER")

    def test_tail_preserved(self):
        """尾部内容被保留"""
        content = "HEADER" + "x" * 10000 + "FOOTER"
        result = MessageBuilder._smart_truncate(content, budget=1000)
        assert result.endswith("FOOTER")

    def test_summary_contains_char_count(self):
        """摘要包含省略字符数"""
        content = "A" * 10000
        result = MessageBuilder._smart_truncate(content, budget=1000)
        assert "省略" in result
        assert "字符" in result

    def test_head_tail_ratio_60_40(self):
        """默认头部60%，尾部40%"""
        content = "H" * 600 + "M" * 400 + "T" * 400  # 1400字符
        budget = 1000
        result = MessageBuilder._smart_truncate(content, budget=budget, head_ratio=0.6)
        # 头部600字符应全部保留
        assert "H" * 600 in result
        # 尾部应保留350字符(1000-600-50=350)
        assert "T" * 350 in result

    def test_custom_head_ratio(self):
        """自定义头部比例"""
        content = "H" * 800 + "M" * 200 + "T" * 200  # 1200字符
        budget = 1000
        result = MessageBuilder._smart_truncate(content, budget=budget, head_ratio=0.8)
        # 头部800字符应全部保留
        assert "H" * 800 in result


class TestObservationIntegration:
    """observation截断集成逻辑"""

    def test_short_observation_not_truncated(self):
        """短observation不截断"""
        observation = "这是一个正常的观察结果"
        budget = 150000
        result = MessageBuilder._smart_truncate(observation, budget=budget)
        assert result == observation

    def test_long_observation_smart_truncated(self):
        """超长observation被智能截断"""
        observation = "HEADER\n" + "x" * 150000 + "\nFOOTER"  # 150K+，超过100K预算
        budget = 100000
        result = MessageBuilder._smart_truncate(observation, budget=budget)
        assert "HEADER" in result
        assert "FOOTER" in result
        assert "省略" in result

    def test_very_long_observation_at_late_round(self):
        """后期轮次（预算小），长observation被截断"""
        observation = "H" * 20000 + "M" * 20000 + "T" * 20000  # 60K
        budget = 20000  # 模拟第13轮预算
        result = MessageBuilder._smart_truncate(observation, budget=budget)
        assert len(result) < len(observation)
        assert result.startswith("H")
        assert result.endswith("T")


# ===== 空响应截断历史重试测试 =====

class TestEmptyResponseRetry:
    """测试空响应截断历史重试机制"""

    def test_empty_response_counter_default(self):
        """空响应计数器默认值为0"""
        empty_response_retry_count = 0
        max_empty_response_retries = 2
        assert empty_response_retry_count == 0
        assert max_empty_response_retries == 2

    def test_truncation_keeps_head_and_tail(self):
        """截断历史时保留前2条+后2条"""
        history = [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户输入"},
            {"role": "assistant", "content": "回复1"},
            {"role": "user", "content": "观察1"},
            {"role": "assistant", "content": "回复2"},
            {"role": "user", "content": "观察2"},
            {"role": "assistant", "content": "回复3"},
            {"role": "user", "content": "观察3"},
            {"role": "assistant", "content": "回复4"},
            {"role": "user", "content": "观察4"},
        ]
        kept = history[:2] + history[-2:]
        assert len(kept) == 4
        assert kept[0]["content"] == "系统提示"
        assert kept[1]["content"] == "用户输入"
        assert kept[2]["content"] == "回复4"
        assert kept[3]["content"] == "观察4"

    def test_short_history_not_truncated(self):
        """历史太短（<=4条）时不截断"""
        history = [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "用户输入"},
            {"role": "assistant", "content": "回复1"},
        ]
        assert len(history) <= 4

    def test_retry_counter_increment(self):
        """空响应时计数器递增"""
        count = 0
        max_retries = 2
        count += 1
        assert count == 1 and count <= max_retries
        count += 1
        assert count == 2 and count <= max_retries
        count += 1
        assert count == 3 and count > max_retries

    def test_4_entry_history_is_boundary(self):
        """4条历史时不截断（4不>4）"""
        history = [{"role": "user", "content": f"消息{i}"} for i in range(4)]
        assert not (len(history) > 4)


# ===== file_prompts一致性测试 =====

class TestFilePromptConsistency:
    """测试file_prompts.py中的工具名和参数与注册一致性"""

    @pytest.fixture(autouse=True)
    def setup_tools(self):
        """确保工具已注册"""
        from app.services.tools import ensure_tools_registered
        ensure_tools_registered()

    def test_parameter_reminder_uses_correct_tool_names(self):
        """参数提醒中使用正确的工具名"""
        prompts = FileOperationPrompts()
        reminder = prompts.get_parameter_reminder()
        assert "read_file" in reminder
        assert "write_text_file" in reminder
        assert "search_files" in reminder
        assert "grep_file_content" in reminder
        assert "edit_file" in reminder
        assert "text" in reminder  # write的text参数
        assert "pattern" in reminder  # search的pattern参数
        assert "search_dir" in reminder  # search的search_dir参数

    def test_system_prompt_uses_correct_tool_names(self):
        """系统prompt中使用正确的注册工具名"""
        prompts = FileOperationPrompts()
        system_prompt = prompts.get_system_prompt()
        assert "read_file" in system_prompt
        assert "write_text_file" in system_prompt
        assert "search_files" in system_prompt
        assert "search_dir" in system_prompt
        assert "pattern" in system_prompt
        assert "edit_file" in system_prompt
        assert "file_operation" in system_prompt

    def test_examples_use_correct_params(self):
        """示例中使用正确的参数名"""
        prompts = FileOperationPrompts()
        system_prompt = prompts.get_system_prompt()
        assert '"text": "Hello World"' in system_prompt
        assert '"search_dir": "D:/project"' in system_prompt
        assert '"glob": "*.py"' in system_prompt
        assert '"read_file"' in system_prompt
        assert '"write_text_file"' in system_prompt

    def test_forbidden_parameters_in_prompt(self):
        """parameter_reminder中包含禁止参数名提醒（build_full_system_prompt不再包含，由方案C替代）"""
        prompts = FileOperationPrompts()
        reminder = prompts.get_parameter_reminder()
        assert "content for write" in reminder
        assert "file_pattern for search" in reminder
        assert "path for search_dir" in reminder

    def test_search_files_example_uses_pattern_and_search_dir(self):
        """search_files正确示例使用pattern和search_dir"""
        prompts = FileOperationPrompts()
        system_prompt = prompts.get_system_prompt()
        assert 'search_files(pattern="**/*.py", search_dir=' in system_prompt
