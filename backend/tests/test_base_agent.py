"""
BaseAgent 测试 - 小沈

测试通用Agent基类的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.services.agent.base import BaseAgent
from app.services.agent.types import Step, AgentResult, AgentStatus


class ConcreteAgent(BaseAgent):
    """测试用的具体Agent实现"""
    
    def __init__(self, max_steps=20, use_function_calling=False):
        super().__init__(max_steps=max_steps, use_function_calling=use_function_calling)
        self.executor = MagicMock()
    
    async def _get_llm_response_text(self, message, history_dicts):
        """模拟LLM响应"""
        return '{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'
    
    async def _get_llm_response_with_tools(self, message, history_dicts):
        """模拟LLM响应（Function Calling模式）"""
        return '{"thought": "test", "action_tool": "finish", "params": {"result": "done"}}'
    
    async def _execute_tool(self, action, action_input):
        """模拟工具执行"""
        return {"status": "success", "data": {"result": "ok"}}


class TestBaseAgentInitialization:
    """测试BaseAgent初始化"""
    
    def test_agent_initialization_default(self):
        """测试默认初始化"""
        agent = ConcreteAgent()
        assert agent.max_steps == 20
        assert agent.use_function_calling == False
        assert agent.status == AgentStatus.IDLE
        assert agent.llm_call_count == 0
        assert agent.steps == []
        assert agent.conversation_history == []
    
    def test_agent_initialization_custom(self):
        """测试自定义参数初始化"""
        agent = ConcreteAgent(max_steps=50, use_function_calling=True)
        assert agent.max_steps == 50
        assert agent.use_function_calling == True
    
    def test_agent_has_parser(self):
        """测试Agent有parser属性"""
        agent = ConcreteAgent()
        assert agent.parser is not None
    
    def test_agent_has_lock(self):
        """测试Agent有锁属性（并发安全）"""
        agent = ConcreteAgent()
        assert agent._lock is not None


class TestBaseAgentRun:
    """测试BaseAgent运行功能"""
    
    @pytest.mark.asyncio
    async def test_agent_run_success(self):
        """测试Agent运行成功"""
        agent = ConcreteAgent()
        result = await agent.run_with_tools("test task")
        
        assert result.success == True
        assert result.message == "Task completed successfully"
        assert result.total_steps == 1
        assert len(result.steps) == 1
    
    @pytest.mark.asyncio
    async def test_agent_run_with_context(self):
        """测试Agent带上下文运行"""
        agent = ConcreteAgent()
        result = await agent.run_with_tools(
            "test task",
            context={"key": "value"}
        )
        
        assert result.success == True
        # 检查对话历史包含上下文
        assert any("key" in str(msg) for msg in agent.conversation_history)
    
    @pytest.mark.asyncio
    async def test_agent_run_with_system_prompt(self):
        """测试Agent带系统提示运行"""
        agent = ConcreteAgent()
        result = await agent.run_with_tools(
            "test task",
            system_prompt="You are a helpful assistant"
        )
        
        assert result.success == True
        # 检查对话历史包含系统提示
        assert agent.conversation_history[0]["role"] == "system"
        assert "helpful assistant" in agent.conversation_history[0]["content"]
    
    @pytest.mark.asyncio
    async def test_agent_llm_call_counter(self):
        """测试LLM调用计数器"""
        agent = ConcreteAgent()
        await agent.run_with_tools("test task")
        
        # 至少调用一次LLM
        assert agent.llm_call_count >= 1


class TestBaseAgentMaxSteps:
    """测试BaseAgent最大步数限制"""
    
    @pytest.mark.asyncio
    async def test_agent_max_steps_exceeded(self):
        """测试超过最大步数"""
        class NeverFinishAgent(ConcreteAgent):
            async def _get_llm_response_text(self, message, history_dicts):
                # 永远不返回finish
                return '{"thought": "thinking", "action_tool": "test", "params": {}}'
            
            async def _execute_tool(self, action, action_input):
                return {"status": "success", "data": {}}
        
        agent = NeverFinishAgent(max_steps=3)
        result = await agent.run_with_tools("test task")
        
        assert result.success == False
        assert "Exceeded maximum steps" in result.message
        assert result.total_steps == 3
    
    @pytest.mark.asyncio
    async def test_agent_max_steps_exact(self):
        """测试刚好达到最大步数"""
        class FinishOnStep3Agent(ConcreteAgent):
            def __init__(self, max_steps=20, use_function_calling=False):
                super().__init__(max_steps=max_steps, use_function_calling=use_function_calling)
                self.step_count = 0
            
            async def _get_llm_response_text(self, message, history_dicts):
                self.step_count += 1
                if self.step_count >= 3:
                    return '{"thought": "done", "action_tool": "finish", "params": {"result": "completed"}}'
                return '{"thought": "thinking", "action_tool": "test", "params": {}}'
            
            async def _execute_tool(self, action, action_input):
                return {"status": "success", "data": {}}
        
        agent = FinishOnStep3Agent(max_steps=10)
        result = await agent.run_with_tools("test task")
        
        assert result.success == True
        assert result.total_steps == 3


class TestBaseAgentErrorHandling:
    """测试BaseAgent错误处理"""
    
    @pytest.mark.asyncio
    async def test_agent_llm_parse_error(self):
        """测试LLM响应解析错误"""
        class ParseErrorAgent(ConcreteAgent):
            async def _get_llm_response_text(self, message, history_dicts):
                return "invalid json"
        
        agent = ParseErrorAgent(max_steps=3)
        result = await agent.run_with_tools("test task")
        
        # 应该继续运行，而不是崩溃
        assert result.success == False
    
    @pytest.mark.asyncio
    async def test_agent_tool_execution_error(self):
        """测试工具执行错误"""
        class ToolErrorAgent(ConcreteAgent):
            def __init__(self, max_steps=20, use_function_calling=False):
                super().__init__(max_steps=max_steps, use_function_calling=use_function_calling)
                self.call_count = 0
            
            async def _get_llm_response_text(self, message, history_dicts):
                self.call_count += 1
                if self.call_count == 1:
                    # 第一次调用，执行工具
                    return '{"thought": "test", "action_tool": "test", "params": {}}'
                else:
                    # 第二次调用，结束
                    return '{"thought": "done", "action_tool": "finish", "params": {"result": "done"}}'
            
            async def _execute_tool(self, action, action_input):
                return {"status": "error", "summary": "Tool failed"}
        
        agent = ToolErrorAgent(max_steps=2)
        result = await agent.run_with_tools("test task")
        
        # 应该成功，因为最后finish了
        assert result.success == True
        # 检查步骤中有错误
        assert len(result.steps) >= 1
        # 第一个步骤应该是工具执行
        assert result.steps[0].action == "test"


class TestBaseAgentStatus:
    """测试BaseAgent状态管理"""
    
    @pytest.mark.asyncio
    async def test_agent_status_transitions(self):
        """测试Agent状态转换"""
        agent = ConcreteAgent()
        
        # 初始状态
        assert agent.status == AgentStatus.IDLE
        
        # 运行后状态应该是COMPLETED
        await agent.run_with_tools("test task")
        assert agent.status == AgentStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_agent_status_on_failure(self):
        """测试Agent失败状态"""
        class NeverFinishAgent(ConcreteAgent):
            async def _get_llm_response_text(self, message, history_dicts):
                return '{"thought": "thinking", "action_tool": "test", "params": {}}'
            
            async def _execute_tool(self, action, action_input):
                return {"status": "success", "data": {}}
        
        agent = NeverFinishAgent(max_steps=1)
        await agent.run_with_tools("test task")
        
        assert agent.status == AgentStatus.FAILED


class TestBaseAgentConversationHistory:
    """测试BaseAgent对话历史管理"""
    
    @pytest.mark.asyncio
    async def test_conversation_history_format(self):
        """测试对话历史格式"""
        agent = ConcreteAgent()
        await agent.run_with_tools("test task")
        
        # 检查对话历史格式
        for msg in agent.conversation_history:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["system", "user", "assistant"]
    
    @pytest.mark.asyncio
    async def test_conversation_history_includes_user_message(self):
        """测试对话历史包含用户消息"""
        agent = ConcreteAgent()
        await agent.run_with_tools("test task")
        
        # 检查用户消息
        user_msgs = [msg for msg in agent.conversation_history if msg["role"] == "user"]
        assert len(user_msgs) >= 1
        assert any("test task" in msg["content"] for msg in user_msgs)


class TestBaseAgentUtilityMethods:
    """测试BaseAgent工具方法"""
    
    def test_format_observation_success(self):
        """测试格式化成功观察结果"""
        agent = ConcreteAgent()
        observation = {"status": "success", "data": {"result": "ok"}}
        formatted = agent._format_observation(observation)
        
        assert "result" in formatted
    
    def test_format_observation_error(self):
        """测试格式化错误观察结果"""
        agent = ConcreteAgent()
        observation = {"status": "error", "summary": "Failed"}
        formatted = agent._format_observation(observation)
        
        assert "Error" in formatted
        assert "Failed" in formatted
    
    def test_get_execution_log(self):
        """测试获取执行日志"""
        agent = ConcreteAgent()
        agent.steps = [
            Step(step_number=1, thought="test", action="test", action_input={})
        ]
        
        log = agent.get_execution_log()
        assert len(log) == 1
        assert log[0]["step_number"] == 1
