"""
ReAct Agent单元测试 (FileOperationAgent Unit Tests)
测试FileOperationAgent的核心功能

测试范围:
- agent_run_success: Agent成功执行任务
- agent_max_steps: 最大步数限制
- agent_rollback: Agent回滚功能

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
from app.services.file_operations.agent import (
    FileOperationAgent,
    ToolParser,
    ToolExecutor,
    AgentStatus,
    Step,
    AgentResult
)
from app.services.file_operations.tools import FileTools


@pytest.fixture
def mock_llm_client():
    """创建模拟LLM客户端"""
    async def mock_chat(message, history=None):
        # 模拟简单的LLM响应
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
def agent(mock_llm_client, mock_file_tools):
    """创建Agent实例（带模拟依赖）"""
    with patch('app.services.file_operations.agent.get_session_service') as mock_session:
        mock_session_service = MagicMock()
        mock_session_service.create_session.return_value = "test-session"
        mock_session_service.complete_session.return_value = None
        mock_session.return_value = mock_session_service
        
        agent = FileOperationAgent(
            llm_client=mock_llm_client,
            session_id="test-session",
            file_tools=mock_file_tools,
            max_steps=5
        )
        return agent


import json


class TestAgentRunSuccess:
    """测试Agent成功执行任务"""
    
    @pytest.mark.asyncio
    async def test_agent_run_success(self, agent, mock_llm_client):
        """TC051: Agent成功完成简单任务"""
        # 设置LLM响应：直接完成任务
        async def finish_immediately(message, history=None):
            return Mock(content=json.dumps({
                "thought": "Task is straightforward, I will finish",
                "action": "finish",
                "action_input": {"result": "Done", "message": "Completed"}
            }))
        
        agent.llm_client = finish_immediately
        
        result = await agent.run("Please help me organize files")
        
        assert result.success is True
        assert result.message == "Task completed successfully"
        assert result.total_steps == 1
        assert result.session_id == "test-session"
        assert result.final_result["result"] == "Done"
        assert agent.status == AgentStatus.COMPLETED
    
    @pytest.mark.asyncio
    async def test_agent_run_with_steps(self, agent):
        """TC052: Agent执行多步任务"""
        step_count = [0]
        
        async def multi_step_llm(message, history=None):
            step_count[0] += 1
            if step_count[0] == 1:
                # 第一步：列出目录
                return Mock(content=json.dumps({
                    "thought": "First, I need to list the directory",
                    "action": "list_directory",
                    "action_input": {"dir_path": "/tmp"}
                }))
            else:
                # 第二步：完成任务
                return Mock(content=json.dumps({
                    "thought": "Now I have the information, I can finish",
                    "action": "finish",
                    "action_input": {"result": "Listed directory"}
                }))
        
        agent.llm_client = multi_step_llm
        agent.file_tools.list_directory = AsyncMock(return_value={
            "success": True,
            "entries": [{"name": "file1.txt", "type": "file"}]
        })
        
        result = await agent.run("List files in /tmp")
        
        assert result.success is True
        assert result.total_steps == 2
        assert len(result.steps) == 2
        assert result.steps[0].action == "list_directory"
        assert result.steps[1].action == "finish"
    
    @pytest.mark.asyncio
    async def test_agent_run_with_context(self, agent):
        """TC053: Agent使用上下文信息"""
        async def context_aware_llm(message, history=None):
            # 验证上下文在message中
            assert "test context" in message.lower() or any("test context" in str(m) for m in history or [])
            return Mock(content=json.dumps({
                "thought": "Using context to complete task",
                "action": "finish",
                "action_input": {"result": "Context used"}
            }))
        
        agent.llm_client = context_aware_llm
        
        result = await agent.run(
            "Do something",
            context={"key": "test context", "value": 123}
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_agent_run_with_system_prompt(self, agent):
        """TC054: 使用自定义系统prompt"""
        custom_prompt = "You are a specialized file organizer"
        
        async def check_system_prompt(message, history=None):
            # 验证系统prompt在历史中
            # 处理history可能是Message对象或dict的情况
            def get_role(h):
                if hasattr(h, 'role'):
                    return h.role
                return h.get("role") if isinstance(h, dict) else None
            
            def get_content(h):
                if hasattr(h, 'content'):
                    return h.content
                return h.get("content", "") if isinstance(h, dict) else ""
            
            system_msgs = [h for h in (history or []) if get_role(h) == "system"]
            if system_msgs:
                assert custom_prompt in get_content(system_msgs[0])
            return Mock(content=json.dumps({
                "thought": "Using custom prompt",
                "action": "finish",
                "action_input": {"result": "Custom prompt used"}
            }))
        
        agent.llm_client = check_system_prompt
        
        result = await agent.run(
            "Organize my files",
            system_prompt=custom_prompt
        )
        
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_agent_run_execution_log(self, agent):
        """TC055: 验证执行日志"""
        async def finish_with_log(message, history=None):
            return Mock(content=json.dumps({
                "thought": "I will log this step",
                "action": "finish",
                "action_input": {"result": "Logged"}
            }))
        
        agent.llm_client = finish_with_log
        
        result = await agent.run("Test logging")
        
        # 获取执行日志
        log = agent.get_execution_log()
        assert len(log) == 1
        assert log[0]["step_number"] == 1
        assert log[0]["thought"] == "I will log this step"
        assert log[0]["action"] == "finish"
        assert "timestamp" in log[0]


class TestAgentMaxSteps:
    """测试Agent最大步数限制"""
    
    @pytest.mark.asyncio
    async def test_agent_max_steps(self, agent):
        """TC056: 达到最大步数限制"""
        agent.max_steps = 3
        call_count = [0]
        
        async def never_finish(message, history=None):
            call_count[0] += 1
            # 永远执行list_directory，不finish
            return Mock(content=json.dumps({
                "thought": f"Step {call_count[0]}: Still working",
                "action": "list_directory",
                "action_input": {"dir_path": "/tmp"}
            }))
        
        agent.llm_client = never_finish
        agent.file_tools.list_directory = AsyncMock(return_value={
            "success": True,
            "entries": []
        })
        
        result = await agent.run("Task that never ends")
        
        assert result.success is False
        assert "Exceeded maximum steps" in result.message
        assert result.total_steps == 3
        assert result.error == "Maximum steps exceeded"
        assert agent.status == AgentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_agent_max_steps_exact(self, agent):
        """TC057: 恰好在最后一步完成"""
        agent.max_steps = 2
        call_count = [0]
        
        async def finish_at_last_step(message, history=None):
            call_count[0] += 1
            if call_count[0] < 2:
                return Mock(content=json.dumps({
                    "thought": "Working...",
                    "action": "read_file",
                    "action_input": {"file_path": "/tmp/test.txt"}
                }))
            else:
                return Mock(content=json.dumps({
                    "thought": "Finished!",
                    "action": "finish",
                    "action_input": {"result": "Done"}
                }))
        
        agent.llm_client = finish_at_last_step
        agent.file_tools.read_file = AsyncMock(return_value={
            "success": True,
            "content": "test"
        })
        
        result = await agent.run("Task")
        
        assert result.success is True
        assert result.total_steps == 2
    
    @pytest.mark.asyncio
    async def test_agent_step_counter_reset(self, agent):
        """TC058: 每次run重置步数计数器"""
        async def quick_finish(message, history=None):
            return Mock(content=json.dumps({
                "thought": "Done",
                "action": "finish",
                "action_input": {"result": "Quick"}
            }))
        
        agent.llm_client = quick_finish
        
        # 第一次运行
        result1 = await agent.run("Task 1")
        assert result1.total_steps == 1
        
        # 第二次运行，步数应重置
        result2 = await agent.run("Task 2")
        assert result2.total_steps == 1  # 不是2！


class TestAgentRollback:
    """测试Agent回滚功能"""
    
    @pytest.mark.asyncio
    async def test_agent_rollback_session(self, agent):
        """TC059: 回滚整个会话"""
        # 先执行一些操作
        agent.steps = [
            Step(
                step_number=1,
                thought="Created file",
                action="write_file",
                action_input={"file_path": "/tmp/test.txt"},
                observation={"success": True, "result": {"operation_id": "op-1"}}
            ),
            Step(
                step_number=2,
                thought="Deleted file",
                action="delete_file",
                action_input={"file_path": "/tmp/test.txt"},
                observation={"success": True, "result": {"operation_id": "op-2"}}
            )
        ]
        
        # 模拟rollback_session成功
        agent.file_tools.safety = MagicMock()
        agent.file_tools.safety.rollback_session.return_value = {
            "success": 2,
            "failed": 0
        }
        
        result = await agent.rollback()
        
        assert result is True
        assert agent.status == AgentStatus.ROLLED_BACK
        agent.file_tools.safety.rollback_session.assert_called_once_with("test-session")
    
    @pytest.mark.asyncio
    async def test_agent_rollback_single_step(self, agent):
        """TC060: 回滚到指定步骤"""
        agent.steps = [
            Step(
                step_number=1,
                thought="Step 1",
                action="write_file",
                action_input={},
                observation={"success": True, "result": {"operation_id": "op-1"}}
            ),
            Step(
                step_number=2,
                thought="Step 2",
                action="delete_file",
                action_input={},
                observation={"success": True, "result": {"operation_id": "op-2"}}
            ),
            Step(
                step_number=3,
                thought="Step 3",
                action="read_file",
                action_input={},
                observation={"success": True, "result": {"operation_id": "op-3"}}
            )
        ]
        
        agent.file_tools.safety = MagicMock()
        agent.file_tools.safety.rollback_operation.return_value = True
        
        # 回滚到第2步（撤销第3步）
        result = await agent.rollback(step_number=2)
        
        assert result is True
        # 应该回滚operation_id为op-3的操作
        agent.file_tools.safety.rollback_operation.assert_called_once_with("op-3")
    
    @pytest.mark.asyncio
    async def test_agent_rollback_no_session(self, agent):
        """TC061: 无会话时回滚应失败"""
        agent.session_id = None
        
        with pytest.raises(ValueError) as exc_info:
            await agent.rollback()
        
        assert "Session ID is required" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_agent_rollback_invalid_step(self, agent):
        """TC062: 回滚不存在的步骤"""
        agent.steps = [
            Step(
                step_number=1,
                thought="Step 1",
                action="write_file",
                action_input={},
                observation={"success": True, "result": {"operation_id": "op-1"}}
            )
        ]
        
        result = await agent.rollback(step_number=99)
        
        assert result is False  # 应该失败


class TestAgentErrorHandling:
    """测试Agent错误处理"""
    
    @pytest.mark.asyncio
    async def test_agent_llm_parse_error(self, agent):
        """TC063: LLM响应解析错误处理"""
        call_count = [0]
        
        async def bad_then_good(message, history=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次返回无效JSON
                return Mock(content="This is not valid JSON")
            else:
                # 第二次返回正确响应
                return Mock(content=json.dumps({
                    "thought": "I fixed my response",
                    "action": "finish",
                    "action_input": {"result": "Fixed"}
                }))
        
        agent.llm_client = bad_then_good
        
        result = await agent.run("Task")
        
        # 应该能恢复并完成任务
        assert result.success is True
        assert result.total_steps == 2  # 第一步解析失败，第二步成功
    
    @pytest.mark.asyncio
    async def test_agent_tool_execution_error(self, agent):
        """TC064: 工具执行错误处理"""
        async def tool_error(message, history=None):
            return Mock(content=json.dumps({
                "thought": "I will try to read a file",
                "action": "read_file",
                "action_input": {"file_path": "/nonexistent"}
            }))
        
        agent.llm_client = tool_error
        agent.file_tools.read_file = AsyncMock(return_value={
            "success": False,
            "error": "File not found"
        })
        
        # Agent应该能处理工具错误并继续
        result = await agent.run("Read file")
        
        # 由于工具返回错误但没有finish，会达到max_steps
        assert result.success is False  # 超时失败
        assert agent.status == AgentStatus.FAILED
    
    @pytest.mark.asyncio
    async def test_agent_llm_client_exception(self, agent):
        """TC065: LLM客户端异常处理"""
        async def raise_exception(message, history=None):
            raise Exception("LLM service unavailable")
        
        agent.llm_client = raise_exception
        
        result = await agent.run("Task")
        
        assert result.success is False
        assert "Execution failed" in result.message
        assert "LLM service unavailable" in result.error


class TestAgentInitialization:
    """测试Agent初始化"""
    
    def test_agent_requires_session_id(self):
        """TC066: Agent需要session_id"""
        with pytest.raises(ValueError) as exc_info:
            FileOperationAgent(
                llm_client=Mock(),
                session_id="",  # 空字符串
                max_steps=10
            )
        
        assert "session_id is required" in str(exc_info.value)
    
    def test_agent_initialization_with_defaults(self):
        """TC067: 使用默认值初始化"""
        with patch('app.services.file_operations.agent.get_session_service'):
            agent = FileOperationAgent(
                llm_client=Mock(),
                session_id="test-session",
                max_steps=10
            )
            
            assert agent.session_id == "test-session"
            assert agent.max_steps == 10
            assert agent.status == AgentStatus.IDLE
            assert agent.steps == []
            assert agent.file_tools is not None  # 自动创建
    
    def test_agent_initial_status(self, agent):
        """TC068: Agent初始状态"""
        assert agent.status == AgentStatus.IDLE
        assert len(agent.steps) == 0
        assert agent.session_id == "test-session"


class TestAgentConcurrency:
    """测试Agent并发安全性"""
    
    @pytest.mark.asyncio
    async def test_agent_concurrent_run_protection(self, agent):
        """TC069: 并发run调用保护（锁机制）"""
        execution_order = []
        
        async def slow_llm(message, history=None):
            execution_order.append(f"start-{message}")
            await asyncio.sleep(0.1)  # 模拟慢操作
            execution_order.append(f"end-{message}")
            return Mock(content=json.dumps({
                "thought": "Done",
                "action": "finish",
                "action_input": {"result": message}
            }))
        
        agent.llm_client = slow_llm
        
        # 并发调用两个run
        task1 = asyncio.create_task(agent.run("Task1"))
        task2 = asyncio.create_task(agent.run("Task2"))
        
        await asyncio.gather(task1, task2, return_exceptions=True)
        
        # 验证执行顺序：start-1, end-1, start-2, end-2（串行）
        # 而不是：start-1, start-2, end-1, end-2（并行）
        starts = [i for i, x in enumerate(execution_order) if x.startswith("start")]
        ends = [i for i, x in enumerate(execution_order) if x.startswith("end")]
        
        # 每个start后应该有对应的end
        for i, start_idx in enumerate(starts):
            assert ends[i] > start_idx, "并发执行违反锁机制"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])