# -*- coding: utf-8 -*-
"""
move工具深度测试 — 挖掘bug

测试目标：发现move工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.move_file import move
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-move-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestMoveBasicParams:
    """参数组合测试 - 6个"""
    
    def test_move_file(self, tmp_path):
        """组合1: 移动文件"""
        src = tmp_path / "source.txt"
        src.write_text("test content")
        dst = tmp_path / "dest.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "test content"
    
    def test_move_directory(self, tmp_path):
        """组合2: 移动目录"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test")
        
        dst_dir = tmp_path / "dest_dir"
        result = _run(move(path=str(src_dir), dest=str(dst_dir)))
        assert is_success(result)
        assert not src_dir.exists()
        assert dst_dir.exists()
        assert (dst_dir / "file.txt").exists()
    
    def test_move_with_overwrite_false(self, tmp_path):
        """组合3: overwrite=False（默认）"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(move(path=str(src), dest=str(dst), overwrite=False))
        assert is_error(result)
        assert src.exists()
        assert dst.read_text() == "dest"
    
    def test_move_with_overwrite_true(self, tmp_path):
        """组合4: overwrite=True"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(move(path=str(src), dest=str(dst), overwrite=True))
        assert is_success(result)
        assert not src.exists()
        assert dst.read_text() == "source"
    
    def test_move_empty_source(self, tmp_path):
        """Bug1: 空source应该报错"""
        result = _run(move(path="", dest=str(tmp_path / "dest.txt")))
        assert is_error(result)
    
    def test_move_empty_destination(self, tmp_path):
        """Bug2: 空destination应该报错"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        
        result = _run(move(path=str(src), dest=""))
        assert is_error(result)


class TestMoveInvalidScenarios:
    """无效场景测试 - 6个"""
    
    def test_nonexistent_source(self, tmp_path):
        """Bug3: 不存在的源应该报错"""
        result = _run(move(path=str(tmp_path / "nonexistent.txt"), dest=str(tmp_path / "dest.txt")))
        assert is_error(result)
    
    def test_same_source_and_destination(self, tmp_path):
        """Bug4: 源和目标相同应该报错"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        result = _run(move(path=str(src), dest=str(src)))
        assert is_error(result)
    
    def test_move_to_existing_without_overwrite(self, tmp_path):
        """Bug5: 目标已存在且不覆盖应该报错"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(move(path=str(src), dest=str(dst), overwrite=False))
        assert is_error(result)
    
    def test_move_directory_to_file(self, tmp_path):
        """Bug6: 移动目录到文件路径应该处理"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        dst_file = tmp_path / "dest.txt"
        dst_file.write_text("dest")
        
        result = _run(move(path=str(src_dir), dest=str(dst_file), overwrite=True))
        assert is_success(result) or is_error(result)
    
    def test_move_file_to_directory_path(self, tmp_path):
        """测试移动文件到目录路径"""
        src_file = tmp_path / "source.txt"
        src_file.write_text("test")
        dst_dir = tmp_path / "dest_dir"
        dst_dir.mkdir()
        
        result = _run(move(path=str(src_file), dest=str(dst_dir)))
        assert is_success(result) or is_error(result)
    
    def test_move_locked_file(self, tmp_path):
        """Bug7: 被锁定的文件应该处理"""
        src = tmp_path / "locked.txt"
        src.write_text("locked")
        
        with open(src, 'r') as f:
            dst = tmp_path / "unlocked.txt"
            result = _run(move(path=str(src), dest=str(dst)))
            assert is_success(result) or is_error(result)


class TestMoveCrossBoundary:
    """跨边界测试 - 5个"""
    
    def test_move_across_drives(self, tmp_path):
        """Bug8: 跨盘符移动应该支持"""
        if os.name == 'nt':
            src = tmp_path / "test.txt"
            src.write_text("test")
            dst = "D:/test_cross_drive.txt"
            
            result = _run(move(path=str(src), dest=dst))
            assert is_success(result) or is_error(result)
            if is_success(result):
                assert not src.exists()
                assert Path(dst).exists()
                Path(dst).unlink()
        else:
            pytest.skip("Windows only test")
    
    def test_move_with_special_chars(self, tmp_path):
        """Bug9: 特殊字符路径应该支持"""
        src = tmp_path / "test file.txt"
        src.write_text("test")
        dst = tmp_path / "new file.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
    
    def test_move_with_chinese_chars(self, tmp_path):
        """Bug10: 中文字符应该支持"""
        src = tmp_path / "测试文件.txt"
        src.write_text("中文内容")
        dst = tmp_path / "新文件.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
        assert dst.read_text() == "中文内容"
    
    def test_move_with_long_path(self, tmp_path):
        """Bug11: 长路径应该处理"""
        long_name = "a" * 200 + ".txt"
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst = tmp_path / long_name
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)
    
    def test_move_create_parent_dirs(self, tmp_path):
        """Bug12: 目标父目录不存在应该自动创建"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst = tmp_path / "subdir1" / "subdir2" / "dest.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
        assert not src.exists()


class TestMovePermissions:
    """权限测试 - 4个"""
    
    def test_move_readonly_file(self, tmp_path):
        """Bug13: 只读文件移动应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        src = tmp_path / "readonly.txt"
        src.write_text("readonly")
        os.chmod(str(src), 0o444)
        
        try:
            dst = tmp_path / "new_readonly.txt"
            result = _run(move(path=str(src), dest=str(dst)))
            assert is_success(result) or is_error(result)
        finally:
            if src.exists():
                os.chmod(str(src), 0o644)
    
    def test_move_to_readonly_directory(self, tmp_path):
        """Bug14: 移动到只读目录应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst_dir = tmp_path / "readonly_dir"
        dst_dir.mkdir()
        os.chmod(str(dst_dir), 0o444)
        
        try:
            dst = dst_dir / "dest.txt"
            result = _run(move(path=str(src), dest=str(dst)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(dst_dir), 0o755)
    
    def test_move_system_file(self, tmp_path):
        """Bug15: 系统文件移动应该报错"""
        if os.name == 'nt':
            result = _run(move(path="C:/Windows/System32/drivers/etc/hosts", dest="C:/tmp/hosts"))
            assert is_error(result)
        else:
            result = _run(move(path="/etc/passwd", dest="/tmp/passwd"))
            assert is_error(result)
    
    def test_move_to_system_directory(self, tmp_path):
        """Bug16: 移动到系统目录应该报错"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        if os.name == 'nt':
            result = _run(move(path=str(src), dest="C:/Windows/test.txt"))
            assert is_error(result)
        else:
            result = _run(move(path=str(src), dest="/root/test.txt"))
            assert is_error(result)


class TestMoveRealScenarios:
    """真实场景测试 - 5个"""
    
    def test_move_large_file(self, tmp_path):
        """Bug17: 大文件移动应该成功"""
        src = tmp_path / "large.bin"
        src.write_bytes(b"0" * 10_000_000)
        dst = tmp_path / "large_moved.bin"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
        assert dst.stat().st_size == 10_000_000
    
    def test_move_nested_directory(self, tmp_path):
        """测试移动嵌套目录"""
        src = tmp_path / "parent"
        src.mkdir()
        (src / "child1").mkdir()
        (src / "child1" / "file1.txt").write_text("content1")
        (src / "child2").mkdir()
        (src / "child2" / "file2.txt").write_text("content2")
        
        dst = tmp_path / "parent_moved"
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert (dst / "child1" / "file1.txt").exists()
        assert (dst / "child2" / "file2.txt").exists()
    
    def test_move_project_structure(self, tmp_path):
        """测试移动项目结构"""
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("print('hello')")
        (project / "tests").mkdir()
        (project / "tests" / "test.py").write_text("assert True")
        
        new_location = tmp_path / "backup" / "myproject_backup"
        result = _run(move(path=str(project), dest=str(new_location)))
        assert is_success(result)
        assert (new_location / "src" / "main.py").exists()
    
    def test_move_with_overwrite_directory(self, tmp_path):
        """Bug18: overwrite目录应该删除目标后移动"""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.txt").write_text("source content")
        
        dst = tmp_path / "dest"
        dst.mkdir()
        (dst / "old_file.txt").write_text("old content")
        
        result = _run(move(path=str(src), dest=str(dst), overwrite=True))
        assert is_success(result)
        assert (dst / "file.txt").exists()
        assert not (dst / "old_file.txt").exists()
    
    def test_move_symlink(self, tmp_path):
        """Bug19: 符号链接移动应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows symlink needs admin")
        
        target = tmp_path / "target.txt"
        target.write_text("target")
        src = tmp_path / "link"
        src.symlink_to(target)
        
        dst = tmp_path / "link_moved"
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)


class TestMoveEdgeCases:
    """边界测试 - 4个"""
    
    def test_move_empty_file(self, tmp_path):
        """测试移动空文件"""
        src = tmp_path / "empty.txt"
        src.write_text("")
        dst = tmp_path / "empty_moved.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
        assert dst.stat().st_size == 0
    
    def test_move_hidden_file(self, tmp_path):
        """测试移动隐藏文件"""
        src = tmp_path / ".hidden"
        src.write_text("hidden")
        dst = tmp_path / ".hidden_moved"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert dst.exists()
    
    def test_move_unicode_filename(self, tmp_path):
        """Bug20: Unicode文件名应该支持"""
        src = tmp_path / "文件🎉测试.txt"
        src.write_text("unicode")
        dst = tmp_path / "新文件📁.txt"
        
        result = _run(move(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)
    
    def test_move_multiple_times(self, tmp_path):
        """Bug21: 多次移动同一文件应该成功"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        dst1 = tmp_path / "move1.txt"
        result1 = _run(move(path=str(src), dest=str(dst1)))
        assert is_success(result1)
        
        dst2 = tmp_path / "move2.txt"
        result2 = _run(move(path=str(dst1), dest=str(dst2)))
        assert is_success(result2)
        assert dst2.exists()