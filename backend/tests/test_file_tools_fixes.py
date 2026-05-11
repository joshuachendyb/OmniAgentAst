"""
测试 file_tools.py 的 2026-05-11 新增修复

1. _current_task_id ContextVar 替代构造函数task_id
2. _generate_summary tool_name统一(edit_text_file/write_text_file)
3. 死代码分支清理(read_file/glob_files)

作者：小健
创建时间：2026-05-11
"""

import pytest
from contextvars import ContextVar


# =====================================================================
# 测试1: _current_task_id ContextVar
# =====================================================================

class TestCurrentTaskIdContextVar:
    """测试_current_task_id ContextVar行为"""

    def test_default_is_none(self):
        """TC-CTXVAR-001: 默认值为None"""
        from app.services.tools.file.file_tools import _current_task_id
        assert _current_task_id.get(None) is None

    def test_set_and_get(self):
        """TC-CTXVAR-002: set/get正常工作"""
        from app.services.tools.file.file_tools import _current_task_id
        token = _current_task_id.set("task-abc-123")
        assert _current_task_id.get() == "task-abc-123"
        _current_task_id.reset(token)

    def test_reset_restores_none(self):
        """TC-CTXVAR-003: reset恢复None"""
        from app.services.tools.file.file_tools import _current_task_id
        token = _current_task_id.set("task-xyz")
        _current_task_id.reset(token)
        assert _current_task_id.get(None) is None

    def test_contextvar_type(self):
        """TC-CTXVAR-004: _current_task_id是ContextVar实例"""
        from app.services.tools.file.file_tools import _current_task_id
        assert isinstance(_current_task_id, ContextVar)

    def test_filetools_init_uses_contextvar(self):
        """TC-CTXVAR-005: FileTools.__init__使用_current_task_id.get()作为fallback"""
        from app.services.tools.file.file_tools import FileTools, _current_task_id
        token = _current_task_id.set("ctx-task-999")
        try:
            ft = FileTools()
            assert ft.task_id == "ctx-task-999"
        finally:
            _current_task_id.reset(token)

    def test_filetools_init_explicit_task_id_overrides(self):
        """TC-CTXVAR-006: 显式task_id优先于ContextVar"""
        from app.services.tools.file.file_tools import FileTools, _current_task_id
        token = _current_task_id.set("ctx-task-888")
        try:
            ft = FileTools(task_id="explicit-task-777")
            assert ft.task_id == "explicit-task-777"
        finally:
            _current_task_id.reset(token)


# =====================================================================
# 测试2: _generate_summary tool_name统一
# =====================================================================

class TestGenerateSummaryToolNameConsistency:
    """测试_generate_summary的tool_name统一"""

    def test_edit_text_file_summary(self):
        """TC-SUMMARY-001: edit_text_file(新名)生成摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("edit_text_file", {"success": True, "applied_edits": 3, "preview": "diff"})
        assert "3" in result

    def test_edit_text_file_failure_summary(self):
        """TC-SUMMARY-002: edit_text_file失败摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("edit_text_file", {"success": False, "error": "文件不存在"})
        assert "编辑失败" in result

    def test_write_text_file_summary(self):
        """TC-SUMMARY-003: write_text_file(新名)生成摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("write_text_file", {"success": True, "bytes_written": 1024})
        assert "1024" in result

    def test_extract_archive_summary(self):
        """TC-SUMMARY-004: extract_archive新增摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("extract_archive", {"success": True, "output_dir": "/tmp/out", "extracted_files": 5})
        assert "5" in result
        assert "/tmp/out" in result

    def test_get_file_hash_summary(self):
        """TC-SUMMARY-005: get_file_hash新增摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("get_file_hash", {"success": True, "algorithm": "sha256", "file_size": 2048})
        assert "SHA256" in result or "sha256" in result

    def test_old_edit_file_not_matched(self):
        """TC-SUMMARY-006: 旧名edit_file不再匹配编辑摘要"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("edit_file", {"success": True, "applied_edits": 3, "preview": "diff"})
        assert "3" not in result

    def test_old_read_file_branch_removed(self):
        """TC-SUMMARY-007: 已删除read_file分支不再匹配"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("read_file", {"success": True, "content": "hello", "total_lines": 10})
        assert "读取" not in result

    def test_old_glob_files_branch_removed(self):
        """TC-SUMMARY-008: 已删除glob_files分支不再匹配"""
        from app.services.tools.file.file_tools import _generate_summary
        result = _generate_summary("glob_files", {"success": True, "total": 8})
        assert "Glob" not in result
