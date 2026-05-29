"""
测试并行工具调用完整链路 - 小沈 2026-05-14
"""
import pytest
import json
import sys
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agent.llm_strategies import ToolsStrategy
from app.services.agent.llm_response_parser import parse_react_response
sys.path.insert(0, r'G:\OmniAgentAs-desk\backend')

from app.services.agent.steps import StepFactory


class TestStepFactoryParallel:
    """验证StepFactory方法签名正确"""

    def test_create_observation_step_signature(self):
        """验证create_observation_step接受的参数"""
        step = StepFactory.create_observation_step(
            step=1, tool_name="search_web",
            tool_params={"query": "test"},
            execution_result={"status": "success", "summary": "找到结果"},
            return_direct=False
        )
        assert step is not None
        assert step.get_type() == "observation"

    def test_create_action_tool_step_signature(self):
        """验证create_action_tool_step接受的参数"""
        step = StepFactory.create_action_tool_step(
            step=1, tool_name="search_web",
            tool_params={"query": "test"},
            execution_result={"status": "success", "summary": "找到结果"},
            execution_time_ms=100
        )
        assert step is not None
        assert step.get_type() == "action_tool"


class TestPendingCallsFormatting:
    """验证_format_tool_calls 正确生成_pending_calls"""

    def test_single_call_no_pending(self):
        ts = ToolsStrategy([])
        tool_calls = [{
            "id": "call_1", "type": "function",
            "function": {"name": "search_web", "arguments": '{"query": "test"}'}
        }]
        result = ts._format_tool_calls(tool_calls)
        d = json.loads(result)
        assert d["tool_name"] == "search_web"
        assert "_pending_calls" not in d

    def test_multi_call_has_pending(self):
        ts = ToolsStrategy([])
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "search_web", "arguments": '{"query": "a"}'}},
            {"id": "call_2", "type": "function", "function": {"name": "search_web", "arguments": '{"query": "b"}'}},
        ]
        result = ts._format_tool_calls(tool_calls)
        d = json.loads(result)
        assert d["tool_name"] == "search_web"
        assert "_pending_calls" in d
        assert len(d["_pending_calls"]) == 1
        assert d["_pending_calls"][0]["args"]["query"] == "b"

    def test_three_calls_pending(self):
        ts = ToolsStrategy([])
        tool_calls = [
            {"id": "c1", "type": "function", "function": {"name": "a", "arguments": '{}'}},
            {"id": "c2", "type": "function", "function": {"name": "b", "arguments": '{}'}},
            {"id": "c3", "type": "function", "function": {"name": "c", "arguments": '{}'}},
        ]
        result = ts._format_tool_calls(tool_calls)
        d = json.loads(result)
        assert len(d["_pending_calls"]) == 2
        assert d["_pending_calls"][0]["name"] == "b"
        assert d["_pending_calls"][1]["name"] == "c"


class TestPendingCallsParsing:
    """验证parse_react_response透传_pending_calls"""

    def test_tool_name_path_preserves_pending(self):
        data = json.dumps({
            "tool_name": "search_web",
            "tool_params": {"query": "a"},
            "thought": "testing",
            "_pending_calls": [{"name": "search_web", "args": {"query": "b"}}]
        })
        result = parse_react_response(data)
        assert result["tool_name"] == "search_web"
        assert "_pending_calls" in result
        assert len(result["_pending_calls"]) == 1

    def test_no_pending_doesnt_add(self):
        data = json.dumps({
            "tool_name": "search_web",
            "tool_params": {"query": "a"},
        })
        result = parse_react_response(data)
        assert "_pending_calls" not in result


class TestAgentPendingExecution:
    """模拟agent循环中_pending_calls的执行"""

    @pytest.mark.asyncio
    async def test_pending_calls_are_executed(self):
        """验证并行工具被正确执行"""
        from app.services.agent.base_react import BaseAgent
        from app.services.agent.steps import StepFactory

        executed_tools = []

        # 创建一个最小agent模拟pending执行
        class MockAgent(BaseAgent):
            def __init__(self):
                super().__init__(llm_client=None, task_id="test")
                self.steps = []
                self.conversation_history = []
                self.temp_history = []

            async def _get_llm_response(self): return ""
            async def _execute_tool(self, action, params):
                result = {"status": "success", "summary": f"{action}完成"}
                if action == "search_web":
                    result["data"] = {"results": [{"title": "r1"}]}
                return result
            def _get_system_prompt(self): return ""
            def _get_task_prompt(self, task, ctx=None): return task

        agent = MockAgent()

        # 模拟parsed结果（有_pending_calls）
        parsed = {
            "type": "action",
            "tool_name": "search_web",
            "tool_params": {"query": "a"},
            "content": "testing",
            "reasoning": "",
            "_pending_calls": [
                {"name": "search_web", "args": {"query": "b"}},
                {"name": "fetch_webpage", "args": {"url": "http://test.com"}}
            ]
        }

        # 模拟观察阶段后的pending执行（跟base_react.py第914行一致）
        step_count = 1
        pending_calls = parsed.get("_pending_calls", [])
        for pending in pending_calls:
            p_name = pending.get("name", "finish")
            p_params = pending.get("args", {})
            p_result = await agent._execute_tool(p_name, p_params)

            p_result_dict = {
                "status": p_result.get("status", "success"),
                "summary": p_result.get("summary", ""),
                "data": p_result.get("data"),
                "error": p_result.get("error", ""),
            }

            # 创建action_tool step
            try:
                p_action_step = StepFactory.create_action_tool_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=p_result_dict, execution_time_ms=100
                )
                agent.steps.append(p_action_step)
                assert p_action_step.get_type() == "action_tool"
                executed_tools.append(("action", p_name))
            except TypeError as e:
                pytest.fail(f"create_action_tool_step 参数错误: {e}")

            # 创建observation step（这是之前bug的位置）
            try:
                p_obs_step = StepFactory.create_observation_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=p_result_dict, return_direct=False
                )
                agent.steps.append(p_obs_step)
                assert p_obs_step.get_type() == "observation"
                executed_tools.append(("obs", p_name))
            except TypeError as e:
                pytest.fail(f"create_observation_step 参数错误: {e}")

            # 加入history
            agent.conversation_history.append({
                "role": "system",
                "content": f"Observation: success - {p_result.get('summary', '')}"
            })

        # 验证所有工具都被执行
        assert len(executed_tools) == 4  # 2 tools * (action + obs) = 4
        assert executed_tools[0] == ("action", "search_web")
        assert executed_tools[2] == ("action", "fetch_webpage")

    @pytest.mark.asyncio
    async def test_pending_with_real_steps(self):
        """用真实的StepFactory创建步骤，验证完整的step列表"""
        from app.services.agent.steps import StepFactory

        step_count = 2
        steps = []

        # 模拟主工具的observation（已经完成）
        # 现在执行并行工具
        pending = [
            {"name": "search_web", "args": {"query": "b"}},
            {"name": "search_web", "args": {"query": "c"}},
        ]

        for p in pending:
            p_name = p["name"]
            p_params = p["args"]
            mock_result = {
                "status": "success",
                "summary": f"找到结果",
                "data": {"results": [{"title": "r1"}]},
            }

            action = StepFactory.create_action_tool_step(
                step=step_count, tool_name=p_name, tool_params=p_params,
                execution_result=mock_result, execution_time_ms=50
            )
            steps.append(action)

            obs = StepFactory.create_observation_step(
                step=step_count, tool_name=p_name, tool_params=p_params,
                execution_result=mock_result, return_direct=False
            )
            steps.append(obs)

        assert len(steps) == 4
        assert steps[0].get_type() == "action_tool"
        assert steps[0].tool_name == "search_web"
        assert steps[1].get_type() == "observation"
        assert steps[2].get_type() == "action_tool"
        assert steps[3].get_type() == "observation"
        # 所有step使用相同的step_count
        assert steps[0].step == steps[1].step == steps[2].step == steps[3].step == 2
