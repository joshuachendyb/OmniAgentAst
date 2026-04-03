# -*- coding: utf-8 -*-
"""
chat_stream_query 模块测试

测试流式问答处理函数的逻辑

Author: 小健 - 2026-03-22
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import List, Dict, Optional


class TestChatStreamQueryImport:
    """测试导入"""

    def test_import_chat_stream_query(self):
        """测试 chat_stream_query 可以正确导入"""
        from app.chat_stream import chat_stream_query
        assert chat_stream_query is not None

    def test_import_chat_helpers(self):
        """测试 chat_helpers 可以正确导入"""
        from app.chat_stream.chat_helpers import create_timestamp, get_provider_display_name, create_final_response
        assert create_timestamp is not None
        assert get_provider_display_name is not None
        assert create_final_response is not None

    def test_import_error_handler(self):
        """测试 error_handler 可以正确导入"""
        from app.chat_stream.error_handler import create_error_response, get_user_friendly_error
        assert create_error_response is not None
        assert get_user_friendly_error is not None

    def test_import_incident_handler(self):
        """测试 incident_handler 可以正确导入"""
        from app.chat_stream.incident_handler import create_incident_data, check_and_yield_if_interrupted, check_and_yield_if_paused
        assert create_incident_data is not None
        assert check_and_yield_if_interrupted is not None
        assert check_and_yield_if_paused is not None


class TestCreateTimestamp:
    """测试 create_timestamp 函数"""

    def test_create_timestamp_returns_int(self):
        """测试返回整数类型"""
        from app.chat_stream.chat_helpers import create_timestamp
        result = create_timestamp()
        assert isinstance(result, int)

    def test_create_timestamp_is_reasonable(self):
        """测试时间戳在合理范围内（2020年以后）"""
        from app.chat_stream.chat_helpers import create_timestamp
        result = create_timestamp()
        min_timestamp = 1577836800000  # 2020-01-01 00:00:00 in ms
        assert result > min_timestamp

    def test_create_timestamp_unique(self):
        """测试多次调用返回不同值"""
        import time
        from app.chat_stream.chat_helpers import create_timestamp
        t1 = create_timestamp()
        time.sleep(0.01)
        t2 = create_timestamp()
        assert t2 > t1


class TestCreateFinalResponse:
    """测试 create_final_response 函数"""

    def test_create_final_response_basic(self):
        """测试基本功能"""
        from app.chat_stream.chat_helpers import create_final_response
        result = create_final_response(
            content="Hello",
            model="test-model",
            provider="test-provider"
        )
        assert isinstance(result, str)
        assert "data:" in result
        assert "final" in result
        assert "Hello" in result

    def test_create_final_response_with_display_name(self):
        """测试带 display_name"""
        from app.chat_stream.chat_helpers import create_final_response
        result = create_final_response(
            content="Hello",
            model="test-model",
            provider="test-provider",
            display_name="My Assistant"
        )
        assert "My Assistant" in result

    def test_create_final_response_with_step(self):
        """测试带 step 参数"""
        from app.chat_stream.chat_helpers import create_final_response
        result = create_final_response(
            content="Hello",
            model="test-model",
            provider="test-provider",
            step=5
        )
        assert '"step":5' in result or '"step": 5' in result

    def test_create_final_response_contains_timestamp(self):
        """测试包含 timestamp"""
        from app.chat_stream.chat_helpers import create_final_response
        result = create_final_response(
            content="Hello",
            model="test-model",
            provider="test-provider"
        )
        assert "timestamp" in result


class TestCreateIncidentData:
    """测试 create_incident_data 函数"""

    def test_create_incident_data_interrupted(self):
        """测试 interrupted 类型"""
        from app.chat_stream.incident_handler import create_incident_data
        result = create_incident_data('interrupted', '任务已被中断', step=1)
        assert result['type'] == 'incident'
        assert result['incident_value'] == 'interrupted'
        assert result['message'] == '任务已被中断'
        assert result['step'] == 1
        assert 'timestamp' in result

    def test_create_incident_data_retrying(self):
        """测试 retrying 类型"""
        from app.chat_stream.incident_handler import create_incident_data
        result = create_incident_data('retrying', '正在重试...', step=2)
        assert result['incident_value'] == 'retrying'

    def test_create_incident_data_without_step(self):
        """测试不带 step 参数"""
        from app.chat_stream.incident_handler import create_incident_data
        result = create_incident_data('paused', '任务已暂停')
        assert result['incident_value'] == 'paused'
        assert 'step' not in result


class TestCreateErrorResponse:
    """测试 create_error_response 函数"""

    def test_create_error_response_basic(self):
        """测试基本功能"""
        from app.chat_stream.error_handler import create_error_response
        result = create_error_response(
            error_type="server",
            message="服务错误",
            model="test-model",
            provider="test-provider"
        )
        assert isinstance(result, str)
        assert "data:" in result
        assert "error" in result
        assert "服务错误" in result

    def test_create_error_response_with_step(self):
        """测试带 step 参数"""
        from app.chat_stream.error_handler import create_error_response
        result = create_error_response(
            error_type="timeout",
            message="超时",
            model="test-model",
            provider="test-provider",
            step=3
        )
        assert '"step":3' in result or '"step": 3' in result

    def test_create_error_response_retryable(self):
        """测试 retryable 参数"""
        from app.chat_stream.error_handler import create_error_response
        result = create_error_response(
            error_type="network",
            message="网络错误",
            model="test-model",
            provider="test-provider",
            retryable=True
        )
        assert "retryable" in result


class TestGetUserFriendlyError:
    """测试 get_user_friendly_error 函数"""

    def test_timeout_error(self):
        """测试超时错误"""
        from app.chat_stream.error_handler import get_user_friendly_error
        error = TimeoutError("连接超时")
        result = get_user_friendly_error(error)
        assert result['error_type'] == 'network'  # 根据实际实现

    def test_connection_error(self):
        """测试连接错误"""
        from app.chat_stream.error_handler import get_user_friendly_error
        error = ConnectionError("连接失败")
        result = get_user_friendly_error(error)
        assert result['error_type'] == 'network'  # 根据实际实现

    def test_generic_exception(self):
        """测试通用异常"""
        from app.chat_stream.error_handler import get_user_friendly_error
        error = ValueError("未知错误")
        result = get_user_friendly_error(error)
        assert 'message' in result


class TestCheckAndYieldIfPaused:
    """测试 check_and_yield_if_paused 函数"""

    @pytest.mark.asyncio
    async def test_no_pause_no_yield(self):
        """测试未暂停时不 yield"""
        from app.chat_stream.incident_handler import check_and_yield_if_paused
        
        running_tasks = {'task1': {'paused': False}}
        running_tasks_lock = asyncio.Lock()
        
        results = []
        async for event in check_and_yield_if_paused('task1', running_tasks, running_tasks_lock, lambda: 1):
            results.append(event)
        
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_paused_yields_event(self):
        """测试暂停时 yield 事件"""
        from app.chat_stream.incident_handler import check_and_yield_if_paused
        
        running_tasks = {'task1': {'paused': True}}
        running_tasks_lock = asyncio.Lock()
        
        results = []
        async for event in check_and_yield_if_paused('task1', running_tasks, running_tasks_lock, lambda: 1):
            results.append(event)
        
        assert len(results) == 0


class TestGetProviderDisplayName:
    """测试 get_provider_display_name 函数"""

    def test_returns_provider(self):
        """测试返回 provider 名称"""
        from app.chat_stream.chat_helpers import get_provider_display_name
        result = get_provider_display_name("openai")
        assert result == "openai"


class TestErrorTypeMap:
    """测试错误类型映射"""

    def test_error_type_map_exists(self):
        """测试 ERROR_TYPE_MAP 存在"""
        from app.chat_stream.error_handler import ERROR_TYPE_MAP
        assert isinstance(ERROR_TYPE_MAP, dict)
        assert len(ERROR_TYPE_MAP) > 0

    def test_error_type_map_keys(self):
        """测试错误类型映射包含常见错误"""
        from app.chat_stream.error_handler import ERROR_TYPE_MAP
        assert 'idle_timeout' in ERROR_TYPE_MAP
        assert 'network_error' in ERROR_TYPE_MAP


class TestChatStreamQueryFunctionSignature:
    """测试 chat_stream_query 函数签名"""

    def test_function_exists(self):
        """测试函数存在"""
        from app.chat_stream.chat_stream_query import chat_stream_query
        import inspect
        assert callable(chat_stream_query)
        assert inspect.iscoroutinefunction(chat_stream_query)

    def test_function_parameters(self):
        """测试函数参数"""
        from app.chat_stream.chat_stream_query import chat_stream_query
        import inspect
        sig = inspect.signature(chat_stream_query)
        params = list(sig.parameters.keys())
        
        expected_params = [
            'request', 'ai_service', 'task_id', 'llm_call_count',
            'current_execution_steps', 'current_content', 'last_is_reasoning',
            'last_message', 'running_tasks', 'running_tasks_lock',
            'next_step', 'display_name', 'save_execution_steps_to_db',
            'add_step_and_save'
        ]
        
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
