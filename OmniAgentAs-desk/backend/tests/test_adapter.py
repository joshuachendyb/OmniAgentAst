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
        """【修复后】测试dict_history_to_messages别名（现在指向dict_list_to_messages）"""
        dict_list = [{"role": "user", "content": "测试"}]
        
        # 使用别名函数（现在执行 dict -> message 转换）
        result = dict_history_to_messages(dict_list)
        
        # 应该与dict_list_to_messages结果相同
        expected = dict_list_to_messages(dict_list)
        assert len(result) == len(expected)
        for i in range(len(result)):
            assert result[i].role == expected[i].role
            assert result[i].content == expected[i].content


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


class TestRobustness:
    """测试修复后的健壮性（防御性编程）"""
    
    def test_messages_to_dict_list_with_none(self):
        """【修复验证】测试传入None返回空列表"""
        result = messages_to_dict_list(None)
        assert result == []
        assert isinstance(result, list)
    
    def test_messages_to_dict_list_with_none_elements(self):
        """【修复验证】测试列表中包含None元素"""
        messages = [
            Message(role="user", content="test"),
            None,  # None元素
            Message(role="assistant", content="reply")
        ]
        result = messages_to_dict_list(messages)
        # 应该跳过None元素，返回2个结果
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
    
    def test_messages_to_dict_list_with_invalid_objects(self):
        """【修复验证】测试无效对象（缺少属性）"""
        class FakeMessage:
            pass
        
        messages = [
            Message(role="user", content="valid"),
            FakeMessage(),  # 缺少role和content
        ]
        result = messages_to_dict_list(messages)
        # 应该跳过无效对象，只返回有效消息
        assert len(result) == 1
        assert result[0]["content"] == "valid"
    
    def test_messages_to_dict_list_with_none_attributes(self):
        """【修复验证】测试Message属性为None的处理"""
        # 创建一个模拟对象，role为None
        class MessageWithNoneRole:
            role = None
            content = "test"
        
        msg = MessageWithNoneRole()
        # type: ignore - 测试防御性编程，传入非标准对象
        result = messages_to_dict_list([msg])  # type: ignore
        # 应该转换为字符串""
        assert result[0]["role"] == ""
        assert result[0]["content"] == "test"
    
    def test_dict_list_to_messages_with_none(self):
        """【修复验证】测试传入None返回空列表"""
        result = dict_list_to_messages(None)
        assert result == []
        assert isinstance(result, list)
    
    def test_dict_list_to_messages_with_none_elements(self):
        """【修复验证】测试列表中包含None元素"""
        dict_list = [
            {"role": "user", "content": "hello"},
            None,
            {"role": "assistant", "content": "hi"}
        ]
        result = dict_list_to_messages(dict_list)
        # 应该跳过None元素
        assert len(result) == 2
    
    def test_dict_list_to_messages_missing_keys(self):
        """【修复验证】测试字典缺少键（使用.get()安全访问）"""
        dict_list = [
            {"role": "user"},  # 缺少content
            {"content": "hello"},  # 缺少role
            {},  # 完全空字典
        ]
        result = dict_list_to_messages(dict_list)
        # 应该使用默认值""
        assert len(result) == 3
        assert result[0].role == "user"
        assert result[0].content == ""
        assert result[1].role == ""
        assert result[1].content == "hello"
        assert result[2].role == ""
        assert result[2].content == ""


class TestAliasCorrectness:
    """测试别名指向正确性"""
    
    def test_dict_history_to_messages_alias_correctness(self):
        """【修复验证】测试别名指向正确的函数"""
        # dict_history_to_messages 应该执行 dict -> message 转换
        dict_list = [{"role": "user", "content": "test"}]
        
        # 使用别名
        result = dict_history_to_messages(dict_list)
        
        # 验证结果是Message对象（不是dict）
        assert len(result) == 1
        assert isinstance(result[0], Message)
        assert result[0].role == "user"
        assert result[0].content == "test"
    
    def test_alias_and_original_equivalence(self):
        """测试别名和原函数等价"""
        dict_list = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]
        
        # 别名和原函数应该返回相同结果
        alias_result = dict_history_to_messages(dict_list)
        original_result = dict_list_to_messages(dict_list)
        
        assert len(alias_result) == len(original_result)
        for i in range(len(alias_result)):
            assert alias_result[i].role == original_result[i].role
            assert alias_result[i].content == original_result[i].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
