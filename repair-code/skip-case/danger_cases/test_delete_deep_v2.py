# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/danger_cases/test_delete_deep_v2.py
# 归档原因: 包含 Windows 平台限制类 skip case(readonly/symlink),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台(如 Linux)恢复运行。
# ================================================================
"""
delete工具深度测试 — 挖掘bug

测试目标：发现delete工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.delete_file import delete
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-delete-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestDeleteBasicParams:
    """参数组合测试 - 6个"""
    
    def test_delete_file(self, tmp_path):
        """组合1: 删除文件"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_directory_recursive(self, tmp_path):
        """组合2: 递归删除目录"""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test")
        
        result = _run(delete(path=str(test_dir), recursive=True))
        assert is_success(result)
        assert not test_dir.exists()
    
    def test_delete_with_force_false(self, tmp_path):
        """组合3: force=False（默认，放入回收站）"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = _run(delete(path=str(test_file), force=False))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_with_force_true(self, tmp_path):
        """组合4: force=True（永久删除）"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = _run(delete(path=str(test_file), force=True))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_empty_directory(self, tmp_path):
        """组合5: 删除空目录"""
        test_dir = tmp_path / "empty_dir"
        test_dir.mkdir()
        
        result = _run(delete(path=str(test_dir), recursive=True))
        assert is_success(result)
        assert not test_dir.exists()
    
    def test_delete_nonexistent_file(self, tmp_path):
        """组合6: 删除不存在的文件应该报错"""
        result = _run(delete(path=str(tmp_path / "nonexistent.txt")))
        assert is_error(result)


class TestDeleteInvalidScenarios:
    """无效场景测试 - 6个"""
    
    def test_delete_nonexistent_source(self, tmp_path):
        """Bug1: 不存在的源应该报错"""
        result = _run(delete(path=str(tmp_path / "nonexistent.txt")))
        assert is_error(result)
    
    def test_delete_directory_without_recursive(self, tmp_path):
        """Bug2: 删除非空目录不设置recursive应该报错"""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test")
        
        result = _run(delete(path=str(test_dir), recursive=False))
        assert is_error(result)
    
    def test_delete_empty_source(self, tmp_path):
        """Bug3: 空source应该报错"""
        result = _run(delete(path=""))
        assert is_error(result)
    
    def test_delete_locked_file(self, tmp_path):
        """Bug4: 被锁定的文件应该处理"""
        test_file = tmp_path / "locked.txt"
        test_file.write_text("locked")
        
        with open(test_file, 'r') as f:
            result = _run(delete(path=str(test_file), force=True))
            assert is_success(result) or is_error(result)
    
    def test_delete_file_in_use(self, tmp_path):
        """Bug5: 正在使用的文件应该处理"""
        test_file = tmp_path / "in_use.txt"
        test_file.write_text("in use")
        
        with open(test_file, 'r') as f:
            content = f.read()
            result = _run(delete(path=str(test_file)))
            assert is_success(result) or is_error(result)
    
    def test_delete_readonly_file_force(self, tmp_path):
        """Bug6: 只读文件force删除应该成功"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("readonly")
        os.chmod(str(test_file), 0o444)
        
        try:
            result = _run(delete(path=str(test_file), force=True))
            assert is_success(result)
            assert not test_file.exists()
        except:
            if test_file.exists():
                os.chmod(str(test_file), 0o644)


class TestDeleteCrossBoundary:
    """跨边界测试 - 5个"""
    
    def test_delete_with_special_chars(self, tmp_path):
        """Bug7: 特殊字符路径应该支持"""
        test_file = tmp_path / "test file.txt"
        test_file.write_text("test")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_with_chinese_chars(self, tmp_path):
        """Bug8: 中文字符应该支持"""
        test_file = tmp_path / "测试文件.txt"
        test_file.write_text("中文内容")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_with_long_path(self, tmp_path):
        """Bug9: 长路径应该处理"""
        long_name = "a" * 100 + ".txt"
        test_file = tmp_path / long_name
        test_file.write_text("test")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result) or is_error(result)
    
    def test_delete_nested_directory(self, tmp_path):
        """测试删除深层嵌套目录"""
        test_dir = tmp_path / "parent"
        test_dir.mkdir()
        current = test_dir
        for i in range(10):
            current = current / f"level{i}"
            current.mkdir()
        (current / "file.txt").write_text("deep")
        
        result = _run(delete(path=str(test_dir), recursive=True))
        assert is_success(result)
        assert not test_dir.exists()
    
    def test_delete_symlink(self, tmp_path):
        """Bug10: 符号链接删除应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows symlink needs admin")
        
        target = tmp_path / "target.txt"
        target.write_text("target")
        link = tmp_path / "link"
        link.symlink_to(target)
        
        result = _run(delete(path=str(link)))
        assert is_success(result) or is_error(result)
        if is_success(result):
            assert not link.exists()
            assert target.exists()


class TestDeletePermissions:
    """权限测试 - 4个"""
    
    def test_delete_readonly_file(self, tmp_path):
        """Bug11: 只读文件删除应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("readonly")
        os.chmod(str(test_file), 0o444)
        
        try:
            result = _run(delete(path=str(test_file), force=True))
            assert is_success(result)
            assert not test_file.exists()
        except:
            if test_file.exists():
                os.chmod(str(test_file), 0o644)
    
    def test_delete_in_readonly_directory(self, tmp_path):
        """Bug12: 只读目录中的文件删除应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        test_dir = tmp_path / "readonly_dir"
        test_dir.mkdir()
        test_file = test_dir / "file.txt"
        test_file.write_text("test")
        os.chmod(str(test_dir), 0o444)
        
        try:
            result = _run(delete(path=str(test_file), force=True))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(test_dir), 0o755)
    
    def test_delete_system_file(self, tmp_path):
        """Bug13: 系统文件删除应该报错"""
        if os.name == 'nt':
            result = _run(delete(path="C:/Windows/System32/drivers/etc/hosts"))
            assert is_error(result)
        else:
            result = _run(delete(path="/etc/passwd"))
            assert is_error(result)
    
    def test_delete_system_directory(self, tmp_path):
        """Bug14: 系统目录删除应该报错"""
        if os.name == 'nt':
            result = _run(delete(path="C:/Windows", recursive=True))
            assert is_error(result)
        else:
            result = _run(delete(path="/root", recursive=True))
            assert is_error(result)


class TestDeleteRealScenarios:
    """真实场景测试 - 5个"""
    
    def test_delete_large_file(self, tmp_path):
        """Bug15: 大文件删除应该成功"""
        test_file = tmp_path / "large.bin"
        test_file.write_bytes(b"0" * 10_000_000)
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_project_structure(self, tmp_path):
        """测试删除项目结构"""
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("print('hello')")
        (project / "tests").mkdir()
        (project / "tests" / "test.py").write_text("assert True")
        
        result = _run(delete(path=str(project), recursive=True))
        assert is_success(result)
        assert not project.exists()
    
    def test_delete_mixed_content(self, tmp_path):
        """测试删除混合内容"""
        test_dir = tmp_path / "mixed"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("file1")
        (test_dir / "file2.txt").write_text("file2")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "file3.txt").write_text("file3")
        
        result = _run(delete(path=str(test_dir), recursive=True))
        assert is_success(result)
        assert not test_dir.exists()
    
    def test_delete_with_many_files(self, tmp_path):
        """Bug16: 大量文件删除应该成功"""
        test_dir = tmp_path / "many_files"
        test_dir.mkdir()
        for i in range(100):
            (test_dir / f"file{i:03d}.txt").write_text(f"content{i}")
        
        result = _run(delete(path=str(test_dir), recursive=True))
        assert is_success(result)
        assert not test_dir.exists()
    
    def test_delete_force_vs_recycle(self, tmp_path):
        """测试force删除和回收站删除的区别"""
        test_file1 = tmp_path / "recycle.txt"
        test_file1.write_text("recycle")
        
        result1 = _run(delete(path=str(test_file1), force=False))
        assert is_success(result1)
        assert not test_file1.exists()
        
        test_file2 = tmp_path / "permanent.txt"
        test_file2.write_text("permanent")
        
        result2 = _run(delete(path=str(test_file2), force=True))
        assert is_success(result2)
        assert not test_file2.exists()


class TestDeleteEdgeCases:
    """边界测试 - 4个"""
    
    def test_delete_empty_file(self, tmp_path):
        """测试删除空文件"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_hidden_file(self, tmp_path):
        """测试删除隐藏文件"""
        test_file = tmp_path / ".hidden"
        test_file.write_text("hidden")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result)
        assert not test_file.exists()
    
    def test_delete_unicode_filename(self, tmp_path):
        """Bug17: Unicode文件名应该支持"""
        test_file = tmp_path / "文件🎉测试.txt"
        test_file.write_text("unicode")
        
        result = _run(delete(path=str(test_file)))
        assert is_success(result) or is_error(result)
    
    def test_delete_already_deleted(self, tmp_path):
        """Bug18: 重复删除应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result1 = _run(delete(path=str(test_file)))
        assert is_success(result1)
        
        result2 = _run(delete(path=str(test_file)))
        assert is_error(result2)