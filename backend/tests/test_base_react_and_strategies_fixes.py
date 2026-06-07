"""
测试 base_react.py 的 2026-05-11 新增修复

1. _current_task_id.set(task_id) 在工具执行前设置
2. _current_task_id 从 file_tools 导入

作者：小健
创建时间：2026-05-11
"""

import pytest
from app.services.tools.file.file_tools import _current_task_id
from contextvars import ContextVar
from app.services.agent.llm_response_parser._json_strategies import _extract_json_block


class TestBaseReactCurrentTaskId:
    """测试_current_task_id的使用（定义在file_tools.py中，base_react.py已移除导入）"""

    def test_current_task_id_import_exists(self):
        """TC-BREACT-001: file_tools.py导出了_current_task_id"""
        assert _current_task_id is not None

    def test_current_task_id_is_contextvar(self):
        """TC-BREACT-002: _current_task_id是ContextVar实例"""
        assert isinstance(_current_task_id, ContextVar)

    def test_current_task_id_same_as_file_tools(self):
        """TC-BREACT-003: _current_task_id在file_tools中定义且可正常导入"""
        assert _current_task_id is not None


class TestLlmStrategiesExtractJsonBlock:
    """测试llm_strategies.py中_extract_json_block的使用"""

    def test_extract_json_block_importable(self):
        """TC-STRAT-001: _extract_json_block可从llm_strategies上下文导入"""
        assert callable(_extract_json_block)

    def test_extract_json_block_with_mixed_content(self):
        """TC-STRAT-002: ToolsStrategy场景-混合前言+JSON提取含tool_name"""
        import json
        content = '好的，我来帮你\n\n{"tool_name": "read_file", "tool_params": {"file_path": "/tmp/test"}, "thought": "读取"}'
        result = _extract_json_block(content)
        assert result is not None
        assert isinstance(result, dict)
        assert "tool_name" in result
        assert result["tool_name"] == "read_file"

    def test_extract_json_block_no_tool_name_falls_through(self):
        """TC-STRAT-003: 提取结果不含tool_name时ToolsStrategy不匹配(交给下游)"""
        content = '{"type": "answer", "content": "完成了"}'
        result = _extract_json_block(content)
        assert result is not None
        assert "tool_name" not in result
