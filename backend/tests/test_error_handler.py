# -*- coding: utf-8 -*-
"""
错误处理测试 - 验证ERROR_TYPE_MAP和相关函数

根据TDD原则：
1. 先写测试用例（RED）- 测试用例应该失败
2. 再写实现代码（GREEN）- 让测试通过

测试目标：
1. ERROR_TYPE_MAP 映射正确性
2. get_function_call_error_info() 调用 ERROR_TYPE_MAP（处理function call异常）
3. get_stream_error_info() 辅助函数（处理stream错误）
4. create_session_error_result() 函数（会话级错误）
5. create_tool_error_result() 函数（工具级错误）

Author: 小沈 - 2026-04-10
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.chat_stream.error_handler import (
    ERROR_TYPE_MAP,
    get_function_call_error_info,
    classify_error,
    resolve_http_error_type,
)


class TestErrorTypeMap:
    """测试 ERROR_TYPE_MAP 的映射正确性"""

    def test_connect_error_mapping(self):
        """connect_error 应该映射为 'connect'，不是 'network'"""
        assert ERROR_TYPE_MAP['connect_error'][0] == 'connect'

    def test_protocol_error_mapping(self):
        """protocol_error 应该映射为 'protocol'，不是 'server'"""
        assert ERROR_TYPE_MAP['protocol_error'][0] == 'protocol'

    def test_proxy_error_mapping(self):
        """proxy_error 应该映射为 'protocol'，不是 'network'"""
        assert ERROR_TYPE_MAP['proxy_error'][0] == 'protocol'

    def test_timeout_mapping(self):
        """timeout_error 应该映射为 'timeout'"""
        assert ERROR_TYPE_MAP['timeout_error'][0] == 'timeout'

    def test_idle_timeout_mapping(self):
        """idle_timeout 应该映射为 'timeout'"""
        assert ERROR_TYPE_MAP['idle_timeout'][0] == 'timeout'

    def test_read_error_mapping(self):
        """read_error 应该映射为 'server'"""
        assert ERROR_TYPE_MAP['read_error'][0] == 'server'

    def test_write_error_mapping(self):
        """write_error 应该映射为 'server'"""
        ERROR_TYPE_MAP['write_error'][0] == 'server'

    def test_network_error_mapping(self):
        """network_error 应该映射为 'network'"""
        assert ERROR_TYPE_MAP['network_error'][0] == 'network'


class TestGetFunctionCallErrorInfo:
    """测试 get_function_call_error_info() 函数"""

    def test_httpx_connect_error(self):
        """httpx.ConnectError 应该返回 error_type='connect'"""
        from httpx import ConnectError
        error = ConnectError("Connection failed")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'connect', f"Expected 'connect', got '{result['error_type']}'"

    def test_httpx_protocol_error(self):
        """httpx.ProtocolError 应该返回 error_type='protocol'"""
        from httpx import ProtocolError
        error = ProtocolError("Protocol error")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'protocol', f"Expected 'protocol', got '{result['error_type']}'"

    def test_httpx_proxy_error(self):
        """httpx.ProxyError 应该返回 error_type='protocol'"""
        from httpx import ProxyError
        error = ProxyError("Proxy error")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'protocol', f"Expected 'protocol', got '{result['error_type']}'"

    def test_httpx_timeout_exception(self):
        """httpx.TimeoutException 应该返回 error_type='timeout'"""
        from httpx import TimeoutException
        error = TimeoutException("Timeout")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'timeout', f"Expected 'timeout', got '{result['error_type']}'"

    def test_httpx_read_error(self):
        """httpx.ReadError 应该返回 error_type='server'"""
        from httpx import ReadError
        error = ReadError("Read error")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'server', f"Expected 'server', got '{result['error_type']}'"

    def test_httpx_write_error(self):
        """httpx.WriteError 应该返回 error_type='server'"""
        from httpx import WriteError
        error = WriteError("Write error")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'server', f"Expected 'server', got '{result['error_type']}'"

    def test_httpx_network_error(self):
        """httpx.NetworkError 应该返回 error_type='network'"""
        from httpx import NetworkError
        error = NetworkError("Network error")
        result = get_function_call_error_info(error)
        assert result['error_type'] == 'network', f"Expected 'network', got '{result['error_type']}'"


class TestClassifyError:
    """测试 classify_error() 函数"""

    def test_classify_connect_error(self):
        """classify_error('connect_error') 应该返回 ('connect', ...)"""
        code, message = classify_error('connect_error')
        assert code == 'connect', f"Expected 'connect', got '{code}'"

    def test_classify_protocol_error(self):
        """classify_error('protocol_error') 应该返回 ('protocol', ...)"""
        code, message = classify_error('protocol_error')
        assert code == 'protocol', f"Expected 'protocol', got '{code}'"

    def test_classify_proxy_error(self):
        """classify_error('proxy_error') 应该返回 ('protocol', ...)"""
        code, message = classify_error('proxy_error')
        assert code == 'protocol', f"Expected 'protocol', got '{code}'"

    def test_classify_timeout_error(self):
        """classify_error('timeout_error') 应该返回 ('timeout', ...)"""
        code, message = classify_error('timeout_error')
        assert code == 'timeout', f"Expected 'timeout', got '{code}'"

    def test_classify_unknown(self):
        """classify_error('unknown_type') 应该返回默认 ('server', ...)"""
        code, message = classify_error('unknown_type', 'Some error')
        assert code == 'server', f"Expected 'server', got '{code}'"


class TestGetStreamErrorInfo:
    """测试 get_stream_error_info() 辅助函数"""

    def test_get_stream_error_info_exists(self):
        """get_stream_error_info() 函数应该存在"""
        from app.chat_stream.error_handler import get_stream_error_info
        assert callable(get_stream_error_info)

    def test_get_stream_error_info_connect(self):
        """get_stream_error_info('connect_error') 应该返回 error_type='connect'"""
        from app.chat_stream.error_handler import get_stream_error_info
        result = get_stream_error_info('connect_error')
        assert result[0] == 'connect', f"Expected 'connect', got '{result[0]}'"

    def test_get_stream_error_info_protocol(self):
        """get_stream_error_info('protocol_error') 应该返回 error_type='protocol'"""
        from app.chat_stream.error_handler import get_stream_error_info
        result = get_stream_error_info('protocol_error')
        assert result[0] == 'protocol', f"Expected 'protocol', got '{result[0]}'"

    def test_get_stream_error_info_proxy(self):
        """get_stream_error_info('proxy_error') 应该返回 error_type='protocol'"""
        from app.chat_stream.error_handler import get_stream_error_info
        result = get_stream_error_info('proxy_error')
        assert result[0] == 'protocol', f"Expected 'protocol', got '{result[0]}'"

    def test_get_stream_error_info_unknown(self):
        """get_stream_error_info('unknown') 应该返回默认 error_type='server'"""
        from app.chat_stream.error_handler import get_stream_error_info
        result = get_stream_error_info('unknown')
        assert result[0] == 'server', f"Expected 'server', got '{result[0]}'"


class TestResolveHttpErrorType:
    """测试 resolve_http_error_type 函数 - 从错误消息中解析HTTP错误码"""

    def test_limit_error(self):
        """limit_error 应该解析为 api_error_429"""
        result = resolve_http_error_type('rate limit error: limit_error')
        assert result == 'api_error_429', f"Expected 'api_error_429', got '{result}'"

    def test_rate_limit_space(self):
        """rate limit(空格) 应该解析为 api_error_429"""
        result = resolve_http_error_type('rate limit exceeded')
        assert result == 'api_error_429', f"Expected 'api_error_429', got '{result}'"

    def test_too_many_requests(self):
        """too many requests 应该解析为 api_error_429"""
        result = resolve_http_error_type('Too Many Requests')
        assert result == 'api_error_429', f"Expected 'api_error_429', got '{result}'"

    def test_429_code(self):
        """429 应该解析为 api_error_429"""
        result = resolve_http_error_type('HTTP 429 Too Many Requests')
        assert result == 'api_error_429', f"Expected 'api_error_429', got '{result}'"

    def test_503_code(self):
        """503 应该解析为 api_error_503"""
        result = resolve_http_error_type('HTTP 503 Service Unavailable')
        assert result == 'api_error_503', f"Expected 'api_error_503', got '{result}'"

    def test_401_code(self):
        """401 应该解析为 api_error_401"""
        result = resolve_http_error_type('HTTP 401 Unauthorized')
        assert result == 'api_error_401', f"Expected 'api_error_401', got '{result}'"

    def test_auth_keyword(self):
        """auth 关键词应该解析为 api_error_401"""
        result = resolve_http_error_type('authentication failed')
        assert result == 'api_error_401', f"Expected 'api_error_401', got '{result}'"

    def test_unauthorized_keyword(self):
        """unauthorized 关键词应该解析为 api_error_401"""
        result = resolve_http_error_type('unauthorized access')
        assert result == 'api_error_401', f"Expected 'api_error_401', got '{result}'"

    def test_403_code(self):
        """403 应该解析为 api_error_403"""
        result = resolve_http_error_type('HTTP 403 Forbidden')
        assert result == 'api_error_403', f"Expected 'api_error_403', got '{result}'"

    def test_forbidden_keyword(self):
        """forbidden 关键词应该解析为 api_error_403"""
        result = resolve_http_error_type('access forbidden')
        assert result == 'api_error_403', f"Expected 'api_error_403', got '{result}'"

    def test_400_code(self):
        """400 应该解析为 api_error_400"""
        result = resolve_http_error_type('HTTP 400 Bad Request')
        assert result == 'api_error_400', f"Expected 'api_error_400', got '{result}'"

    def test_500_code(self):
        """500 应该解析为 api_error_500"""
        result = resolve_http_error_type('HTTP 500 Internal Server Error')
        assert result == 'api_error_500', f"Expected 'api_error_500', got '{result}'"

    def test_502_code(self):
        """502 应该解析为 api_error_502"""
        result = resolve_http_error_type('HTTP 502 Bad Gateway')
        assert result == 'api_error_502', f"Expected 'api_error_502', got '{result}'"

    def test_504_code(self):
        """504 应该解析为 api_error_504"""
        result = resolve_http_error_type('HTTP 504 Gateway Timeout')
        assert result == 'api_error_504', f"Expected 'api_error_504', got '{result}'"

    def test_empty_string(self):
        """空字符串应该返回 None"""
        result = resolve_http_error_type('')
        assert result is None, f"Expected None, got '{result}'"

    def test_none_input(self):
        """None 输入应该返回 None"""
        result = resolve_http_error_type(None)
        assert result is None, f"Expected None, got '{result}'"

    def test_no_match(self):
        """无法匹配的错误消息应该返回 None"""
        result = resolve_http_error_type('some random error message')
        assert result is None, f"Expected None, got '{result}'"

    def test_priority_limit_error_vs_429(self):
        """limit_error 应该优先于 429 匹配（虽然结果相同）"""
        result = resolve_http_error_type('limit_error (429)')
        assert result == 'api_error_429', f"Expected 'api_error_429', got '{result}'"


class TestCreateSessionErrorResult:
    """测试 create_session_error_result() 函数 - 会话级错误处理"""

    def test_function_exists(self):
        """create_session_error_result() 函数应该存在"""
        from app.chat_stream.error_handler import create_session_error_result
        assert callable(create_session_error_result)

    def test_returns_tuple(self):
        """create_session_error_result() 应该返回 (error_response, error_step) 元组"""
        from app.chat_stream.error_handler import create_session_error_result
        result = create_session_error_result(
            error_step_type='timeout',
            original_error='Connection timeout',
            step_num=1
        )
        assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
        assert len(result) == 2, f"Expected 2 elements, got {len(result)}"

    def test_error_response_format(self):
        """返回的 error_response 应该是 SSE 格式字符串"""
        from app.chat_stream.error_handler import create_session_error_result
        error_response, error_step = create_session_error_result(
            error_step_type='timeout',
            original_error='Connection timeout',
            step_num=1
        )
        assert isinstance(error_response, str), f"Expected str, got {type(error_response)}"
        assert error_response.startswith('data: '), f"Expected SSE format, got {error_response[:20]}"

    def test_error_step_format(self):
        """返回的 error_step 应该是包含 type='error' 的字典"""
        from app.chat_stream.error_handler import create_session_error_result
        error_response, error_step = create_session_error_result(
            error_step_type='timeout',
            original_error='Connection timeout',
            step_num=1
        )
        assert isinstance(error_step, dict), f"Expected dict, got {type(error_step)}"
        assert error_step.get('type') == 'error', f"Expected type='error', got {error_step.get('type')}"

    def test_with_idle_timeout(self):
        """idle_timeout 错误应该包含超时时间信息"""
        from app.chat_stream.error_handler import create_session_error_result
        error_response, error_step = create_session_error_result(
            error_step_type='idle_timeout',
            original_error='Timeout after 30s',
            step_num=1,
            display_name='GPT-4',
            chat_timeout=30,
            max_retries=3
        )
        # 【15.7修改】message替换为error_message
        error_message = error_step.get('error_message', '')
        assert 'GPT-4' in error_message, f"Expected 'GPT-4' in error_message, got {error_message}"
        assert '30秒' in error_message, f"Expected '30秒' in error_message, got {error_message}"

    def test_with_http_error_429(self):
        """429 错误应该正确解析"""
        from app.chat_stream.error_handler import create_session_error_result
        error_response, error_step = create_session_error_result(
            error_step_type='api_error_429',
            original_error='Rate limit exceeded (429)',
            step_num=1
        )
        assert error_step.get('error_type') == 'api_error', f"Expected 'api_error', got {error_step.get('error_type')}"

    def test_with_http_error_500(self):
        """500 错误应该正确解析"""
        from app.chat_stream.error_handler import create_session_error_result
        error_response, error_step = create_session_error_result(
            error_step_type='api_error_500',
            original_error='Internal server error (500)',
            step_num=2
        )
        assert error_step.get('error_type') == 'server', f"Expected 'server', got {error_step.get('error_type')}"


class TestCreateToolErrorResult:
    """测试 create_tool_error_result() 函数 - 工具级错误处理"""

    def test_function_exists(self):
        """create_tool_error_result() 函数应该存在"""
        from app.chat_stream.error_handler import create_tool_error_result
        assert callable(create_tool_error_result)

    def test_returns_dict(self):
        """create_tool_error_result() 应该返回可以直接 yield 的 dict"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='read_file',
            error_message='File not found',
            step_num=1
        )
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_contains_required_fields(self):
        """返回的 dict 应包含 action_tool 的必需字段"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='read_file',
            error_message='File not found',
            step_num=1
        )
        # 【2026-04-15 小沈修改15.7】：按15.7.1要求修改字段名
        # raw_data → execution_result, 新增 error_message, execution_time_ms
        required_fields = ['tool_name', 'tool_params', 'execution_status', 'summary', 'execution_result', 'action_retry_count', 'step', 'timestamp', 'error_message', 'execution_time_ms']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_execution_status_is_error(self):
        """execution_status 应该是 'error'"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='read_file',
            error_message='File not found',
            step_num=1
        )
        assert result.get('execution_status') == 'error', f"Expected 'error', got {result.get('execution_status')}"

    def test_summary_contains_error_info(self):
        """summary 应该包含工具名和错误信息"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='read_file',
            error_message='File not found',
            step_num=1
        )
        summary = result.get('summary', '')
        assert 'read_file' in summary, f"Expected 'read_file' in summary, got {summary}"
        assert 'File not found' in summary, f"Expected 'File not found' in summary, got {summary}"

    def test_with_tool_params(self):
        """应该正确处理 tool_params 参数"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='search_files',
            error_message='Permission denied',
            step_num=2,
            tool_params={'path': '/data', 'pattern': '*.txt'}
        )
        assert result.get('tool_params') == {'path': '/data', 'pattern': '*.txt'}, f"Expected tool_params, got {result.get('tool_params')}"

    def test_with_retry_count(self):
        """应该正确处理 retry_count 参数"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='http_request',
            error_message='Connection timeout',
            step_num=3,
            retry_count=2,
            max_retries=3
        )
        assert result.get('action_retry_count') == 2, f"Expected 2, got {result.get('action_retry_count')}"

    def test_with_raw_data(self):
        """应该正确处理 raw_data 参数"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='execute_command',
            error_message='Command failed',
            step_num=4,
            raw_data={'exit_code': 1, 'stderr': 'Error output'}
        )
        # 【2026-04-15 小沈修改15.7】：按15.7.1要求，raw_data字段已改为execution_result
        assert result.get('execution_result') == {'exit_code': 1, 'stderr': 'Error output'}, f"Expected execution_result, got {result.get('execution_result')}"

    def test_timestamp_is_present(self):
        """timestamp 字段应该存在"""
        from app.chat_stream.error_handler import create_tool_error_result
        result = create_tool_error_result(
            tool_name='read_file',
            error_message='Error',
            step_num=1
        )
        assert 'timestamp' in result, "Missing timestamp field"
        assert result['timestamp'], "timestamp should not be empty"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])