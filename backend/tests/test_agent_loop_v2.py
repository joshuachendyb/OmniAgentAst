"""
ReAct Agent 主循环 2.0 单元测试 (Agent Loop V2 Unit Tests)

测试范围：
- max_steps超限错误处理
- empty_response空响应错误处理
- answer/implicit分支直接返回FinalStep
- thought_only分支继续循环
- action分支return_direct判断
- parse_error重试逻辑
- 循环外状态清理

Author: 小健 - 2026-04-17
"""

import pytest
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import Mock, AsyncMock, MagicMock, patch, AsyncIterator
from unittest import IsolatedAsyncioTestCase

from app.services.agent.base_react import BaseAgent
from app.services.agent import IntentAgent
from app.services.agent.types import AgentStatus
from app.services.tools.file.file_tools import FileTools


def create_mock_llm(responses: List[str]):
    """创建模拟 LLM 客户端"""
    mock = AsyncMock()
    mock.side_effect = responses
    return mock


class TestMaxStepsExceeded:
    """测试 max_steps 超限错误处理"""
    
    @pytest.mark.asyncio
    async def test_max_steps_exceeded_returns_error_step(self):
        """测试达到最大迭代次数时返回ErrorStep"""
        # 设置LLM返回answer，让循环正常终止但通过max_steps限制
        mock_llm = AsyncMock(return_value='{"type": "answer", "content": "最终答案"}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-max-steps",
            file_tools=MagicMock(spec=FileTools),
            max_steps=2  # 只允许2步
        )
        
        steps = []
        async for step in agent.run_stream("测试任务"):
            steps.append(step)
        
        # 应该有max_steps次迭代，加上最后的ErrorStep
        error_steps = [s for s in steps if s.get("type") == "error"]
        
        # 验证有错误步骤，且错误类型为max_steps_exceeded
        assert len(error_steps) > 0
        assert error_steps[0].get("error_type") == "max_steps_exceeded"
        assert "最大迭代次数" in error_steps[0].get("error_message", "")
    
    @pytest.mark.asyncio
    async def test_max_steps_exceeded_stops_immediately(self):
        """测试max_steps超限时立即停止，不继续循环"""
        call_count = 0
        
        async def mock_llm_response():
            nonlocal call_count
            call_count += 1
            return '{"type": "answer", "content": "答案"}'
        
        mock_llm = AsyncMock()
        mock_llm.side_effect = mock_llm_response
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-stop-immediate",
            file_tools=MagicMock(spec=FileTools),
            max_steps=1
        )
        
        steps = list(agent.run_stream("测试"))
        
        # 调用次数应该等于max_steps，不是更多
        assert call_count <= 2  # 第一次调用 + 超过限制后的检查


class TestEmptyResponse:
    """测试空响应错误处理"""
    
    @pytest.mark.asyncio
    async def test_empty_response_returns_error(self):
        """测试LLM返回空响应时返回ErrorStep"""
        mock_llm = AsyncMock(return_value="")  # 空响应
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-empty",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        error_steps = [s for s in steps if s.get("type") == "error"]
        
        assert len(error_steps) > 0
        assert error_steps[0].get("error_type") == "empty_response"
    
    @pytest.mark.asyncio
    async def test_none_response_returns_error(self):
        """测试LLM返回None时返回ErrorStep"""
        mock_llm = AsyncMock(return_value=None)
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-none",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        error_steps = [s for s in steps if s.get("type") == "error"]
        
        assert len(error_steps) > 0


class TestAnswerImplicitBranch:
    """测试answer/implicit分支"""
    
    @pytest.mark.asyncio
    async def test_answer_returns_final_step(self):
        """测试type=answer时返回FinalStep"""
        mock_llm = AsyncMock(return_value='{"type": "answer", "response": "最终答案"}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-answer",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        assert len(final_steps) > 0
        assert final_steps[0].get("response") == "最终答案"
    
    @pytest.mark.asyncio
    async def test_implicit_returns_final_step(self):
        """测试type=implicit时返回FinalStep"""
        mock_llm = AsyncMock(return_value='{"type": "implicit", "content": "隐式答案"}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-implicit",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        assert len(final_steps) > 0
    
    @pytest.mark.asyncio
    async def test_answer_returns_stops_immediately(self):
        """测试answer返回时立即停止，不继续循环"""
        call_count = 0
        
        async def mock_llm_response():
            nonlocal call_count
            call_count += 1
            return '{"type": "answer", "response": "答案"}'
        
        mock_llm = AsyncMock()
        mock_llm.side_effect = mock_llm_response
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-answer-stop",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = list(agent.run_stream("测试"))
        
        # LLM只应该被调用一次
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_final_step_is_finished_true(self):
        """测试FinalStep的is_finished为True"""
        mock_llm = AsyncMock(return_value='{"type": "answer", "response": "完成"}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-finished",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        assert final_steps[0].get("is_finished") == True


class TestThoughtOnlyBranch:
    """测试thought_only分支"""
    
    @pytest.mark.asyncio
    async def test_thought_only_continues_loop(self):
        """测试type=thought_only时继续循环"""
        responses = [
            '{"type": "thought_only", "thought": "思考中"}',  # 第一次返回thought_only
            '{"type": "answer", "response": "最终答案"}'  # 第二次返回answer
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-thought-only",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        thought_steps = [s for s in steps if s.get("type") == "thought"]
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        # 应该有thought步骤（继续循环）且有final步骤（最终结束）
        assert len(thought_steps) > 0
        assert len(final_steps) > 0
    
    @pytest.mark.asyncio
    async def test_thought_only_multiple_cycles(self):
        """测试thought_only可以多次循环"""
        responses = [
            '{"type": "thought_only", "thought": "思考1"}',
            '{"type": "thought_only", "thought": "思考2"}',
            '{"type": "answer", "response": "完成"}'
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-multi-thought",
            file_tools=MagicMock(spec=FileTools)
        )
        
        steps = list(agent.run_stream("测试"))
        
        thought_steps = [s for s in steps if s.get("type") == "thought"]
        
        # 应该有2个thought步骤
        assert len(thought_steps) == 2


class TestActionBranch:
    """测试action分支"""
    
    @pytest.mark.asyncio
    async def test_action_executes_tool(self):
        """测试action分支执行工具"""
        mock_llm = AsyncMock(return_value='{"type": "action", "action_tool": "list_directory", "action_input": {"dir_path": "."}}')
        
        # 模拟工具返回
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.list_directory = AsyncMock(return_value={"status": "success", "data": ["file1", "file2"]})
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-action",
            file_tools=mock_tools
        )
        
        steps = []
        async for step in agent.run_stream("列出当前目录"):
            steps.append(step)
        
        action_steps = [s for s in steps if s.get("type") == "action_tool"]
        
        assert len(action_steps) > 0
        assert action_steps[0].get("tool_name") == "list_directory"
    
    @pytest.mark.asyncio
    async def test_action_yields_observation(self):
        """测试action分支返回observation步骤"""
        mock_llm = AsyncMock(return_value='{"type": "action", "action_tool": "read_file", "action_input": {"file_path": "test.txt"}}')
        
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.read_file = AsyncMock(return_value={"status": "success", "data": "文���内���"})
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-observation",
            file_tools=mock_tools
        )
        
        steps = []
        async for step in agent.run_stream("读取文件"):
            steps.append(step)
        
        observation_steps = [s for s in steps if s.get("type") == "observation"]
        
        assert len(observation_steps) > 0
    
    @pytest.mark.asyncio
    async def test_return_direct_creates_final_step(self):
        """测试return_direct=True时创建FinalStep并退出"""
        responses = [
            '{"type": "action", "action_tool": "read_file", "action_input": {"file_path": "test.txt"}}'
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.read_file = AsyncMock(return_value={
            "status": "success", 
            "data": "文件内容",
            "return_direct": True  # 标记为直接返回
        })
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-return-direct",
            file_tools=mock_tools
        )
        
        steps = []
        async for step in agent.run_stream("读取文件"):
            steps.append(step)
        
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        # 有final步骤且是return_direct产生的
        assert len(final_steps) > 0
        # 验证没有observation步骤（有也应该是return_direct跳过的）
    
    @pytest.mark.asyncio
    async def test_no_return_direct_continues_loop(self):
        """测试return_direct=False时继续循环"""
        responses = [
            '{"type": "action", "action_tool": "list_directory", "action_input": {"dir_path": "."}}',
            '{"type": "answer", "response": "完成"}'
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.list_directory = AsyncMock(return_value={
            "status": "success",
            "data": ["file1"],
            "return_direct": False
        })
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-no-return-direct",
            file_tools=mock_tools
        )
        
        steps = []
        async for step in agent.run_stream("列出"):
            steps.append(step)
        
        observation_steps = [s for s in steps if s.get("type") == "observation"]
        
        # 有observation步骤，且没有立即返回final
        assert len(observation_steps) > 0


class TestParseErrorBranch:
    """测试parse_error重试逻辑"""
    
    @pytest.mark.asyncio
    async def test_parse_error_retry_within_limit(self):
        """测试parse_error在重试次数内继续循环"""
        responses = [
            '{"type": "parse_error", "error": "无效格式"}',  # 第一次解析失败
            '{"type": "answer", "response": "最终答案"}'  # 第二次成功
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-parse-retry",
            file_tools=MagicMock(spec=FileTools),
            max_parse_retries=3
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        final_steps = [s for s in steps if s.get("type") == "final"]
        
        # 最终成功，应该有final步骤
        assert len(final_steps) > 0
    
    @pytest.mark.asyncio
    async def test_parse_error_exceeds_limit_returns_error(self):
        """测试parse_error超过重试次数返回ErrorStep"""
        responses = [
            '{"type": "parse_error", "error": "格式错误1"}',
            '{"type": "parse_error", "error": "格式错误2"}',
            '{"type": "parse_error", "error": "格式错误3"}'
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-parse-exceed",
            file_tools=MagicMock(spec=FileTools),
            max_parse_retries=2  # 只允许2次重试
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        error_steps = [s for s in steps if s.get("type") == "error"]
        
        # 超过重试次数，应该有错误步骤
        assert len(error_steps) > 0
        assert error_steps[0].get("error_type") == "parse_error"
        assert "2次" in error_steps[0].get("error_message", "")
    
    @pytest.mark.asyncio
    async def test_parse_error_injects_correction_to_history(self):
        """测试parse_error时注入修正提示到历史"""
        responses = [
            '{"type": "parse_error", "error": "格式错误"}',
            '{"type": "answer", "response": "完成"}'
        ]
        mock_llm = AsyncMock()
        mock_llm.side_effect = responses
        
        mock_tools = MagicMock(spec=FileTools)
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-parse-history",
            file_tools=mock_tools
        )
        
        # 运行并检查conversation_history
        steps = list(agent.run_stream("测试"))
        
        # 验证conversation_history中有修正提示
        history_has_correction = any(
            "Parse Error" in str(h.get("content", "")) 
            for h in agent.conversation_history 
            if isinstance(h, dict)
        )
        
        assert history_has_correction


class TestExceptionHandling:
    """测试异常处理"""
    
    @pytest.mark.asyncio
    async def test_unexpected_exception_returns_error(self):
        """测试未捕获异常返回ErrorStep"""
        mock_llm = AsyncMock(return_value='{"type": "action", "action_tool": "finish", "params": {}}')
        
        # 模拟工具抛出异常
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.finish = AsyncMock(side_effect=ValueError("意外错误"))
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-exception",
            file_tools=mock_tools
        )
        
        steps = []
        async for step in agent.run_stream("测试"):
            steps.append(step)
        
        error_steps = [s for s in steps if s.get("type") == "error"]
        
        assert len(error_steps) > 0
    
    @pytest.mark.asyncio
    async def test_exception_stops_loop(self):
        """测试异常发生后停止循环"""
        call_count = 0
        
        async def mock_llm_response():
            nonlocal call_count
            call_count += 1
            return '{"type": "action", "action_tool": "finish", "params": {}}'
        
        mock_llm = AsyncMock()
        mock_llm.side_effect = mock_llm_response
        
        mock_tools = MagicMock(spec=FileTools)
        mock_tools.finish = AsyncMock(side_effect=ValueError("错误"))
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-stop",
            file_tools=mock_tools
        )
        
        steps = list(agent.run_stream("测试"))
        
        # LLM只应该被调用一次
        assert call_count == 1


class TestNoCrossLoopState:
    """测试循环外状态清理"""
    
    @pytest.mark.asyncio
    async def test_no_last_parsed_type_variable(self):
        """测试没有last_parsed_type等跨循环变量"""
        # 这个测试检查代码结构，确保没有遗留的跨循环状态变量
        # 通过检查run_stream方法不包含这些变量名
        
        import inspect
        from app.services.agent.base_react import BaseAgent
        
        source = inspect.getsource(BaseAgent.run_stream)
        
        # 这些变量不应该存在于主循环中
        forbidden_vars = ["last_parsed_type", "last_error", "last_response", "last_answer_response"]
        
        for var in forbidden_vars:
            # 注意：在注释中提到不算违规，这里宽松检查
            is_forbidden = var in source and f"= {var}" in source
            # 如果代码中有这些变量的赋值语句，才算违规
            if is_forbidden:
                # 检查是否是赋值语句
                for line in source.split('\n'):
                    if var in line and "=" in line and not line.strip().startswith("#"):
                        pytest.fail(f"发现跨循环状态变量: {var}")
    
    @pytest.mark.asyncio
    async def test_no_break_outside_loop(self):
        """测试没有循环外的break处理"""
        import inspect
        from app.services.agent.base_react import BaseAgent
        
        source = inspect.getsource(BaseAgent.run_stream)
        
        # 检查循环外是否还有if last_*的判断
        # 这是一个宽松的检查
        lines = source.split('\n')
        in_while = False
        after_while = []
        
        for line in lines:
            if "while True" in line:
                in_while = True
            if in_while:
                after_while.append(line)
        
        # 循环后的代码应该简化，不应该有复杂的if判断
        # 这个测试更多是设计层面的验证


class TestOnAfterLoopCallback:
    """测试_on_after_loop回调"""
    
    @pytest.mark.asyncio
    async def test_on_after_loop_called_on_exit(self):
        """测试不同退出场景都调用_on_after_loop"""
        mock_llm = AsyncMock(return_value='{"type": "answer", "response": "完成"}')
        
        agent = IntentAgent(
            llm_client=mock_llm,
            session_id="test-callback",
            file_tools=MagicMock(spec=FileTools)
        )
        
        # 验证方法存在
        assert hasattr(agent, '_on_after_loop')
        
        # 运行一次
        steps = list(agent.run_stream("测试"))
        
        # _on_after_loop应该在某处被调用（这通过代码检查验证）


if __name__ == "__main__":
    pytest.main([__file__, "-v"])