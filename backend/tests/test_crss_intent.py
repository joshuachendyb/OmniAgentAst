# -*- coding: utf-8 -*-
"""
CRSS意图检测测试用例

Author: 小沈 - 2026-04-20
"""
import pytest
from app.services.chat_router import detect_intent_from_crss


class TestCRSSIntentDetection:
    """CRSS意图检测测试类"""
    
    def test_dangerous_command_rm_rf(self):
        """测试危险命令: rm -rf"""
        result = detect_intent_from_crss('rm -rf /')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_dangerous_command_format(self):
        """测试危险命令: format"""
        result = detect_intent_from_crss('format c:')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_dangerous_command_sudo_rm(self):
        """测试危险命令: sudo rm"""
        result = detect_intent_from_crss('sudo rm -rf /var')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_file_operation_cat(self):
        """测试文件读取: cat"""
        result = detect_intent_from_crss('cat readme.txt')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_file_operation_delete(self):
        """测试文件删除: delete"""
        result = detect_intent_from_crss('帮我删除这个文件')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_file_operation_ls(self):
        """测试目录列表: ls"""
        result = detect_intent_from_crss('ls -la')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_file_operation_mkdir(self):
        """测试创建目录: mkdir"""
        result = detect_intent_from_crss('mkdir newfolder')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_file_operation_copy(self):
        """测试复制文件: copy"""
        result = detect_intent_from_crss('copy file1 file2')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_chat_simple_greeting(self):
        """测试简单对话: 问候"""
        result = detect_intent_from_crss('你好')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_chat_weather(self):
        """测试简单对话: 天气"""
        result = detect_intent_from_crss('今天天气怎么样')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_chat_explanation(self):
        """测试简单对话: 解释"""
        result = detect_intent_from_crss('解释一下量子计算')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_chat_question(self):
        """测试简单对话: 问题"""
        result = detect_intent_from_crss('什么是人工智能')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_chat_empty(self):
        """测试空输入"""
        result = detect_intent_from_crss('')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_chat_whitespace(self):
        """测试空白输入"""
        result = detect_intent_from_crss('   ')
        assert result == ('chat', 1.0), f"期望chat，实际{result}"
    
    def test_network_keyword_ping(self):
        """测试网络操作: ping"""
        result = detect_intent_from_crss('ping 192.168.1.1')
        assert result == ('file', 1.0), f"期望file，实际{result}"
    
    def test_network_keyword_curl(self):
        """测试网络操作: curl"""
        result = detect_intent_from_crss('curl https://example.com')
        assert result == ('file', 1.0), f"期望file，实际{result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
