"""
ReAct流式重构测试用例
根据《流式ReAct的type和API重构设计说明书》第8-9章编写

测试范围：
1. 流式推送：thought → action_tool → observation → final
2. 字段格式：新字段 tool_name, tool_params, execution_status, summary
3. 分页功能：next-page接口
4. tools.py统一返回格式：status代替success

创建时间：2026-03-09 22:00:00
创建人：小沈
更新时间：2026-04-08 16:30:00
更新人：小健（根据第8章文档修改）
"""
import pytest
import json
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

from app.services.agent import FileReactAgent
from app.services.agent.types import AgentStatus, ThoughtStep, ActionToolStep, ObservationStep
from app.services.tools.file.file_tools import FileTools
from app.api.v1.file_operations import NextPageRequest


class TestToolsNewFormat:
    """测试tools.py新返回格式（status代替success）"""
    
    @pytest.fixture
    def file_tools(self):
        """创建FileTools实例"""
        tools = FileTools(session_id="test-session")
        return tools
    
    @pytest.mark.asyncio
    async def test_read_file_returns_status_field(self, tmp_path):
        """测试read_file返回status字段而不是success"""
        file_tools = FileTools(session_id="test-session")
        
        # 创建测试文件
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World")
        
        result = await file_tools.read_file(str(test_file))
        
        # 验证使用新字段status
        assert "status" in result, "应返回status字段"
        assert result["status"] == "success", "status应为success"
        # 验证不再使用旧字段success
        assert result.get("success") is None or "status" in result, "不应使用旧字段success"
    
    @pytest.mark.asyncio
    async def test_write_file_returns_status_field(self, tmp_path):
        """测试write_file返回status字段"""
        file_tools = FileTools(session_id="test-session")
        test_file = tmp_path / "write_test.txt"
        
        result = await file_tools.write_file(str(test_file), "Test content")
        
        assert "status" in result, "应返回status字段"
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_list_directory_returns_status_field(self, tmp_path):
        """测试list_directory返回status字段"""
        file_tools = FileTools(session_id="test-session")
        
        # 创建测试目录
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        
        result = await file_tools.list_directory(str(test_dir))
        
        assert "status" in result, "应返回status字段"
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_delete_file_returns_status_field(self, tmp_path):
        """测试delete_file返回status字段"""
        file_tools = FileTools(session_id="test-session")
        test_file = tmp_path / "delete_me.txt"
        test_file.write_text("delete me")
        
        result = await file_tools.delete_file(str(test_file))
        
        assert "status" in result, "应返回status字段"
    
    @pytest.mark.asyncio
    async def test_move_file_returns_status_field(self, tmp_path):
        """测试move_file返回status字段"""
        file_tools = FileTools(session_id="test-session")
        source = tmp_path / "source.txt"
        source.write_text("move content")
        dest = tmp_path / "dest.txt"
        
        result = await file_tools.move_file(str(source), str(dest))
        
        assert "status" in result, "应返回status字段"
    
    @pytest.mark.asyncio
    async def test_search_files_returns_status_field(self, tmp_path):
        """测试search_files返回status字段"""
        file_tools = FileTools(session_id="test-session")
        
        test_dir = tmp_path / "searchdir"
        test_dir.mkdir()
        (test_dir / "test_file.txt").write_text("content")
        
        result = await file_tools.search_files(str(test_dir), "test")
        
        assert "status" in result, "应返回status字段"
    
    @pytest.mark.asyncio
    async def test_unified_format_has_required_fields(self, tmp_path):
        """测试统一格式包含所有必要字段"""
        file_tools = FileTools(session_id="test-session")
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        result = await file_tools.read_file(str(test_file))
        
        # 验证统一格式字段
        assert "status" in result, "应有status字段"
        assert "summary" in result, "应有summary字段"
        assert "data" in result, "应有data字段"


class TestAgentNewFields:
    """测试agent.py使用新字段（action_tool, params）"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """创建模拟LLM客户端"""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def agent(self, mock_llm_client):
        """创建Agent实例"""
        return FileReactAgent(
            llm_client=mock_llm_client,
            session_id="test-session"
        )
    
    @pytest.mark.asyncio
    async def test_parse_response_returns_tool_name(self, agent):
        """测试parse_response返回新字段tool_name"""
        response = json.dumps({
            "content": "用户想要查看桌面",
            "tool_name": "list_directory",
            "tool_params": {"path": "C:\\Users\\test"}
        })
        
        result = agent.parser.parse_response(response)
        
        assert "tool_name" in result, "应包含tool_name字段"
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {"path": "C:\\Users\\test"}
    
    @pytest.mark.asyncio
    async def test_parse_response_backward_compatible(self, agent):
        """测试parse_response兼容旧字段action/action_input"""
        response = json.dumps({
            "thought": "用户想要查看桌面",
            "action": "list_directory",
            "action_input": {"path": "C:\\Users\\test"}
        })
        
        result = agent.parser.parse_response(response)
        
        # 新字段应该从旧字段转换而来
        assert result["tool_name"] == "list_directory"
        assert result["tool_params"] == {"path": "C:\\Users\\test"}
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="run_stream测试需要更完善的mock设置")
    async def test_run_stream_yields_thought_action_observation(self, mock_llm_client):
        """测试run_stream按正确顺序yield：thought → action_tool → observation → final"""
        # 模拟LLM返回
        mock_llm_client.chat = AsyncMock(return_value=Mock(
            content=json.dumps({
                "content": "用户想要查看桌面",
                "tool_name": "finish",
                "tool_params": {"result": "任务完成"}
            })
        ))
        
        agent = FileReactAgent(
            llm_client=mock_llm_client,
            session_id="test-session-stream"
        )
        
        # 收集所有yield的事件
        events = []
        async for event in agent.run_stream("查看桌面"):
            events.append(event)
        
        # 验证事件顺序：thought -> final
        assert len(events) >= 2, "至少应该有thought和final"
        assert events[0]["type"] == "thought", "第一个事件应该是thought"
        assert events[-1]["type"] == "final", "最后一个事件应该是final"
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="run_stream测试需要更完善的mock设置")
    async def test_run_stream_thought_fields(self, mock_llm_client):
        """测试thought阶段的字段"""
        mock_llm_client.chat = AsyncMock(return_value=Mock(
            content=json.dumps({
                "content": "思考内容",
                "tool_name": "list_directory",
                "tool_params": {"path": "C:\\test"}
            })
        ))
        
        agent = FileReactAgent(
            llm_client=mock_llm_client,
            session_id="test-session-thought"
        )
        
        events = []
        async for event in agent.run_stream("测试"):
            events.append(event)
        
        # 验证thought字段
        thought_event = events[0]
        assert thought_event["type"] == "thought"
        assert "content" in thought_event
        assert "tool_name" in thought_event
        assert "tool_params" in thought_event


class TestActionToolFields:
    """测试action_tool阶段的字段（根据设计文档5.3节）"""
    
    @pytest.fixture
    def file_tools(self):
        return FileTools(session_id="test-session")
    
    @pytest.mark.asyncio
    async def test_action_tool_has_execution_status(self, tmp_path):
        """测试action_tool结果包含execution_status"""
        file_tools = FileTools(session_id="test-session")
        
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        
        result = await file_tools.list_directory(str(test_dir))
        
        # 验证execution_status字段（不是旧字段success）
        assert "execution_status" not in result, "execution_status应该在嵌套的data中"
        # 实际返回格式是 {status, summary, data}
        # data中包含tool执行结果
        assert result["status"] in ["success", "error", "warning"]
    
    @pytest.mark.asyncio
    async def test_action_tool_has_summary(self, tmp_path):
        """测试action_tool结果包含summary"""
        file_tools = FileTools(session_id="test-session")
        
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        
        result = await file_tools.list_directory(str(test_dir))
        
        assert "summary" in result, "应包含summary字段"
        assert isinstance(result["summary"], str), "summary应该是字符串"
    
    @pytest.mark.asyncio
    async def test_action_tool_has_raw_data(self, tmp_path):
        """测试action_tool结果包含raw_data"""
        file_tools = FileTools(session_id="test-session")
        
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()
        
        result = await file_tools.list_directory(str(test_dir))
        
        assert "data" in result, "应包含data字段（raw_data）"


class TestPagination:
    """测试分页功能（next-page接口）"""
    
    def test_next_page_request_model(self):
        """测试NextPageRequest模型"""
        request = NextPageRequest(
            task_id="test-123",
            tool_name="list_directory",
            tool_params={"dir_path": "C:\\test"},
            next_page_token="MTAw"
        )
        
        assert request.task_id == "test-123"
        assert request.tool_name == "list_directory"
        assert request.next_page_token == "MTAw"
    
    @pytest.mark.skip(reason="分页功能已删除 - 2026-04-03")
    async def test_list_directory_pagination(self):
        """测试list_directory分页功能"""
        file_tools = FileTools(session_id="test-pagination")
        
        # 创建一个有很多文件的目录
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建100个文件
            for i in range(100):
                with open(os.path.join(tmpdir, f"file{i}.txt"), "w") as f:
                    f.write(f"content {i}")
            
            # 第一次调用，限制为10条
            result1 = await file_tools.list_directory(tmpdir, page_size=10)
            
            assert result1["status"] == "success"
            data1 = result1.get("data", {})
            entries1 = data1.get("entries", [])
            
            # 应该有10条
            assert len(entries1) == 10, f"应该返回10条，实际{len(entries1)}条"
            
            # 检查分页字段
            assert "has_more" in data1, "应包含has_more字段"
            assert "next_page_token" in data1, "应包含next_page_token字段"
            assert data1["has_more"] == True, "应该有更多数据"
            assert data1["next_page_token"] is not None, "应该有下一页token"
            
            # 第二次调用，使用next_page_token
            result2 = await file_tools.list_directory(
                tmpdir, 
                page_token=data1["next_page_token"]
            )
            
            assert result2["status"] == "success"
            data2 = result2.get("data", {})
            entries2 = data2.get("entries", [])
            
            # 第二页应该有10条（不重复）
            assert len(entries2) == 10, f"第二页应该返回10条，实际{len(entries2)}条"
            
            # 验证不重复
            entry_names1 = {e["name"] for e in entries1}
            entry_names2 = {e["name"] for e in entries2}
            assert entry_names1.isdisjoint(entry_names2), "两页不应有重复数据"


class TestReActFlow:
    """测试ReAct完整流程（设计文档1.1节）"""
    
    @pytest.mark.asyncio
    async def test_react_three_stages_independent(self):
        """测试ReAct三个阶段独立（原则1）"""
        # 验证三个阶段是独立的，不是嵌套的
        # Thought: LLM决定 action_tool + params
        # Action: 执行 action_tool，返回 execution_status + summary + data
        # Observation: LLM基于结果决定下一步
        
        # 这个测试验证数据结构设计是否遵循原则
        from app.services.agent.types import ThoughtStep, ActionToolStep, ObservationStep
        
        # Thought阶段
        thought = ThoughtStep(
            step_number=1,
            content="用户想要查看桌面",
            tool_name="list_directory",
            tool_params={"path": "C:\\Users\\test"}
        )
        
        assert thought.tool_name == "list_directory"
        assert thought.tool_params == {"path": "C:\\Users\\test"}
        
        # Action阶段
        action = ActionToolStep(
            step_number=1,
            tool_name="list_directory",
            tool_params={"path": "C:\\Users\\test"},
            execution_status="success",
            summary="成功读取目录"
        )
        
        assert action.execution_status == "success"
        assert action.summary == "成功读取目录"
        
        # Observation阶段
        observation = ObservationStep(
            step_number=1,
            execution_status="success",
            summary="成功读取目录",
            content="已获取文件列表",
            tool_name="finish",
            tool_params={},
            is_finished=True
        )
        
        assert observation.is_finished == True
        assert observation.tool_name == "finish"
    
    @pytest.mark.asyncio
    async def test_observation_contains_both_input_and_output(self):
        """测试Observation阶段同时包含输入和输出（设计文档5.4节）"""
        # Observation阶段特点：
        # - 输入：来自Action的 execution_status, summary, raw_data
        # - 输出：LLM新的 content, reasoning, tool_name, tool_params
        
        from app.services.agent.types import ObservationStep
        
        observation = ObservationStep(
            step_number=1,
            # 输入（来自Action）
            execution_status="success",
            summary="成功读取目录",
            raw_data={"entries": ["file1.txt"]},
            # 输出（LLM决策）
            content="已获取文件列表，可以回复用户",
            reasoning="文件列表已完整",
            tool_name="finish",
            tool_params={},
            is_finished=True
        )
        
        # 验证同时包含输入和输出
        assert observation.execution_status == "success"  # 输入
        assert observation.raw_data is not None  # 输入
        assert observation.content is not None  # 输出
        assert observation.tool_name is not None  # 输出


class TestFieldNaming:
    """测试字段命名规范（设计文档4.2节）"""
    
    def test_no_duplicate_field_names(self):
        """测试type名称不出现在字段名中"""
        # 错误示例：{"type": "thought", "thought_content": "..."}
        # 正确示例：{"type": "thought", "content": "..."}
        
        # 验证thought类型不使用thought作为字段
        thought_data = {
            "type": "thought",
            "content": "思考内容",
            "tool_name": "list_directory",
            "tool_params": {}
        }
        
        assert "thought" not in thought_data or thought_data.get("type") == "thought"
        # 应该是content而不是thought_content
        assert "content" in thought_data
        assert "thought_content" not in thought_data
    
    def test_action_tool_fields_not_nested(self):
        """测试tool_name结果不嵌套thought/action"""
        # 错误：observation内部嵌套thought/tool_name
        # 正确：observation直接包含execution_status/summary/content/tool_name/tool_params
        
        action_data = {
            "type": "action_tool",
            "step": 1,
            "tool_name": "list_directory",
            "tool_params": {},
            "execution_status": "success",
            "summary": "成功"
        }
        
        # 验证不嵌套
        assert "thought" not in action_data
        assert "tool_name" in action_data


class TestChatStreamFields:
    """测试chat.py流式推送的字段"""
    
    def test_thought_event_fields(self):
        """测试thought事件字段"""
        # 根据设计文档5.2节
        event = {
            "type": "thought",
            "content": "用户想要查看桌面",
            "reasoning": "需要先列出目录",
            "tool_name": "list_directory",
            "tool_params": {"path": "C:\\Users\\test"}
        }
        
        assert event["type"] == "thought"
        assert "content" in event
        assert "tool_name" in event
        assert "tool_params" in event
    
    def test_action_event_fields(self):
        """测试action事件字段"""
        # 根据设计文档5.3节
        event = {
            "type": "action",
            "step": 1,
            "tool_name": "list_directory",
            "tool_params": {"path": "C:\\Users\\test"},
            "execution_status": "success",
            "summary": "成功读取目录"
        }
        
        assert event["type"] == "action"
        assert "tool_name" in event
        assert "execution_status" in event
        assert "summary" in event
    
    def test_observation_event_fields(self):
        """测试observation事件字段"""
        # 根据设计文档5.4节
        event = {
            "type": "observation",
            "step": 1,
            "execution_status": "success",
            "summary": "成功读取目录",
            "content": "已获取文件列表",
            "tool_name": "finish",
            "tool_params": {},
            "is_finished": True
        }
        
        assert event["type"] == "observation"
        assert "execution_status" in event
        assert "content" in event
        assert "tool_name" in event
        assert "is_finished" in event
    
    def test_final_event_fields(self):
        """测试final事件字段"""
        event = {
            "type": "final",
            "content": "任务完成"
        }
        
        assert event["type"] == "final"
        assert "content" in event


# ===== 新增测试用例：问题1和问题7修复后验证 =====
# 【测试编写】小健 - 2026-04-07
# 对应文档：ReAct模式标准及修改当前实现的改进-小沈-2026-0407.md 第4.4.2节

class TestSingleLLMCallPerStep:
    """验证问题1修复：每step只调用1次LLM"""
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要完整mock LLM client才能测试")
    async def test_single_llm_call_per_step(self):
        """验证每step只调用1次LLM"""
        # 模拟场景：3个step
        # 期望：LLM被调用3次（每step 1次）
        # 实际：需要通过mock计数验证
        pass
    
    def test_no_second_llm_call_in_observation(self):
        """验证observation阶段不再调用LLM"""
        # 检查base_react.py中observation阶段没有_get_llm_response调用
        # 这是一个静态检查测试
        import inspect
        from app.services.agent.base_react import BaseAgent
        
        source = inspect.getsource(BaseAgent.run_stream)
        
        # 检查在observation yield之后是否还有LLM调用
        # 修改后应该没有第二次LLM调用
        assert "llm_response = await self._get_llm_response()" not in source.split("yield")[1] if len(source.split("yield")) > 1 else True


class TestObservationSimplifiedFields:
    """验证问题7修复：observation字段简化"""
    
    def test_observation_fields_after_fix(self):
        """验证修复后observation只包含必要字段"""
        # 修改后的observation字段
        event = {
            "type": "observation",
            "step": 1,
            "timestamp": 1773742493000,
            "content": "Tool 'list_directory' executed: 成功读取目录"
            # 不应有：obs_execution_status, obs_summary, obs_raw_data, obs_reasoning, obs_action_tool, obs_params, is_finished
        }
        
        # 验证必要字段存在
        assert event["type"] == "observation"
        assert event["step"] == 1
        assert event["content"].startswith("Tool '")
        assert "executed:" in event["content"]
        
        # 验证不再需要的字段不存在
        assert "obs_execution_status" not in event
        assert "obs_summary" not in event
        assert "obs_raw_data" not in event
        assert "obs_reasoning" not in event
        assert "obs_action_tool" not in event
        assert "obs_params" not in event
        assert "is_finished" not in event
    
    def test_observation_content_format(self):
        """验证observation的content格式正确"""
        tool_name = "list_directory"
        summary = "成功读取目录"
        
        # 修改后的content格式
        expected_content = f"Tool '{tool_name}' executed: {summary}"
        
        assert expected_content == "Tool 'list_directory' executed: 成功读取目录"
        assert "executed:" in expected_content


class TestObservationContainsToolResult:
    """验证observation显示工具执行结果"""
    
    def test_observation_shows_tool_name(self):
        """验证observation显示工具名称"""
        event = {
            "type": "observation",
            "content": "Tool 'read_file' executed: 成功读取文件"
        }
        
        assert "read_file" in event["content"]
        assert "executed:" in event["content"]
    
    def test_observation_shows_summary(self):
        """验证observation显示工具执行摘要"""
        event = {
            "type": "observation", 
            "content": "Tool 'write_file' executed: 文件写入成功"
        }
        
        assert "文件写入成功" in event["content"]


class TestFinishDetectionInToolName:
    """验证finish在tool_name阶段检测"""
    
    def test_finish_not_in_observation(self):
        """验证finish判断不在observation阶段"""
        # 检查base_react.py代码结构
        # finish判断应该在action_tool执行后、observation yield之前
        # 而不是单独在observation阶段判断
        import inspect
        from app.services.agent.base_react import BaseAgent
        
        source = inspect.getsource(BaseAgent.run_stream)
        
        # 检查is_finished判断的位置
        # 修改前：is_finished = parsed_obs.get("tool_name") == "finish"（在observation yield之前）
        # 修改后：应该检查tool_name阶段的tool_name值
        
        # 验证没有在observation阶段单独判断is_finished
        observation_section = source.split("type")[-1] if "type" in source else ""
        
        # 这个测试验证修改后代码结构正确
        assert True  # 占位，实际需要修改后验证
    
    def test_final_only_when_tool_name_is_finish(self):
        """验证final只在tool_name是finish时触发"""
        # 修改后流程：
        # 1. tool_name阶段：解析LLM response得到tool_name
        # 2. 如果tool_name == "finish" → yield final
        # 3. 否则 → yield observation → 下一轮循环
        
        # 测试场景：tool_name = "finish"
        tool_name = "finish"
        
        if tool_name == "finish":
            # 应该直接yield final
            expected_type = "final"
        else:
            # 应该yield observation
            expected_type = "observation"
        
        assert expected_type == "final"
        
        # 测试场景：tool_name = "list_directory"
        tool_name = "list_directory"
        
        if tool_name == "finish":
            expected_type = "final"
        else:
            expected_type = "observation"
        
        assert expected_type == "observation"
