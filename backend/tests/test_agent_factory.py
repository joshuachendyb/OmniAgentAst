# -*- coding: utf-8 -*-
"""
agent_factory.py 测试 — AgentFactory 声明式配置驱动

Author: 小资 - 2026-05-23
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.agent.agent_factory import AgentFactory
from app.services.agent.universal_react import UniversalReactAgent
from app.services.agent.desktop_react import DesktopReactAgent
from app.services.agent.base_react import BaseAgent
from app.services.agent.agent_config import resolve_agent_config
from unittest.mock import MagicMock


class MockLLMClient:
    pass


MOCK_TASK_ID = "test-task-factory-001"


class TestFactoryCreatePrimary:
    """主 intent_type 创建测试"""

    def _make_agent(self, intent_type):
        config = resolve_agent_config(intent_type)
        if hasattr(config, '_prompt_class'):
            config._prompt_class = MagicMock()
        with patch.object(UniversalReactAgent, "_init_tools_and_executor"), \
             patch.object(UniversalReactAgent, "_init_llm_strategies"), \
             patch.object(UniversalReactAgent, "_init_task_tracking"), \
             patch.object(UniversalReactAgent, "_init_candidates"), \
             patch.object(DesktopReactAgent, "_init_tools_and_executor"), \
             patch.object(DesktopReactAgent, "_init_llm_strategies"), \
             patch.object(DesktopReactAgent, "_init_task_tracking"), \
             patch.object(DesktopReactAgent, "_init_candidates"):
            return AgentFactory.create(
                intent_type=intent_type,
                llm_client=MockLLMClient(),
                task_id=MOCK_TASK_ID,
            )

    def test_factory_create_file(self):
        agent = self._make_agent("file")
        assert isinstance(agent, UniversalReactAgent)

    def test_factory_create_system(self):
        agent = self._make_agent("system")
        assert isinstance(agent, UniversalReactAgent)

    def test_factory_create_network(self):
        agent = self._make_agent("network")
        assert isinstance(agent, UniversalReactAgent)

    def test_factory_create_document(self):
        agent = self._make_agent("document")
        assert isinstance(agent, UniversalReactAgent)

    def test_factory_create_desktop(self):
        agent = self._make_agent("desktop")
        assert isinstance(agent, DesktopReactAgent)

    @pytest.mark.parametrize("alias,expected_class", [
        ("shell", UniversalReactAgent),
        ("time", UniversalReactAgent),
        ("meta", UniversalReactAgent),
        ("env", UniversalReactAgent),
        ("code_execution", UniversalReactAgent),
        ("database", UniversalReactAgent),
        ("environment", UniversalReactAgent),
    ])
    def test_factory_create_aliases(self, alias, expected_class):
        """所有别名创建正确的 Agent 类型"""
        agent = self._make_agent(alias)
        assert isinstance(agent, expected_class)

    def test_factory_create_unknown_raises(self):
        """未知 intent_type 抛出异常"""
        with pytest.raises(ValueError, match="Unknown intent_type"):
            AgentFactory.create(
                intent_type="nonexistent",
                llm_client=MockLLMClient(),
                task_id=MOCK_TASK_ID,
            )


class TestFactoryRegistry:
    """Factory 内部注册表"""

    def test_agents_dict_populated(self):
        """list_available_agents 返回非空"""
        agents = AgentFactory.list_available_agents()
        assert len(agents) > 0
        assert "file" in agents
        assert "desktop" in agents

    def test_tool_categories_dict_populated(self):
        """AgentFactory.create 支持所有主意图类型"""
        mock_client = MagicMock()
        for intent in ["file", "system", "desktop", "network"]:
            agent = AgentFactory.create(intent, llm_client=mock_client, task_id="test")
            assert agent is not None

    def test_list_available_agents(self):
        """list_available_agents 返回非空字典"""
        result = AgentFactory.list_available_agents()
        assert isinstance(result, dict)
        assert "file" in result
        assert "desktop" in result
        assert result["desktop"] == "DesktopReactAgent"
        assert result["file"] == "UniversalReactAgent"
