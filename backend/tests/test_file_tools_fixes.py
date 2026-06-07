"""
测试 file_tools.py 的 2026-05-11 新增修复

1. _current_task_id ContextVar 替代构造函数task_id

作者：小健
创建时间：2026-05-11
"""

import pytest
from contextvars import ContextVar
from app.services.tools.file.file_tools import _current_task_id
from app.services.tools.file.file_tools import FileTools, _current_task_id


# =====================================================================
# 测试1: _current_task_id ContextVar
# =====================================================================

class TestCurrentTaskIdContextVar:
    """测试_current_task_id ContextVar行为"""

    def test_default_is_none(self):
        """TC-CTXVAR-001: 默认值为None"""
        assert _current_task_id.get(None) is None

    def test_set_and_get(self):
        """TC-CTXVAR-002: set/get正常工作"""
        token = _current_task_id.set("task-abc-123")
        assert _current_task_id.get() == "task-abc-123"
        _current_task_id.reset(token)

    def test_reset_restores_none(self):
        """TC-CTXVAR-003: reset恢复None"""
        token = _current_task_id.set("task-xyz")
        _current_task_id.reset(token)
        assert _current_task_id.get(None) is None

    def test_contextvar_type(self):
        """TC-CTXVAR-004: _current_task_id是ContextVar实例"""
        assert isinstance(_current_task_id, ContextVar)

    def test_filetools_init_uses_contextvar(self):
        """TC-CTXVAR-005: FileTools.__init__使用_current_task_id.get()作为fallback"""
        token = _current_task_id.set("ctx-task-999")
        try:
            ft = FileTools()
            assert ft.task_id == "ctx-task-999"
        finally:
            _current_task_id.reset(token)

    def test_filetools_init_explicit_task_id_overrides(self):
        """TC-CTXVAR-006: 显式task_id优先于ContextVar"""
        token = _current_task_id.set("ctx-task-888")
        try:
            ft = FileTools(task_id="explicit-task-777")
            assert ft.task_id == "explicit-task-777"
        finally:
            _current_task_id.reset(token)


