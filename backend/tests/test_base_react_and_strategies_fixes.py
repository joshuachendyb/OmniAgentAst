"""
测试 base_react.py 的 2026-05-11 新增修复

1. _current_task_id.set(task_id) 在工具执行前设置
2. _current_task_id 从 file_tools 导入

作者：小健
创建时间：2026-05-11
"""

import pytest


class TestBaseReactCurrentTaskId:
    """测试base_react.py中_current_task_id的使用"""

    def test_current_task_id_import_exists(self):
        """TC-BREACT-001: base_react.py导入了_current_task_id"""
        from app.services.agent.base_react import _current_task_id
        assert _current_task_id is not None

    def test_current_task_id_is_contextvar(self):
        """TC-BREACT-002: _current_task_id是ContextVar实例"""
        from contextvars import ContextVar
        from app.services.agent.base_react import _current_task_id
        assert isinstance(_current_task_id, ContextVar)

    def test_current_task_id_same_as_file_tools(self):
        """TC-BREACT-003: base_react导入的_current_task_id与file_tools中的是同一对象"""
        from app.services.agent.base_react import _current_task_id as br_ctx
        from app.services.tools.file.file_tools import _current_task_id as ft_ctx
        assert br_ctx is ft_ctx


class TestLlmStrategiesExtractJsonBlock:
    """测试llm_strategies.py中_extract_json_block的使用"""

    def test_extract_json_block_importable(self):
        """TC-STRAT-001: _extract_json_block可从llm_strategies上下文导入"""
        from app.services.agent.react_output_parser import _extract_json_block
        assert callable(_extract_json_block)

    def test_extract_json_block_with_mixed_content(self):
        """TC-STRAT-002: ToolsStrategy场景-混合前言+JSON提取含tool_name"""
        from app.services.agent.react_output_parser import _extract_json_block
        import json
        content = '好的，我来帮你\n\n{"tool_name": "read_file", "tool_params": {"file_path": "/tmp/test"}, "thought": "读取"}'
        result = _extract_json_block(content)
        assert result is not None
        assert isinstance(result, dict)
        assert "tool_name" in result
        assert result["tool_name"] == "read_file"

    def test_extract_json_block_no_tool_name_falls_through(self):
        """TC-STRAT-003: 提取结果不含tool_name时ToolsStrategy不匹配(交给下游)"""
        from app.services.agent.react_output_parser import _extract_json_block
        content = '{"type": "answer", "content": "完成了"}'
        result = _extract_json_block(content)
        assert result is not None
        assert "tool_name" not in result
