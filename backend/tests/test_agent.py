"""
ReAct Agent单元测试 (IntentAgent Unit Tests)
测试IntentAgent的核心功能

测试范围:
- agent_run_success: Agent成功执行任务
- agent_max_steps: 最大步数限制
- agent_rollback: Agent回滚功能
- agent_intent_type: 意图类型参数测试
- agent_preprocessing: 预处理流水线测试
- agent_intent_registry: 意图注册表测试

依赖:
- pytest: 测试框架
- pytest-asyncio: 异步测试支持
- unittest.mock: 模拟对象
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock, patch

# 导入被测试模块
from app.services.agent.agent import IntentAgent
from app.services.agent.tool_parser import ToolParser
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.types import AgentStatus, Step, AgentResult
from app.services.tools.file.file_tools import FileTools


@pytest.fixture
def mock_llm_client():
    """模拟LLM客户端"""
    async def mock_client(message, history):
        return '{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'
    return mock_client


@pytest.fixture
def mock_file_tools():
    """模拟文件工具"""
    tools = MagicMock(spec=FileTools)
    tools.read_file = MagicMock(return_value={"success": True, "content": "test content"})
    tools.write_file = MagicMock(return_value={"success": True})
    return tools


@pytest.fixture
def mock_session_service():
    """模拟会话服务"""
    service = MagicMock()
    service.create_session = MagicMock(return_value="sess-test-001")
    service.get_session = MagicMock(return_value={"session_id": "sess-test-001"})
    service.update_session = MagicMock()
    return service


class TestIntentAgentInitialization:
    """测试IntentAgent初始化"""
    
    def test_agent_creation(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试Agent创建成功"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=20
        )
        
        assert agent is not None
        assert agent.max_steps == 20
        assert agent.session_id == "sess-test-001"
    
    def test_agent_has_required_attributes(self, mock_llm_client, mock_file_tools):
        """测试Agent有必需的属性"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools
        )
        
        assert hasattr(agent, 'llm_client')
        assert hasattr(agent, 'session_id')
        assert hasattr(agent, 'max_steps')
        assert hasattr(agent, 'executor')


class TestIntentAgentRun:
    """测试IntentAgent运行"""
    
    @pytest.mark.asyncio
    async def test_agent_run_success(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试Agent成功执行任务"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=5,
            # 提供LLM配置以启用adapter
            api_base="http://test.com",
            api_key="test-key",
            model="test-model"
        )
        
        with patch('app.services.agent.session.get_session_service', return_value=mock_session_service):
            with patch.object(agent.executor, 'execute', return_value={"success": True, "data": {"result": "done"}}):
                with patch.object(agent, '_get_llm_response_text', return_value='{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'):
                    result = await agent.run_with_tools("test task")
                    
                    assert result.success == True
                    assert result.total_steps >= 1
    
    @pytest.mark.asyncio
    async def test_agent_max_steps(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试Agent最大步数限制"""
        # 模拟一个永不返回finish的LLM
        async def never_finish_client(message, history):
            return '{"thought": "thinking", "action_tool": "read_file", "params": {"path": "test.txt"}}'
        
        agent = IntentAgent(
            llm_client=never_finish_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=3,
            # 提供LLM配置以启用adapter
            api_base="http://test.com",
            api_key="test-key",
            model="test-model"
        )
        
        with patch('app.services.agent.session.get_session_service', return_value=mock_session_service):
            with patch.object(agent.executor, 'execute', return_value={"success": True, "data": {"content": "test"}}):
                result = await agent.run_with_tools("test task")
                
                assert result.success == False
                assert result.total_steps == 3


class TestIntentAgentStatus:
    """测试IntentAgent状态"""
    
    def test_agent_initial_status(self, mock_llm_client, mock_file_tools):
        """测试Agent初始状态"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools
        )
        
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_agent_completed_status(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试Agent完成状态"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=5,
            # 提供LLM配置以启用adapter
            api_base="http://test.com",
            api_key="test-key",
            model="test-model"
        )
        
        with patch('app.services.agent.session.get_session_service', return_value=mock_session_service):
            with patch.object(agent.executor, 'execute', return_value={"success": True, "data": {"result": "done"}}):
                with patch.object(agent, '_get_llm_response_text', return_value='{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'):
                    await agent.run_with_tools("test task")
                    
                    assert agent.status == AgentStatus.COMPLETED


class TestIntentAgentSteps:
    """测试IntentAgent步骤记录"""
    
    @pytest.mark.asyncio
    async def test_agent_records_steps(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试Agent记录步骤"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=5,
            # 提供LLM配置以启用adapter
            api_base="http://test.com",
            api_key="test-key",
            model="test-model"
        )
        
        with patch('app.services.agent.session.get_session_service', return_value=mock_session_service):
            with patch.object(agent.executor, 'execute', return_value={"success": True, "data": {"result": "done"}}):
                with patch.object(agent, '_get_llm_response_text', return_value='{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'):
                    result = await agent.run_with_tools("test task")
                    
                    assert len(result.steps) >= 1
                    assert result.steps[0].step_number == 1


class TestIntentAgentLLMCounter:
    """测试IntentAgent LLM调用计数"""
    
    @pytest.mark.asyncio
    async def test_llm_call_counter(self, mock_llm_client, mock_file_tools, mock_session_service):
        """测试LLM调用计数器"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools,
            max_steps=5
        )
        
        with patch('app.services.agent.session.get_session_service', return_value=mock_session_service):
            with patch.object(agent.executor, 'execute', return_value={"success": True, "data": {"result": "done"}}):
                initial_count = agent.llm_call_count
                await agent.run_with_tools("test task")
                
                assert agent.llm_call_count > initial_count


class TestIntentAgentBackwardCompatibility:
    """测试IntentAgent向后兼容"""
    
    def test_import_from_agent(self):
        """测试从agent模块导入IntentAgent"""
        from app.services.agent import IntentAgent
        assert IntentAgent is not None
    
    def test_agent_name_is_intent_agent(self, mock_llm_client, mock_file_tools):
        """测试Agent类名是IntentAgent"""
        agent = IntentAgent(
            llm_client=mock_llm_client,
            session_id="sess-test-001",
            file_tools=mock_file_tools
        )
        
        assert agent.__class__.__name__ == "IntentAgent"


class TestIntentAgentMultiIntentSupport:
    """测试IntentAgent多意图支持（体现重构意义）"""
    
    def test_intent_type_default_is_file(self):
        """测试intent_type默认值为file"""
        from app.services.agent.agent import IntentAgent
        import inspect
        sig = inspect.signature(IntentAgent.__init__)
        intent_type_param = sig.parameters['intent_type']
        assert intent_type_param.default == "file"
    
    def test_intent_type_custom_desktop(self):
        """测试intent_type可设置为desktop"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            with patch('app.services.agent.agent.logger') as mock_logger:
                agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools, intent_type="desktop")
                assert agent.intent_type == "desktop"
                mock_logger.warning.assert_called()
    
    def test_intent_type_custom_network(self):
        """测试intent_type可设置为network"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            with patch('app.services.agent.agent.logger') as mock_logger:
                agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools, intent_type="network")
                assert agent.intent_type == "network"
                mock_logger.warning.assert_called()
    
    def test_intent_type_unsupported_raises(self):
        """测试不支持的intent_type抛出异常"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            with pytest.raises(ValueError, match="Unsupported intent_type"):
                IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools, intent_type="unknown")


class TestIntentAgentPreprocessingAndRegistry:
    """测试IntentAgent预处理流水线和意图注册表（体现重构意义）"""
    
    def test_agent_has_preprocessor(self):
        """测试Agent有preprocessor属性"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            assert hasattr(agent, 'preprocessor')
    
    def test_agent_has_intent_registry(self):
        """测试Agent有intent_registry属性"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            assert hasattr(agent, 'intent_registry')
    
    def test_agent_registers_file_intent(self):
        """测试Agent注册file意图"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            file_intent = agent.intent_registry.get("file")
            assert file_intent is not None
            assert file_intent.name == "file"
    
    def test_agent_registers_network_intent(self):
        """测试Agent注册network意图"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            network_intent = agent.intent_registry.get("network")
            assert network_intent is not None
            assert network_intent.name == "network"
    
    def test_preprocessor_is_preprocessing_pipeline(self):
        """测试preprocessor是PreprocessingPipeline实例"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        from app.services.preprocessing import PreprocessingPipeline
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            assert isinstance(agent.preprocessor, PreprocessingPipeline)
    
    def test_intent_registry_is_intent_registry(self):
        """测试intent_registry是IntentRegistry实例"""
        from unittest.mock import MagicMock, patch
        from app.services.agent.agent import IntentAgent
        from app.services.intent import IntentRegistry
        mock_llm = MagicMock()
        mock_tools = MagicMock()
        with patch('app.services.agent.agent.get_session_service'):
            agent = IntentAgent(llm_client=mock_llm, session_id="test", file_tools=mock_tools)
            assert isinstance(agent.intent_registry, IntentRegistry)
