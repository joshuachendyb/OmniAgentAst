# -*- coding: utf-8 -*-
"""
后端测试全局 fixtures — 小沈 2026-05-26
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.agent.universal_react import UniversalReactAgent
from app.services.agent.agent_config import AgentConfig, resolve_agent_config
from app.services.tools.registry import ToolCategory


class MockLLMClient:
    """轻量级 LLM client mock，避免真实HTTP调用"""
    chat = AsyncMock(return_value={"content": "mock response"})
    chat_stream = AsyncMock()
    chat_with_tools = AsyncMock(return_value={"content": "mock response"})


MOCK_TASK_ID = "test-task-001"

INIT_METHODS = [
    "_init_tools_and_executor",
    "_init_llm_strategies",
    "_init_task_tracking",
    "_init_candidates",
]


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def file_config():
    return resolve_agent_config("file")


@pytest.fixture
def system_config():
    return resolve_agent_config("system")


@pytest.fixture
def mock_agent(file_config, mock_llm):
    """创建 mock 掉 mixin init 的 UniversalReactAgent（file config）"""
    config = file_config
    config._prompt_class = MagicMock()
    with patch.object(UniversalReactAgent, "_init_tools_and_executor"), \
         patch.object(UniversalReactAgent, "_init_llm_strategies"), \
         patch.object(UniversalReactAgent, "_init_task_tracking"), \
         patch.object(UniversalReactAgent, "_init_candidates"):
        agent = UniversalReactAgent(
            llm_client=mock_llm,
            task_id=MOCK_TASK_ID,
            config=config,
        )
    agent._candidates = []
    agent.executor = MagicMock()
    return agent


def make_mock_agent(config=None, task_id=MOCK_TASK_ID, llm_client=None):
    """辅助函数：创建 mock agent，可自定义 config/task_id"""
    if config is None:
        config = resolve_agent_config("file")
    if llm_client is None:
        llm_client = MockLLMClient()
    config._prompt_class = MagicMock()
    with patch.object(UniversalReactAgent, "_init_tools_and_executor"), \
         patch.object(UniversalReactAgent, "_init_llm_strategies"), \
         patch.object(UniversalReactAgent, "_init_task_tracking"), \
         patch.object(UniversalReactAgent, "_init_candidates"):
        agent = UniversalReactAgent(
            llm_client=llm_client,
            task_id=task_id,
            config=config,
        )
    agent._candidates = []
    agent.executor = MagicMock()
    return agent
