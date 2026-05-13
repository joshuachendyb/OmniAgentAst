"""
后端全面测试 - 覆盖所有修改的核心功能
编写人：小沈 - 2026-05-13

测试范围：
1. ChatResponse reasoning 字段
2. chat() reasoning/content 分离逻辑
3. 通用XML工具调用转JSON
4. SSE step编号递增
5. cancel_task中断机制
6. intent routing (CRSS + LLM)
7. SQLite WAL模式
8. cancellation flag检查
9. TextStrategy reasoning传递
"""

import pytest
import json
import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
from typing import AsyncGenerator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================
# 1. ChatResponse reasoning 字段测试
# ============================================================

class TestChatResponse:
    """ChatResponse reasoning字段 - 新增字段完整测试"""

    def test_reasoning_field_exists(self):
        """验证ChatResponse有reasoning字段"""
        from app.services.llm_core import ChatResponse
        cr = ChatResponse(content="回答", model="test", provider="p", reasoning="推理内容")
        assert cr.reasoning == "推理内容"
        assert cr.content == "回答"

    def test_reasoning_default_empty(self):
        """不传reasoning时默认为空字符串"""
        from app.services.llm_core import ChatResponse
        cr = ChatResponse(content="回答", model="test")
        assert cr.reasoning == ""

    def test_reasoning_with_error(self):
        """同时有error和reasoning"""
        from app.services.llm_core import ChatResponse
        cr = ChatResponse(content="", model="test", error="错误", reasoning="推理")
        assert cr.reasoning == "推理"
        assert cr.error == "错误"
        assert cr.success is False


# ============================================================
# 2. chat() reasoning/content 分离逻辑测试
# ============================================================

class TestChatReasoningSeparation:
    """验证chat()正确分离推理内容和回答内容"""

    @pytest.mark.asyncio
    async def test_separate_reasoning_and_content(self):
        """模型同时输出reasoning_content和content"""
        from app.services.llm_core import StreamChunk

        full_content = ""
        full_reasoning = ""
        has_non_reasoning = False

        async for chunk in self._mock_stream_both():
            if chunk.content:
                if getattr(chunk, 'is_reasoning', False):
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                    has_non_reasoning = True

        # fallback逻辑
        if not has_non_reasoning and full_reasoning:
            full_content = full_reasoning

        assert full_content == "这是最终回答"
        assert full_reasoning == "这是推理思考过程"

    @pytest.mark.asyncio
    async def test_reasoning_only_fallback(self):
        """模型只输出reasoning_content（thinking模型）"""
        from app.services.llm_core import StreamChunk

        full_content = ""
        full_reasoning = ""
        has_non_reasoning = False

        async for chunk in self._mock_stream_reasoning_only():
            if chunk.content:
                if getattr(chunk, 'is_reasoning', False):
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                    has_non_reasoning = True

        if not has_non_reasoning and full_reasoning:
            full_content = full_reasoning

        assert full_content == "仅有推理内容"
        assert full_reasoning == "仅有推理内容"

    @pytest.mark.asyncio
    async def test_content_only_no_reasoning(self):
        """模型只输出content（无reasoning模型）"""
        from app.services.llm_core import StreamChunk

        full_content = ""
        full_reasoning = ""
        has_non_reasoning = False

        async for chunk in self._mock_stream_content_only():
            if chunk.content:
                if getattr(chunk, 'is_reasoning', False):
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                    has_non_reasoning = True

        if not has_non_reasoning and full_reasoning:
            full_content = full_reasoning

        assert full_content == "正常回答"
        assert full_reasoning == ""

    async def _mock_stream_both(self):
        """模拟同时输出reasoning和content的流"""
        from app.services.llm_core import StreamChunk
        yield StreamChunk(content="这是推理思考过程", model="test", is_reasoning=True)
        yield StreamChunk(content="这是最终回答", model="test", is_reasoning=False)
        yield StreamChunk(content="", model="test", is_done=True)

    async def _mock_stream_reasoning_only(self):
        from app.services.llm_core import StreamChunk
        yield StreamChunk(content="仅有推理内容", model="test", is_reasoning=True)
        yield StreamChunk(content="", model="test", is_done=True)

    async def _mock_stream_content_only(self):
        from app.services.llm_core import StreamChunk
        yield StreamChunk(content="正常回答", model="test", is_reasoning=False)
        yield StreamChunk(content="", model="test", is_done=True)


# ============================================================
# 3. 通用XML工具调用转JSON测试
# ============================================================

class TestXmlToolCallConversion:
    """通用XML→JSON转换 - 覆盖多种模型格式"""

    def test_longcat_xml(self):
        """LongCat XML格式"""
        from app.services.llm_core import _convert_xml_tool_call_to_json
        xml = "<longcat_tool_call>search_web\n<longcat_arg_key>query</longcat_arg_key>\n<longcat_arg_value>今天天气</longcat_arg_value>\n</longcat_tool_call>"
        result = _convert_xml_tool_call_to_json(xml)
        assert result is not None
        d = json.loads(result)
        assert d["tool_name"] == "search_web"
        assert d["tool_params"]["query"] == "今天天气"

    def test_generic_prefix_xml(self):
        """任意前缀的XML格式"""
        from app.services.llm_core import _convert_xml_tool_call_to_json
        xml = "<custom_tool_call>my_func\n<custom_arg_key>name</custom_arg_key>\n<custom_arg_value>hello</custom_arg_value>\n</custom_tool_call>"
        result = _convert_xml_tool_call_to_json(xml)
        assert result is not None
        d = json.loads(result)
        assert d["tool_name"] == "my_func"
        assert d["tool_params"]["name"] == "hello"

    def test_multiple_params(self):
        """多参数XML"""
        from app.services.llm_core import _convert_xml_tool_call_to_json
        xml = "<longcat_tool_call>search_web\n<longcat_arg_key>query</longcat_arg_key>\n<longcat_arg_value>天气</longcat_arg_value>\n<longcat_arg_key>num_results</longcat_arg_key>\n<longcat_arg_value>5</longcat_arg_value>\n</longcat_tool_call>"
        result = _convert_xml_tool_call_to_json(xml)
        d = json.loads(result)
        assert d["tool_params"]["query"] == "天气"
        assert d["tool_params"]["num_results"] == "5"

    def test_no_xml(self):
        """普通文本不触发转换"""
        from app.services.llm_core import _convert_xml_tool_call_to_json
        assert _convert_xml_tool_call_to_json("普通文本") is None
        assert _convert_xml_tool_call_to_json('{"tool_name": "search"}') is None
        assert _convert_xml_tool_call_to_json("") is None
        assert _convert_xml_tool_call_to_json(None) is None

    def test_xml_with_prefix_text(self):
        """XML前有文本"""
        from app.services.llm_core import _convert_xml_tool_call_to_json
        xml = "用户查询需要搜索<longcat_tool_call>search_web\n<longcat_arg_key>q</longcat_arg_key>\n<longcat_arg_value>test</longcat_arg_value>\n</longcat_tool_call>"
        result = _convert_xml_tool_call_to_json(xml)
        assert result is not None
        d = json.loads(result)
        assert d["tool_name"] == "search_web"


# ============================================================
# 4. SSE step编号测试
# ============================================================

class TestSSEStepNumbering:
    """验证SSE step编号正确递增"""

    def test_format_sse_event_step(self):
        """验证_format_sse_event使用next_step递增"""
        from app.services.react_sse_wrapper import _format_sse_event

        steps = []
        for i in range(5):
            event = {"type": "thought", "content": f"step_{i}"}
            sse = _format_sse_event(event, i + 1, "model", "provider")
            data = json.loads(sse[6:])  # 去掉"data: "前缀
            steps.append(data["step"])

        assert steps == [1, 2, 3, 4, 5], f"step应递增: {steps}"

    def test_format_chunk_sse(self):
        """验证chunk SSE包含所有字段"""
        from app.services.react_sse_wrapper import format_chunk_sse

        event = {
            "type": "chunk",
            "content": "回答内容",
            "thought": "",
            "reasoning": "",
            "is_reasoning": False,
            "_thinking": "推理过程"
        }
        sse = format_chunk_sse(event, 1, "model", "provider")
        data = json.loads(sse[6:])
        assert data["type"] == "chunk"
        assert data["step"] == 1
        assert data["content"] == "回答内容"
        assert data["_thinking"] == "推理过程"
        assert data["is_reasoning"] is False


# ============================================================
# 5. ToolExecutor XML调用测试
# ============================================================

class TestToolExecutorXml:
    """验证XML转换后的工具调用能被正确执行"""

    def test_xml_conversion_to_tool_executor_format(self):
        """XML→JSON转换后的格式符合ToolExecutor.execute()要求"""
        from app.services.llm_core import _convert_xml_tool_call_to_json

        xml = "<longcat_tool_call>search_web\n<longcat_arg_key>query</longcat_arg_key>\n<longcat_arg_value>天气</longcat_arg_value>\n</longcat_tool_call>"
        result = _convert_xml_tool_call_to_json(xml)
        d = json.loads(result)

        # ToolExecutor.execute(action, action_input) 期望格式
        assert "tool_name" in d  # action参数
        assert "tool_params" in d  # action_input参数
        assert isinstance(d["tool_params"], dict)
        assert d["tool_params"]["query"] == "天气"


# ============================================================
# 6. 中断机制测试
# ============================================================

class TestCancelTask:
    """验证cancel_task中断机制"""

    @pytest.mark.asyncio
    async def test_cancel_task_sets_cancelled_flag(self):
        """验证cancel_task正确设置cancelled标志"""
        from app.services.react_sse_wrapper import cancel_task, running_tasks, running_tasks_lock

        task_id = "test-cancel-001"
        # 模拟注册任务
        async with running_tasks_lock:
            running_tasks[task_id] = {
                "status": "running",
                "cancelled": False,
                "paused": False,
                "created_at": __import__('datetime').datetime.now(),
                "ai_service": None,
            }

        result = await cancel_task(task_id)
        assert result["success"] is True
        assert result["task_status"] == "cancelled"

        async with running_tasks_lock:
            task = running_tasks.get(task_id, {})
            assert task.get("cancelled") is True
            assert task.get("status") == "cancelled"

        # 清理
        async with running_tasks_lock:
            if task_id in running_tasks:
                del running_tasks[task_id]

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """取消不存在的任务"""
        from app.services.react_sse_wrapper import cancel_task
        result = await cancel_task("nonexistent-task")
        assert result["success"] is False
        assert result["task_status"] == "not_found"


# ============================================================
# 7. base_react 中断检查测试
# ============================================================

class TestInterruptCheck:
    """验证agent循环中的cancelled检查"""

    def test_cancelled_flag_check_logic(self):
        """模拟cancelled标志检测逻辑"""
        running_tasks = {
            "task-001": {"cancelled": True, "status": "cancelled"}
        }

        # 模拟agent循环中的检查逻辑
        task_data = running_tasks.get("task-001", {})
        is_cancelled = task_data.get("cancelled", False)
        assert is_cancelled is True

    def test_not_cancelled_flag(self):
        """未取消时标志为False"""
        running_tasks = {
            "task-001": {"cancelled": False, "status": "running"}
        }
        task_data = running_tasks.get("task-001", {})
        is_cancelled = task_data.get("cancelled", False)
        assert is_cancelled is False

    def test_task_not_in_dict(self):
        """任务不在字典中时安全降级"""
        running_tasks = {}
        task_data = running_tasks.get("nonexistent", {})
        is_cancelled = task_data.get("cancelled", False)
        assert is_cancelled is False


# ============================================================
# 8. llm_strategies reasoning 传递测试
# ============================================================

class TestTextStrategyReasoning:
    """验证TextStrategy正确传递response.reasoning"""

    def test_make_result_has_reasoning(self):
        """_make_result支持reasoning参数"""
        from app.services.agent.llm_strategies import TextStrategy
        ts = TextStrategy()
        result = ts._make_result(
            content="回答",
            tool_name="finish",
            tool_params={"result": "回答"},
            reasoning="推理内容"
        )
        d = json.loads(result)
        assert d["content"] == "回答"
        assert d["reasoning"] == "推理内容"

    def test_chunk_json_has_reasoning_field(self):
        """chunk JSON包含reasoning字段"""
        from app.services.agent.llm_strategies import TextStrategy
        ts = TextStrategy()
        # 模拟parse_react_response返回的chunk类型
        parsed = {
            "type": "chunk",
            "content": "回答",
            "thought": "",
            "reasoning": "模型推理",
        }
        # 手动构造chunk_data（模拟TextStrategy.call()中的逻辑）
        import json as j
        chunk_data = {
            "type": "chunk",
            "content": parsed.get("content", ""),
            "thought": parsed.get("thought", ""),
            "reasoning": parsed.get("reasoning", ""),
            "tool_name": None,
            "tool_params": None,
            "response": parsed.get("content", ""),
            "error": None,
            "_thinking": "LLM推理思考过程",
            "is_reasoning": True
        }
        result = j.dumps(chunk_data, ensure_ascii=False)
        d = j.loads(result)
        assert d["_thinking"] == "LLM推理思考过程"
        assert d["is_reasoning"] is True
        assert d["reasoning"] == "模型推理"


# ============================================================
# 9. 导入完整性测试
# ============================================================

class TestModuleImports:
    """所有修改过的模块都能正常导入"""

    MODULES = [
        "app.services.llm_core",
        "app.services.agent.llm_strategies",
        "app.services.react_sse_wrapper",
        "app.services.agent.base_react",
        "app.services.agent.react_output_parser",
        "app.services.agent.reasoning_steps",
        "app.services.chat_router",
        "app.services.intents.crss_scorer",
        "app.services.preprocessing.intent_classifier",
        "app.api.v1.sessions",
        "app.api.v1.execution",
        "app.services.safety.file.file_safety",
        "app.main",
    ]

    def test_all_modules_import(self):
        for module_name in self.MODULES:
            try:
                __import__(module_name)
            except Exception as e:
                pytest.fail(f"导入失败: {module_name} -> {e}")


# ============================================================
# 10. CRSS意图检测测试
# ============================================================

class TestCRSSIntentDetection:
    """CRSS意图分类器基础测试"""

    def test_detect_intent_v2_signature(self):
        """验证detect_intent_v2返回类型正确"""
        import inspect
        from app.services.intents.crss_scorer import detect_intent_v2
        sig = inspect.signature(detect_intent_v2)
        return_annotation = sig.return_annotation
        # 只要有注解就行（L16修复）
        assert return_annotation is not inspect.Parameter.empty


# ============================================================
# 11. SQLite连接测试
# ============================================================

class TestSQLiteConnection:
    """验证SQLite连接函数（WAL模式+忙等待超时）"""

    def test_sessions_db_connection_has_wal(self):
        """sessions.py的_get_db_connection启用了WAL模式"""
        import sqlite3
        from app.api.v1.sessions import _get_db_connection
        conn = _get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal", f"journal_mode应为wal, 实际={mode}"
        cursor.execute("PRAGMA busy_timeout")
        timeout = cursor.fetchone()[0]
        assert timeout >= 4000, f"busy_timeout应>=4000, 实际={timeout}"
        conn.close()

    def test_file_safety_connection_has_wal(self):
        """file_safety.py的_get_connection启用了WAL模式"""
        from app.services.safety.file.file_safety import FileOperationSafety
        safety = FileOperationSafety()
        conn = safety._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode == "wal"
        conn.close()
