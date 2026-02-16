"""
适配器模块单元测试
测试参数类型转换函数的正确性
"""

import pytest
from app.services.base import Message
from app.services.file_operations.adapter import (
    messages_to_dict_list,
    dict_list_to_messages,
    convert_chat_history,
    dict_history_to_messages
)


class TestMessagesToDictList:
    """测试messages_to_dict_list函数"""
    
    def test_empty_list(self):
        """测试空列表"""
        result = messages_to_dict_list([])
        assert result == []
        assert isinstance(result, list)
    
    def test_single_message(self):
        """测试单条消息转换"""
        messages = [Message(role="user", content="你好")]
        result = messages_to_dict_list(messages)
        
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "你好"
    
    def test_multiple_messages(self):
        """测试多条消息转换"""
        messages = [
            Message(role="system", content="你是助手"),
            Message(role="user", content="你好"),
            Message(role="assistant", content="你好！有什么可以帮助你？"),
            Message(role="user", content="谢谢")
        ]
        result = messages_to_dict_list(messages)
        
        assert len(result) == 4
        assert result[0] == {"role": "system", "content": "你是助手"}
        assert result[1] == {"role": "user", "content": "你好"}
        assert result[2] == {"role": "assistant", "content": "你好！有什么可以帮助你？"}
        assert result[3] == {"role": "user", "content": "谢谢"}
    
    def test_special_characters(self):
        """测试特殊字符内容"""
        messages = [
            Message(role="user", content="Hello! 你好！🎉"),
            Message(role="assistant", content="Line1\nLine2\tTabbed")
        ]
        result = messages_to_dict_list(messages)
        
        assert result[0]["content"] == "Hello! 你好！🎉"
        assert result[1]["content"] == "Line1\nLine2\tTabbed"
    
    def test_long_content(self):
        """测试长内容"""
        long_text = "A" * 10000
        messages = [Message(role="user", content=long_text)]
        result = messages_to_dict_list(messages)
        
        assert result[0]["content"] == long_text
        assert len(result[0]["content"]) == 10000


class TestDictListToMessages:
    """测试dict_list_to_messages函数"""
    
    def test_empty_list(self):
        """测试空列表"""
        result = dict_list_to_messages([])
        assert result == []
        assert isinstance(result, list)
    
    def test_single_dict(self):
        """测试单个字典转换"""
        dict_list = [{"role": "user", "content": "你好"}]
        result = dict_list_to_messages(dict_list)
        
        assert len(result) == 1
        assert isinstance(result[0], Message)
        assert result[0].role == "user"
        assert result[0].content == "你好"
    
    def test_multiple_dicts(self):
        """测试多个字典转换"""
        dict_list = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"}
        ]
        result = dict_list_to_messages(dict_list)
        
        assert len(result) == 3
        assert all(isinstance(msg, Message) for msg in result)
        assert result[0].role == "system"
        assert result[1].role == "user"
        assert result[2].role == "assistant"


class TestRoundTripConversion:
    """测试双向转换的一致性"""
    
    def test_message_to_dict_and_back(self):
        """测试Message -> Dict -> Message转换一致性"""
        original = [
            Message(role="system", content="你是助手"),
            Message(role="user", content="你好"),
            Message(role="assistant", content="你好！有什么可以帮助你？")
        ]
        
        # Message -> Dict
        dict_list = messages_to_dict_list(original)
        # Dict -> Message
        converted = dict_list_to_messages(dict_list)
        
        assert len(converted) == len(original)
        for i in range(len(original)):
            assert converted[i].role == original[i].role
            assert converted[i].content == original[i].content
    
    def test_dict_to_message_and_back(self):
        """测试Dict -> Message -> Dict转换一致性"""
        original = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"}
        ]
        
        # Dict -> Message
        messages = dict_list_to_messages(original)
        # Message -> Dict
        converted = messages_to_dict_list(messages)
        
        assert converted == original


class TestConvertChatHistory:
    """测试convert_chat_history函数"""
    
    def test_convert_to_dict(self):
        """测试转换为dict格式"""
        messages = [
            Message(role="user", content="你好")
        ]
        result = convert_chat_history(messages, target_format="dict")
        
        assert isinstance(result, list)
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "你好"
    
    def test_unsupported_format(self):
        """测试不支持的格式"""
        messages = [Message(role="user", content="你好")]
        
        with pytest.raises(ValueError) as exc_info:
            convert_chat_history(messages, target_format="xml")
        
        assert "Unsupported target format" in str(exc_info.value)


class TestBackwardCompatibility:
    """测试向后兼容性"""
    
    def test_dict_history_to_messages_alias(self):
        """测试dict_history_to_messages别名"""
        messages = [Message(role="user", content="测试")]
        
        # 使用别名函数
        result = dict_history_to_messages(messages)
        
        # 应该与messages_to_dict_list结果相同
        expected = messages_to_dict_list(messages)
        assert result == expected


class TestIntegrationWithAgent:
    """测试与FileOperationAgent的集成场景"""
    
    def test_chat_history_to_agent_format(self):
        """测试chat.py历史记录转换为Agent可用格式"""
        # 模拟chat.py中的历史记录
        chat_history = [
            Message(role="system", content="你是文件操作助手"),
            Message(role="user", content="请帮我整理桌面文件"),
            Message(role="assistant", content="我来帮您整理桌面文件"),
        ]
        
        # 转换为Agent格式
        agent_history = messages_to_dict_list(chat_history)
        
        # 验证格式
        assert isinstance(agent_history, list)
        assert all(isinstance(msg, dict) for msg in agent_history)
        assert all("role" in msg and "content" in msg for msg in agent_history)
        
        # 验证FileOperationAgent可以使用
        assert agent_history[0]["role"] == "system"
        assert agent_history[1]["role"] == "user"
        assert agent_history[2]["role"] == "assistant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
