"""
Agent LLMAdapter 集成测试 (Agent LLMAdapter Integration Tests)
测试 IntentAgent 与 LLMAdapter 的集成功能

测试范围:
- LLMAdapter 初始化
- _get_llm_response 自适应策略选择
- _get_llm_response_with_response_format 方法
- 向后兼容性（不提供 api 配置时使用原有方式）

依赖:
- pytest: 测试框架
- pytest-asyncio: 异步测试支持
- unittest.mock: 模拟对象

创建时间: 2026-03-20 11:45:00
编写人: 小沈
重命名: 2026-03-22 小沈 - IntentAgent → IntentAgent
"""

import pytest
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock, patch, PropertyMock

# 导入被测试模块
from app.services.agent import IntentAgent
from app.services.agent.tool_parser import ToolParser
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.types import AgentStatus, Step, AgentResult
from app.services.tools.file.file_tools import FileTools
from app.services.agent.capability import LLMCapability
from app.services.agent.strategy_selector import SelectedStrategy


# ============ Fixtures ============

@pytest.fixture
def mock_llm_client():
    """创建模拟 LLM 客户端"""
    async def mock_chat(message, history=None):
        return Mock(content=json.dumps({
            "thought": "I will finish the task",
            "action": "finish",
            "action_input": {"result": "Task completed successfully"}
        }))
    
    return mock_chat


@pytest.fixture
def mock_file_tools():
    """创建模拟文件工具"""
    tools = MagicMock(spec=FileTools)
    tools.session_id = "test-session"
    tools.set_session = Mock()
    return tools


@pytest.fixture
def mock_llm_adapter():
    """创建模拟 LLMAdapter"""
    adapter = MagicMock()
    adapter.api_base = "https://api.example.com"
    adapter.api_key = "test-key"
    adapter.model = "test-model"
    return adapter


@pytest.fixture
def agent_with_adapter(mock_llm_client, mock_file_tools, mock_llm_adapter):
    """创建带 LLMAdapter 的 Agent 实例"""
    with patch('app.services.agent.agent.get_session_service') as mock_session:
        mock_session_service = MagicMock()
        mock_session_service.create_session.return_value = "test-session"
        mock_session_service.complete_session.return_value = None
        mock_session.return_value = mock_session_service
        
        with patch('app.services.agent.agent.LLMAdapter') as MockLLMAdapter:
            MockLLMAdapter.return_value = mock_llm_adapter
            
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session",
                file_tools=mock_file_tools,
                max_steps=5,
                api_base="https://api.example.com",
                api_key="test-key",
                model="test-model"
            )
            yield agent


@pytest.fixture
def agent_without_adapter(mock_llm_client, mock_file_tools):
    """创建不带 LLMAdapter 的 Agent 实例（向后兼容）"""
    with patch('app.services.agent.agent.get_session_service') as mock_session:
        mock_session_service = MagicMock()
        mock_session_service.create_session.return_value = "test-session"
        mock_session_service.complete_session.return_value = None
        mock_session.return_value = mock_session_service
        
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="test-session",
            file_tools=mock_file_tools,
            max_steps=5
        )
        yield agent


# ============ Test Classes ============

class TestAgentLLMAdapterIntegration:
    """测试 Agent 与 LLMAdapter 的集成"""
    pass


class TestLLMAdapterInitialization:
    """测试 LLMAdapter 初始化"""
    
    def test_agent_with_api_config_initializes_adapter(self, mock_llm_client, mock_file_tools):
        """TC070: 提供 API 配置时初始化 LLMAdapter"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            with patch('app.services.agent.agent.LLMAdapter') as MockLLMAdapter:
                mock_adapter = MagicMock()
                MockLLMAdapter.return_value = mock_adapter
                
                agent = IntentAgent(
                    llm_client=mock_llm_client,
                    session_id="test-session",
                    api_base="https://api.example.com",
                    api_key="test-key",
                    model="test-model"
                )
                
                # 验证 LLMAdapter 被调用
                MockLLMAdapter.assert_called_once_with(
                    api_base="https://api.example.com",
                    api_key="test-key",
                    model="test-model",
                    auto_detect=True
                )
                assert agent.adapter is not None
    
    def test_agent_without_api_config_no_adapter(self, mock_llm_client, mock_file_tools):
        """TC071: 不提供 API 配置时不初始化 LLMAdapter"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session"
            )
            
            assert agent.adapter is None
    
    def test_agent_with_partial_api_config_no_adapter(self, mock_llm_client, mock_file_tools):
        """TC072: 只提供部分 API 配置时不初始化 LLMAdapter"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            # 只提供 api_base，没有 api_key 和 model
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session",
                api_base="https://api.example.com"
            )
            
            assert agent.adapter is None


class TestGetLLMResponseAdaptive:
    """测试 _get_llm_response 自适应策略选择"""
    
    @pytest.mark.asyncio
    async def test_get_llm_response_with_response_format_strategy(self, agent_with_adapter):
        """TC073: 使用 response_format 策略"""
        # 设置策略为 response_format
        agent_with_adapter.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="response_format",
            capability=LLMCapability.RESPONSE_FORMAT,
            description="使用 response_format"
        ))
        
        # 设置 llm_client 的 chat_with_response_format 方法
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "Using response format",
                    "action": "finish",
                    "action_input": {"result": "Success"}
                }),
                error=None
            )
        
        agent_with_adapter.llm_client.chat_with_response_format = mock_response_format
        
        # 设置对话历史
        agent_with_adapter.conversation_history = [
            {"role": "user", "content": "Test task"}
        ]
        
        # 调用 _get_llm_response
        result = await agent_with_adapter._get_llm_response()
        
        # 验证使用了 response_format 方法
        assert "finish" in result
        assert "Using response format" in result or "action" in result
    
    @pytest.mark.asyncio
    async def test_get_llm_response_with_tools_strategy(self, agent_with_adapter):
        """TC074: 使用 tools 策略"""
        # 设置策略为 tools
        agent_with_adapter.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="使用 tools"
        ))
        
        # 设置 llm_client 的 chat_with_tools 方法
        async def mock_chat_with_tools(message, history=None, tools=None):
            return Mock(
                content=json.dumps([{
                    "function": {
                        "name": "finish",
                        "arguments": {"result": "Success"}
                    }
                }]),
                error=None
            )
        
        agent_with_adapter.llm_client.chat_with_tools = mock_chat_with_tools
        
        # 设置对话历史
        agent_with_adapter.conversation_history = [
            {"role": "user", "content": "Test task"}
        ]
        
        # 调用 _get_llm_response
        result = await agent_with_adapter._get_llm_response()
        
        # 验证使用了 tools 方法
        assert "finish" in result
        assert agent_with_adapter.conversation_history[-1]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_get_llm_response_with_prompt_strategy(self, agent_with_adapter):
        """TC075: 使用 prompt 降级策略"""
        # 设置策略为 prompt（降级）
        agent_with_adapter.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="prompt",
            capability=LLMCapability.NONE,
            description="降级到 prompt"
        ))
        
        # 设置 llm_client
        async def mock_chat(message, history=None):
            return Mock(content="使用 prompt 模式")
        
        agent_with_adapter.llm_client = mock_chat
        
        # 设置对话历史
        agent_with_adapter.conversation_history = [
            {"role": "user", "content": "Test task"}
        ]
        
        # 调用 _get_llm_response
        result = await agent_with_adapter._get_llm_response()
        
        # 验证使用了 prompt 方法
        assert result == "使用 prompt 模式"
    
    @pytest.mark.asyncio
    async def test_get_llm_response_backward_compatible_function_calling(self, agent_without_adapter):
        """TC076: 向后兼容 - 使用 Function Calling 模式"""
        # 启用 Function Calling
        agent_without_adapter.use_function_calling = True
        agent_without_adapter.tools = [{"type": "function"}]
        
        # 设置 llm_client 的 chat_with_tools 方法
        async def mock_chat_with_tools(message, history=None, tools=None):
            return Mock(
                content=json.dumps([{
                    "function": {
                        "name": "finish",
                        "arguments": {"result": "Success"}
                    }
                }]),
                error=None
            )
        
        agent_without_adapter.llm_client.chat_with_tools = mock_chat_with_tools
        
        # 设置对话历史
        agent_without_adapter.conversation_history = [
            {"role": "user", "content": "Test task"}
        ]
        
        # 调用 _get_llm_response
        result = await agent_without_adapter._get_llm_response()
        
        # 验证使用了 tools 方法
        assert "finish" in result
    
    @pytest.mark.asyncio
    async def test_get_llm_response_backward_compatible_text_mode(self, agent_without_adapter):
        """TC077: 向后兼容 - 使用文本模式"""
        # 不启用 Function Calling
        agent_without_adapter.use_function_calling = False
        
        # 设置 llm_client
        async def mock_chat(message, history=None):
            return Mock(content="文本模式响应")
        
        agent_without_adapter.llm_client = mock_chat
        
        # 设置对话历史
        agent_without_adapter.conversation_history = [
            {"role": "user", "content": "Test task"}
        ]
        
        # 调用 _get_llm_response
        result = await agent_without_adapter._get_llm_response()
        
        # 验证使用了文本方法
        assert result == "文本模式响应"


class TestGetLLMResponseWithResponseFormat:
    """测试 _get_llm_response_with_response_format 方法"""
    
    @pytest.fixture
    def agent_for_response_format(self, mock_llm_client, mock_file_tools):
        """创建用于 response_format 测试的 Agent"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session",
                file_tools=mock_file_tools,
                max_steps=5
            )
            return agent
    
    @pytest.mark.asyncio
    async def test_response_format_basic(self, agent_for_response_format):
        """TC078: response_format 基本功能"""
        # 设置 llm_client 的 chat_with_response_format 方法
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "I need to finish this task",
                    "action": "finish",
                    "action_input": {"result": "Completed"}
                }),
                error=None
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_response_format
        
        # 调用 _get_llm_response_with_response_format
        result = await agent_for_response_format._get_llm_response_with_response_format(
            message="Test task",
            history_dicts=[]
        )
        
        # 验证返回格式正确
        parsed = json.loads(result)
        assert "thought" in parsed
        assert parsed["thought"] == "I need to finish this task"
    
    @pytest.mark.asyncio
    async def test_response_format_with_history(self, agent_for_response_format):
        """TC079: response_format 处理对话历史"""
        # 设置 llm_client
        async def mock_response_format(message, history=None, response_format=None):
            # 验证 history 被传递
            assert history is not None
            assert len(history) > 0
            return Mock(
                content=json.dumps({
                    "thought": "Based on history",
                    "action": "finish",
                    "action_input": {"result": "Done"}
                }),
                error=None
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_response_format
        
        # 调用时传入历史
        result = await agent_for_response_format._get_llm_response_with_response_format(
            message="Continue task",
            history_dicts=[{"role": "user", "content": "Previous task"}]
        )
        
        # 验证成功
        assert "finish" in result
    
    @pytest.mark.asyncio
    async def test_response_format_error_handling(self, agent_for_response_format):
        """TC080: response_format 错误处理"""
        # 设置 llm_client 返回错误
        async def mock_error_response(message, history=None, response_format=None):
            return Mock(
                content="",
                error="API Error"
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_error_response
        
        # 调用应该抛出异常
        with pytest.raises(Exception) as exc_info:
            await agent_for_response_format._get_llm_response_with_response_format(
                message="Test task",
                history_dicts=[]
            )
        
        assert "API Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_response_format_invalid_json(self, agent_for_response_format):
        """TC081: response_format 处理无效 JSON"""
        # 设置 llm_client 返回无效 JSON
        async def mock_invalid_json_response(message, history=None, response_format=None):
            return Mock(
                content="This is not valid JSON",
                error=None
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_invalid_json_response
        
        # 调用应该抛出异常
        with pytest.raises(Exception) as exc_info:
            await agent_for_response_format._get_llm_response_with_response_format(
                message="Test task",
                history_dicts=[]
            )
        
        assert "Invalid JSON" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_response_format_with_reasoning(self, agent_for_response_format):
        """TC082: response_format 支持 reasoning 字段"""
        # 设置 llm_client 返回带 reasoning 的响应
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "I need to think step by step",
                    "action": "list_directory",
                    "action_input": {"dir_path": "/tmp"},
                    "reasoning": "First I need to see what files exist"
                }),
                error=None
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_response_format
        
        # 调用
        result = await agent_for_response_format._get_llm_response_with_response_format(
            message="List files",
            history_dicts=[]
        )
        
        # 验证返回包含所有字段
        parsed = json.loads(result)
        assert "thought" in parsed
        assert "action_tool" in parsed or "action" in parsed
    
    @pytest.mark.asyncio
    async def test_response_format_schema_structure(self, agent_for_response_format):
        """TC083: response_format 使用正确的 schema 结构"""
        schema_received = [None]
        
        async def mock_response_format(message, history=None, response_format=None):
            # 保存接收到的 schema
            schema_received[0] = response_format
            return Mock(
                content=json.dumps({
                    "thought": "Test",
                    "action": "finish",
                    "action_input": {}
                }),
                error=None
            )
        
        agent_for_response_format.llm_client.chat_with_response_format = mock_response_format
        
        await agent_for_response_format._get_llm_response_with_response_format(
            message="Test",
            history_dicts=[]
        )
        
        # 验证 schema 结构
        schema = schema_received[0]
        assert schema is not None
        assert schema["type"] == "json_object"
        assert "json_schema" in schema
        assert "properties" in schema["json_schema"]
        assert "thought" in schema["json_schema"]["properties"]
        assert "action" in schema["json_schema"]["properties"]
        assert "action_input" in schema["json_schema"]["properties"]


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_original_init_signature_works(self, mock_llm_client, mock_file_tools):
        """TC084: 原有初始化签名仍然有效"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            # 使用原有签名（不提供 api 参数）
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session",
                file_tools=mock_file_tools,
                max_steps=20,
                use_function_calling=False,
                tools=[]
            )
            
            assert agent.session_id == "test-session"
            assert agent.max_steps == 20
            assert agent.use_function_calling is False
            assert agent.tools == []
            assert agent.adapter is None
    
    def test_new_init_signature_works(self, mock_llm_client, mock_file_tools):
        """TC085: 新初始化签名有效"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            with patch('app.services.agent.agent.LLMAdapter') as MockLLMAdapter:
                MockLLMAdapter.return_value = MagicMock()
                
                # 使用新签名（提供 api 参数）
                agent = IntentAgent(
                    llm_client=mock_llm_client,
                    session_id="test-session",
                    file_tools=mock_file_tools,
                    max_steps=20,
                    use_function_calling=True,
                    tools=[{"type": "function"}],
                    api_base="https://api.example.com",
                    api_key="test-key",
                    model="test-model"
                )
                
                assert agent.session_id == "test-session"
                assert agent.adapter is not None


class TestLLMCallCounter:
    """测试 LLM 调用计数器"""
    
    @pytest.mark.asyncio
    async def test_llm_counter_increments(self, agent_with_adapter):
        """TC086: LLM 调用时计数器递增"""
        # 设置策略为 prompt（降级）
        agent_with_adapter.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="prompt",
            capability=LLMCapability.NONE,
            description="降级"
        ))
        
        async def mock_chat(message, history=None):
            return Mock(content="Response")
        
        agent_with_adapter.llm_client = mock_chat
        agent_with_adapter.conversation_history = [
            {"role": "user", "content": "Test"}
        ]
        
        initial_count = agent_with_adapter.llm_call_count
        
        await agent_with_adapter._get_llm_response()
        
        assert agent_with_adapter.llm_call_count == initial_count + 1


class TestAgentRunIntegration:
    """测试 agent.run() 完整流程集成"""
    
    @pytest.fixture
    def agent_for_run_integration(self, mock_llm_client, mock_file_tools):
        """创建用于 run() 集成的 Agent"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            with patch('app.services.agent.agent.LLMAdapter') as MockLLMAdapter:
                mock_adapter = MagicMock()
                MockLLMAdapter.return_value = mock_adapter
                
                agent = IntentAgent(
                    llm_client=mock_llm_client,
                    session_id="test-session",
                    file_tools=mock_file_tools,
                    max_steps=5,
                    api_base="https://api.example.com",
                    api_key="test-key",
                    model="test-model"
                )
                yield agent
    
    @pytest.mark.asyncio
    async def test_run_with_adapter_response_format(self, agent_for_run_integration):
        """TC087: agent.run() 使用 adapter response_format 策略"""
        # 设置策略为 response_format
        agent_for_run_integration.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="response_format",
            capability=LLMCapability.RESPONSE_FORMAT,
            description="response_format"
        ))
        
        # 设置 llm_client
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "Task is simple, finishing now",
                    "action": "finish",
                    "action_input": {"result": "Completed"}
                }),
                error=None
            )
        
        agent_for_run_integration.llm_client.chat_with_response_format = mock_response_format
        
        # 运行 agent
        result = await agent_for_run_integration.run("Simple task")
        
        # 验证结果
        assert result.success is True
        assert agent_for_run_integration.status == AgentStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_run_with_adapter_tools_strategy(self, agent_for_run_integration):
        """TC088: agent.run() 使用 adapter tools 策略"""
        # 设置策略为 tools
        agent_for_run_integration.adapter.ensure_capability = AsyncMock(return_value=SelectedStrategy(
            method="tools",
            capability=LLMCapability.TOOLS,
            description="tools"
        ))
        
        # 设置 llm_client
        async def mock_chat_with_tools(message, history=None, tools=None):
            return Mock(
                content=json.dumps([{
                    "function": {
                        "name": "finish",
                        "arguments": {"result": "Done"}
                    }
                }]),
                error=None
            )
        
        agent_for_run_integration.llm_client.chat_with_tools = mock_chat_with_tools
        
        # 运行 agent
        result = await agent_for_run_integration.run("Finish task")
        
        # 验证结果
        assert result.success is True
        assert agent_for_run_integration.status == AgentStatus.COMPLETED


class TestResponseFormatDataConversion:
    """测试 response_format 数据转换"""
    
    @pytest.fixture
    def agent_for_conversion(self, mock_llm_client, mock_file_tools):
        """创建用于数据转换测试的 Agent"""
        with patch('app.services.agent.agent.get_session_service') as mock_session:
            mock_session_service = MagicMock()
            mock_session_service.create_session.return_value = "test-session"
            mock_session.return_value = mock_session_service
            
            agent = IntentAgent(
                llm_client=mock_llm_client,
                session_id="test-session",
                file_tools=mock_file_tools,
                max_steps=5
            )
            return agent
    
    @pytest.mark.asyncio
    async def test_response_format_converts_action_to_action_tool(self, agent_for_conversion):
        """TC089: response_format 将 action 转换为 action_tool"""
        # 设置 llm_client
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "Need to read a file",
                    "action": "read_file",
                    "action_input": {"file_path": "/tmp/test.txt"}
                }),
                error=None
            )
        
        agent_for_conversion.llm_client.chat_with_response_format = mock_response_format
        
        # 调用方法
        result = await agent_for_conversion._get_llm_response_with_response_format(
            message="Read the file",
            history_dicts=[]
        )
        
        # 验证转换正确
        parsed = json.loads(result)
        assert "action_tool" in parsed
        assert parsed["action_tool"] == "read_file"
        assert parsed["params"] == {"file_path": "/tmp/test.txt"}
    
    @pytest.mark.asyncio
    async def test_response_format_updates_conversation_history(self, agent_for_conversion):
        """TC090: response_format 正确更新对话历史"""
        # 设置 llm_client
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "Thinking...",
                    "action": "finish",
                    "action_input": {"result": "Done"}
                }),
                error=None
            )
        
        agent_for_conversion.llm_client.chat_with_response_format = mock_response_format
        
        # 初始历史
        agent_for_conversion.conversation_history = [
            {"role": "user", "content": "User message"}
        ]
        initial_history_len = len(agent_for_conversion.conversation_history)
        
        # 调用方法
        result = await agent_for_conversion._get_llm_response_with_response_format(
            message="Test",
            history_dicts=[{"role": "user", "content": "User message"}]
        )
        
        # 验证历史被更新
        assert len(agent_for_conversion.conversation_history) == initial_history_len + 1
        assert agent_for_conversion.conversation_history[-1]["role"] == "assistant"
    
    @pytest.mark.asyncio
    async def test_response_format_returns_correct_json_structure(self, agent_for_conversion):
        """TC091: response_format 返回正确的 JSON 结构"""
        # 设置 llm_client 返回完整结构
        async def mock_response_format(message, history=None, response_format=None):
            return Mock(
                content=json.dumps({
                    "thought": "I need to list directory",
                    "action": "list_directory",
                    "action_input": {"dir_path": "/tmp"},
                    "reasoning": "To see available files"
                }),
                error=None
            )
        
        agent_for_conversion.llm_client.chat_with_response_format = mock_response_format
        
        # 调用方法
        result = await agent_for_conversion._get_llm_response_with_response_format(
            message="List files",
            history_dicts=[]
        )
        
        # 验证返回结构
        parsed = json.loads(result)
        
        # 验证必要的字段
        assert "thought" in parsed
        assert "action_tool" in parsed
        assert "params" in parsed
        
        # 验证值正确
        assert parsed["thought"] == "I need to list directory"
        assert parsed["action_tool"] == "list_directory"
        assert parsed["params"] == {"dir_path": "/tmp"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
