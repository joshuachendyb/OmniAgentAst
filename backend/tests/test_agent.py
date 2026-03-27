"""
ReAct Agent单元测试 (IntentAgent Unit Tests)

测试范围:
- BaseAgent 抽象方法实现
- IntentAgent 继承结构
- run_stream 核心循环逻辑
- 事件流结构 (thought → action_tool → observation)

Author: 小健 - 2026-03-25
"""

import pytest
import asyncio
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from app.services.agent.base_react import BaseAgent
from app.services.agent import IntentAgent
from app.services.agent.types import AgentStatus
from app.services.tools.file.file_tools import FileTools


def create_mock_llm(responses: List[str]):
    """创建模拟 LLM 客户端"""
    mock = AsyncMock()
    mock.side_effect = responses
    return mock


class TestBaseAgentAbstractMethods:
    """测试 BaseAgent 抽象方法实现"""
    
    def test_base_agent_cannot_be_instantiated(self):
        """测试 BaseAgent 不能直接实例化"""
        with pytest.raises(TypeError):
            BaseAgent(max_steps=10)
    
    def test_concrete_agent_implements_abstract_methods(self):
        """测试具体 Agent 必须实现抽象方法"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        assert hasattr(agent, '_get_llm_response')
        assert hasattr(agent, '_execute_tool')
        assert hasattr(agent, '_get_system_prompt')
        assert hasattr(agent, '_get_task_prompt')


class TestIntentAgentInitialization:
    """测试 IntentAgent 初始化"""
    
    def test_agent_creation(self):
        """测试 Agent 创建成功"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="sess-test-001",
            file_tools=MagicMock(spec=FileTools),
            max_steps=20
        )
        
        assert agent is not None
        assert agent.max_steps == 20
        assert agent.session_id == "sess-test-001"
    
    def test_agent_has_required_attributes(self):
        """测试 Agent 有必需的属性"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="sess-test-001",
            file_tools=MagicMock(spec=FileTools)
        )
        
        assert hasattr(agent, 'llm_client')
        assert hasattr(agent, 'session_id')
        assert hasattr(agent, 'max_steps')
        assert hasattr(agent, 'executor')
        assert hasattr(agent, 'prompts')
    
    def test_agent_intent_type_default(self):
        """测试 intent_type 默认值为 file"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="sess-test-001",
            file_tools=MagicMock(spec=FileTools)
        )
        
        assert agent.intent_type == "file"


class TestRunStreamBasicFlow:
    """测试 run_stream 基本流程"""
    
    @pytest.mark.asyncio
    async def test_run_stream_single_step_finish(self):
        """测试单步完成任务"""
        mock_llm = create_mock_llm([
            '{"thought": "任务完成", "action_tool": "finish", "params": {"result": "测试成功"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        events = []
        async for event in agent.run_stream("测试任务"):
            events.append(event)
        
        assert len(events) >= 2
        assert events[0]["type"] == "thought"
        assert events[0]["action_tool"] == "finish"
        assert events[-1]["type"] == "final"
        assert events[-1]["content"] == "测试成功"
    
    @pytest.mark.asyncio
    async def test_run_stream_three_phase_loop(self):
        """测试三阶段循环: thought → action_tool → observation"""
        mock_llm = create_mock_llm([
            '{"thought": "需要读取文件", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "文件内容已读取", "action_tool": "finish", "params": {"result": "读取成功"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "文件内容"}, "summary": "读取成功"}
            
            events = []
            async for event in agent.run_stream("读取文件"):
                events.append(event)
            
            event_types = [e["type"] for e in events]
            
            assert "thought" in event_types
            assert "action_tool" in event_types
            assert "observation" in event_types
            assert "final" in event_types
    
    @pytest.mark.asyncio
    async def test_run_stream_max_steps_limit(self):
        """测试最大步数限制"""
        # 创建一个永远返回非 finish 的 LLM 模拟
        async def infinite_llm(message, history=None):
            return '{"thought": "继续执行", "action_tool": "read_file", "params": {"path": "test.txt"}}'
        
        agent = IntentAgent(
            llm_client=infinite_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=3
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "成功"}
            
            events = []
            async for event in agent.run_stream("测试任务"):
                events.append(event)
            
            # 验证达到最大步数
            # 由于每次循环会调用2次LLM(thought+observation)，max_steps=3会执行3次循环
            # 最后会因为达到max_steps而结束
            assert len(events) > 0


class TestRunStreamEventStructure:
    """测试事件结构"""
    
    @pytest.mark.asyncio
    async def test_thought_event_structure(self):
        """测试 thought 事件结构"""
        mock_llm = create_mock_llm([
            '{"thought": "思考中", "action_tool": "finish", "params": {"result": "done"}, "reasoning": "推理过程"}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        events = []
        async for event in agent.run_stream("测试"):
            events.append(event)
        
        thought_event = events[0]
        assert thought_event["type"] == "thought"
        assert "step" in thought_event
        assert "timestamp" in thought_event
        assert "content" in thought_event
        assert "action_tool" in thought_event
        assert "params" in thought_event
    
    @pytest.mark.asyncio
    async def test_action_tool_event_structure(self):
        """测试 action_tool 事件结构"""
        mock_llm = create_mock_llm([
            '{"thought": "执行动作", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "完成", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "读取成功"}
            
            events = []
            async for event in agent.run_stream("测试"):
                events.append(event)
            
            action_events = [e for e in events if e["type"] == "action_tool"]
            assert len(action_events) > 0
            
            action_event = action_events[0]
            assert "step" in action_event
            assert "tool_name" in action_event
            assert "tool_params" in action_event
            assert "execution_status" in action_event
            assert "summary" in action_event
            assert "raw_data" in action_event
    
    @pytest.mark.asyncio
    async def test_observation_event_structure(self):
        """测试 observation 事件结构"""
        mock_llm = create_mock_llm([
            '{"thought": "执行动作", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "观察结果", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "读取成功"}
            
            events = []
            async for event in agent.run_stream("测试"):
                events.append(event)
            
            obs_events = [e for e in events if e["type"] == "observation"]
            assert len(obs_events) > 0
            
            obs_event = obs_events[0]
            assert "step" in obs_event
            assert "content" in obs_event
            assert "obs_action_tool" in obs_event
            assert "is_finished" in obs_event


class TestRunStreamObservationData:
    """测试 observation 包含实际数据（核心修复）"""
    
    @pytest.mark.asyncio
    async def test_observation_contains_raw_data(self):
        """测试 observation 包含 raw_data"""
        mock_llm = create_mock_llm([
            '{"thought": "读取文件", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "已读取", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "success": True, 
                "data": {"content": "重要数据内容", "lines": 100}, 
                "summary": "读取成功"
            }
            
            events = []
            async for event in agent.run_stream("读取文件"):
                events.append(event)
            
            action_events = [e for e in events if e["type"] == "action_tool"]
            obs_events = [e for e in events if e["type"] == "observation"]
            
            assert len(action_events) > 0
            assert "raw_data" in action_events[0]
            assert action_events[0]["raw_data"]["content"] == "重要数据内容"
            
            assert len(obs_events) > 0
            assert "obs_raw_data" in obs_events[0]
            assert obs_events[0]["obs_raw_data"]["content"] == "重要数据内容"


class TestAgentStatus:
    """测试 Agent 状态"""
    
    @pytest.mark.asyncio
    async def test_status_thinking_during_thought(self):
        """测试 thought 阶段状态为 THINKING"""
        mock_llm = create_mock_llm([
            '{"thought": "思考", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        status_history = []
        async for event in agent.run_stream("测试"):
            status_history.append(agent.status)
        
        assert AgentStatus.THINKING in status_history
    
    @pytest.mark.asyncio
    async def test_status_executing_during_action(self):
        """测试 action 阶段状态为 EXECUTING"""
        mock_llm = create_mock_llm([
            '{"thought": "执行", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "完成", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "成功"}
            
            status_history = []
            async for event in agent.run_stream("测试"):
                status_history.append(agent.status)
            
            assert AgentStatus.EXECUTING in status_history
    
    @pytest.mark.asyncio
    async def test_status_observing_during_observation(self):
        """测试 observation 阶段状态为 OBSERVING"""
        mock_llm = create_mock_llm([
            '{"thought": "执行", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "观察", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "成功"}
            
            status_history = []
            async for event in agent.run_stream("测试"):
                status_history.append(agent.status)
            
            assert AgentStatus.OBSERVING in status_history


class TestLLMCallCounter:
    """测试 LLM 调用计数"""
    
    @pytest.mark.asyncio
    async def test_llm_call_count_increases(self):
        """测试 LLM 调用计数增加"""
        mock_llm = create_mock_llm([
            '{"thought": "执行", "action_tool": "read_file", "params": {"path": "test.txt"}}',
            '{"thought": "完成", "action_tool": "finish", "params": {"result": "done"}}'
        ])
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        with patch.object(agent.executor, 'execute', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"success": True, "data": {"content": "内容"}, "summary": "成功"}
            
            assert agent.llm_call_count == 0
            
            async for event in agent.run_stream("测试"):
                pass
            
            assert agent.llm_call_count > 0


class TestInheritanceStructure:
    """测试继承结构"""
    
    def test_intent_agent_inherits_base_agent(self):
        """测试 IntentAgent 继承 BaseAgent"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools)
        )
        
        assert isinstance(agent, BaseAgent)
    
    def test_run_stream_from_base_class(self):
        """测试使用父类的 run_stream 方法"""
        mock_llm = AsyncMock(return_value='{"thought": "完成", "action_tool": "finish", "params": {"result": "done"}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools),
            max_steps=5
        )
        
        assert hasattr(BaseAgent, 'run_stream')
        assert hasattr(agent, 'run_stream')
        assert agent.run_stream.__qualname__.startswith('BaseAgent')


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_import_intent_agent(self):
        """测试可以导入 IntentAgent"""
        from app.services.agent import IntentAgent
        assert IntentAgent is not None
    
    def test_agent_class_name(self):
        """测试 Agent 类名"""
        mock_llm = AsyncMock(return_value='{"thought": "test", "action_tool": "finish", "params": {}}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-session",
            file_tools=MagicMock(spec=FileTools)
        )
        
        assert agent.__class__.__name__ == "IntentReactAgent"
