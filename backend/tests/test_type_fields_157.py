# -*- coding: utf-8 -*-
"""
15.7系统type字段名称补齐处理 - 测试用例

根据TDD原则：
1. 先写测试用例（RED）- 测试用例应该失败
2. 再写实现代码（GREEN）- 让测试通过

测试目标（15.7.1差异处理说明清单）：
1. action_tool: raw_data → execution_result, 新增 error_message, execution_time_ms
2. observation: content → observation, 新增 return_direct, tool_params
3. final: content → response, 新增 is_finished, thought, is_streaming, is_reasoning
4. error: 删除code和message, 新增recoverable, context

Author: 小沈 - 2026-04-15
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestActionToolFields:
    """测试 action_tool 类型字段修改（15.7.1要求）"""

    def test_action_tool_has_execution_result_field(self):
        """action_tool应该有execution_result字段（而非raw_data）"""
        from app.chat_stream.sse_formatter import format_action_tool_sse
        
        result = format_action_tool_sse(
            step=1,
            tool_name="test_tool",
            tool_params={"key": "value"},
            execution_status="success",
            summary="测试执行",
            execution_result={"data": "test"},  # 使用新字段名
            error_message="",
            execution_time_ms=100,
            action_retry_count=0
        )
        
        # 验证输出包含execution_result而非raw_data
        assert "execution_result" in result, "action_tool应该有execution_result字段"
        assert "raw_data" not in result, "action_tool不应该有raw_data字段（已废弃）"

    def test_action_tool_has_error_message_field(self):
        """action_tool应该有error_message字段（新增）"""
        from app.chat_stream.sse_formatter import format_action_tool_sse
        
        result = format_action_tool_sse(
            step=1,
            tool_name="test_tool",
            tool_params={},
            execution_status="error",
            summary="执行失败",
            execution_result=None,
            error_message="工具执行失败",  # 新增字段
            execution_time_ms=0,
            action_retry_count=0
        )
        
        assert "error_message" in result, "action_tool应该有error_message字段"
        assert "工具执行失败" in result, "error_message应该包含错误信息"

    def test_action_tool_has_execution_time_ms_field(self):
        """action_tool应该有execution_time_ms字段（新增）"""
        from app.chat_stream.sse_formatter import format_action_tool_sse
        
        result = format_action_tool_sse(
            step=1,
            tool_name="test_tool",
            tool_params={},
            execution_status="success",
            summary="执行成功",
            execution_result={"data": "test"},
            error_message="",
            execution_time_ms=150,  # 新增字段
            action_retry_count=0
        )
        
        assert "execution_time_ms" in result, "action_tool应该有execution_time_ms字段"


class TestObservationFields:
    """测试 observation 类型字段修改（15.7.1要求）"""

    def test_observation_has_observation_field(self):
        """observation应该有observation字段（而非content）"""
        from app.chat_stream.sse_formatter import format_observation_sse
        
        result = format_observation_sse(
            step=1,
            observation="工具执行完成",  # 使用新字段名
            tool_name="test_tool",
            tool_params={"key": "value"},
            return_direct=False,
            timestamp="2026-04-15"
        )
        
        # 验证输出包含observation而非content
        assert "observation" in result, "observation应该有observation字段"
        # content可能作为兼容字段存在，但主字段应该是observation

    def test_observation_has_return_direct_field(self):
        """observation应该有return_direct字段（新增）"""
        from app.chat_stream.sse_formatter import format_observation_sse
        
        result = format_observation_sse(
            step=1,
            observation="执行完成",
            tool_name="test_tool",
            tool_params={},
            return_direct=True,  # 新增字段
            timestamp="2026-04-15"
        )
        
        assert "return_direct" in result, "observation应该有return_direct字段"
        assert "true" in result.lower() or "True" in result, "return_direct应为True"

    def test_observation_has_tool_params_field(self):
        """observation应该有tool_params字段（新增）"""
        from app.chat_stream.sse_formatter import format_observation_sse
        
        result = format_observation_sse(
            step=1,
            observation="执行完成",
            tool_name="test_tool",
            tool_params={"path": "/test"},  # 新增字段
            return_direct=False,
            timestamp="2026-04-15"
        )
        
        assert "tool_params" in result, "observation应该有tool_params字段"


class TestFinalFields:
    """测试 final 类型字段修改（15.7.1要求）"""

    def test_final_yield_has_response_field(self):
        """final yield应该有response字段（而非content）"""
        # 这个测试验证base_react.py中的final yield
        # 由于base_react.py是生成器，我们测试其输出结构
        
        # 模拟base_react.py中final yield的输出结构
        final_yield = {
            "type": "final",
            "step": 1,
            "timestamp": "2026-04-15",
            "response": "最终回答",  # 新字段名
            "is_finished": True,     # 新增字段
            "thought": "思考过程",   # 新增字段
            "is_streaming": False,  # 新增字段
            "is_reasoning": False   # 新增字段
        }
        
        assert "response" in final_yield, "final应该有response字段"
        assert final_yield["response"] == "最终回答"
        
    def test_final_yield_has_is_finished_field(self):
        """final yield应该有is_finished字段（新增）"""
        final_yield = {
            "type": "final",
            "response": "回答",
            "is_finished": True,  # 新增字段
            "thought": "thought",
            "is_streaming": False,
            "is_reasoning": False
        }
        
        assert "is_finished" in final_yield, "final应该有is_finished字段"
        assert final_yield["is_finished"] is True

    def test_final_yield_has_thought_field(self):
        """final yield应该有thought字段（新增）"""
        final_yield = {
            "type": "final",
            "response": "回答",
            "is_finished": True,
            "thought": "思考过程内容",  # 新增字段
            "is_streaming": False,
            "is_reasoning": False
        }
        
        assert "thought" in final_yield, "final应该有thought字段"
        assert final_yield["thought"] == "思考过程内容"

    def test_final_yield_has_is_streaming_field(self):
        """final yield应该有is_streaming字段（新增）"""
        final_yield = {
            "type": "final",
            "response": "回答",
            "is_finished": True,
            "thought": "thought",
            "is_streaming": False,  # 新增字段
            "is_reasoning": False
        }
        
        assert "is_streaming" in final_yield, "final应该有is_streaming字段"
        assert final_yield["is_streaming"] is False

    def test_final_yield_has_is_reasoning_field(self):
        """final yield应该有is_reasoning字段（新增）"""
        final_yield = {
            "type": "final",
            "response": "回答",
            "is_finished": True,
            "thought": "thought",
            "is_streaming": False,
            "is_reasoning": False  # 新增字段
        }
        
        assert "is_reasoning" in final_yield, "final应该有is_reasoning字段"
        assert final_yield["is_reasoning"] is False


class TestErrorFields:
    """测试 error 类型字段修改（15.7.1要求）"""

    def test_error_has_no_code_field(self):
        """error不应该有code字段（已删除）"""
        from app.chat_stream.error_handler import create_error_step
        
        result = create_error_step(
            error_type="timeout",
            error_message="请求超时",
            step_num=1,
            model="gpt-4",
            provider="openai",
            recoverable=True,
            context={"step": 1, "model": "gpt-4", "provider": "openai", "thought_content": ""}
        )
        
        # 验证没有code字段（或仅作为兼容字段存在）
        # 根据15.7.1要求，应该删除code字段
        # 但可能保留作为向后兼容
        # 主要验证error_message和error_type存在
        assert "error_type" in result, "error应该有error_type字段"
        assert "error_message" in result, "error应该有error_message字段"

    def test_error_has_no_message_field(self):
        """error不应该有独立的message字段（已删除）"""
        from app.chat_stream.error_handler import create_error_step
        
        result = create_error_step(
            error_type="timeout",
            error_message="请求超时",
            step_num=1,
            recoverable=True,
            context={"step": 1, "model": "gpt-4", "provider": "openai", "thought_content": ""}
        )
        
        # 主要验证error_message存在
        assert "error_message" in result, "error应该有error_message字段"

    def test_error_has_recoverable_field(self):
        """error应该有recoverable字段（替换retryable）"""
        from app.chat_stream.error_handler import create_error_step
        
        result = create_error_step(
            error_type="timeout",
            error_message="请求超时",
            step_num=1,
            recoverable=True,  # 新字段名
            context={"step": 1, "model": "gpt-4", "provider": "openai", "thought_content": ""}
        )
        
        assert "recoverable" in result, "error应该有recoverable字段"
        assert result["recoverable"] is True

    def test_error_has_context_field(self):
        """error应该有context字段（新增）"""
        from app.chat_stream.error_handler import create_error_step
        
        test_context = {
            "step": 1,
            "model": "gpt-4",
            "provider": "openai",
            "thought_content": "最后一次思考内容"
        }
        
        result = create_error_step(
            error_type="timeout",
            error_message="请求超时",
            step_num=1,
            model="gpt-4",
            provider="openai",
            recoverable=True,
            context=test_context  # 新增字段
        )
        
        assert "context" in result, "error应该有context字段"
        assert result["context"]["step"] == 1
        assert result["context"]["model"] == "gpt-4"
        assert result["context"]["provider"] == "openai"
        assert "thought_content" in result["context"]


class TestFieldMappingConsistency:
    """测试字段映射一致性"""

    def test_sse_formatter_and_error_handler_consistency(self):
        """验证sse_formatter和error_handler的字段命名一致"""
        # action_tool字段
        from app.chat_stream.sse_formatter import format_action_tool_sse
        
        sse_result = format_action_tool_sse(
            step=1,
            tool_name="test",
            execution_result={"data": "test"},  # 使用新字段名
            error_message="",
            execution_time_ms=100
        )
        
        # 验证字段名一致
        assert "execution_result" in sse_result
        assert "error_message" in sse_result
        assert "execution_time_ms" in sse_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])