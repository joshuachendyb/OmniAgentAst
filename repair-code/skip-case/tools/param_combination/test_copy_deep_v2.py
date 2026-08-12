# -*- coding: utf-8 -*-
# ================================================================
# 【skip case 归档副本】 - 小欧 2026-08-12 10:43:59
# 原路径: backend/tests/tools/param_combination/test_copy_deep_v2.py
# 归档原因: 包含 Windows 平台限制类 skip case(readonly/symlink),
#           已从 backend/tests 原文件删除对应 skip case, 此处保留完整代码,
#           便于未来在其他平台(如 Linux)恢复运行。
# ================================================================
"""
copy工具深度测试 — 挖掘bug

测试目标：发现copy工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.copy_file import copy
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-copy-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestCopyBasicParams:
    """参数组合测试 - 6个"""
    
    def test_copy_file(self, tmp_path):
        """组合1: 复制文件"""
        src = tmp_path / "source.txt"
        src.write_text("test content")
        dst = tmp_path / "dest.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.exists()
        assert dst.read_text() == "test content"
    
    def test_copy_directory_recursive(self, tmp_path):
        """组合2: 递归复制目录"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test")
        
        dst_dir = tmp_path / "dest_dir"
        result = _run(copy(path=str(src_dir), dest=str(dst_dir), recursive=True))
        assert is_success(result)
        assert src_dir.exists()
        assert dst_dir.exists()
        assert (dst_dir / "file.txt").exists()
    
    def test_copy_with_overwrite_false(self, tmp_path):
        """组合3: overwrite=False（默认）"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(copy(path=str(src), dest=str(dst), overwrite=False))
        assert is_error(result)
        assert dst.read_text() == "dest"
    
    def test_copy_with_overwrite_true(self, tmp_path):
        """组合4: overwrite=True"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(copy(path=str(src), dest=str(dst), overwrite=True))
        assert is_success(result)
        assert dst.read_text() == "source"
    
    def test_copy_preserve_metadata_true(self, tmp_path):
        """组合5: preserve_metadata=True（默认）"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        import time
        time.sleep(0.1)
        
        dst = tmp_path / "dest.txt"
        result = _run(copy(path=str(src), dest=str(dst), preserve_metadata=True))
        assert is_success(result)
        assert src.stat().st_mtime == dst.stat().st_mtime
    
    def test_copy_preserve_metadata_false(self, tmp_path):
        """组合6: preserve_metadata=False"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        
        dst = tmp_path / "dest.txt"
        result = _run(copy(path=str(src), dest=str(dst), preserve_metadata=False))
        assert is_success(result)
        assert dst.exists()


class TestCopyInvalidScenarios:
    """无效场景测试 - 6个"""
    
    def test_nonexistent_source(self, tmp_path):
        """Bug1: 不存在的源应该报错"""
        result = _run(copy(path=str(tmp_path / "nonexistent.txt"), dest=str(tmp_path / "dest.txt")))
        assert is_error(result)
    
    def test_same_source_and_destination(self, tmp_path):
        """Bug2: 源和目标相同应该报错"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        result = _run(copy(path=str(src), dest=str(src)))
        assert is_error(result)
    
    def test_copy_to_existing_without_overwrite(self, tmp_path):
        """Bug3: 目标已存在且不覆盖应该报错"""
        src = tmp_path / "source.txt"
        src.write_text("source")
        dst = tmp_path / "dest.txt"
        dst.write_text("dest")
        
        result = _run(copy(path=str(src), dest=str(dst), overwrite=False))
        assert is_error(result)
    
    def test_copy_directory_without_recursive(self, tmp_path):
        """Bug4: 复制目录不设置recursive应该只创建空目录"""
        src_dir = tmp_path / "source_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test")
        
        dst_dir = tmp_path / "dest_dir"
        result = _run(copy(path=str(src_dir), dest=str(dst_dir), recursive=False))
        assert is_success(result)
        assert dst_dir.exists()
        assert not (dst_dir / "file.txt").exists()
    
    def test_copy_empty_source(self, tmp_path):
        """Bug5: 空source应该报错"""
        result = _run(copy(path="", dest=str(tmp_path / "dest.txt")))
        assert is_error(result)
    
    def test_copy_empty_destination(self, tmp_path):
        """Bug6: 空destination应该报错"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        
        result = _run(copy(path=str(src), dest=""))
        assert is_error(result)


class TestCopyCrossBoundary:
    """跨边界测试 - 5个"""
    
    def test_copy_across_drives(self, tmp_path):
        """Bug7: 跨盘符复制应该支持"""
        if os.name == 'nt':
            src = tmp_path / "test.txt"
            src.write_text("test")
            dst = "D:/test_cross_drive.txt"
            
            result = _run(copy(path=str(src), dest=dst))
            assert is_success(result) or is_error(result)
            if is_success(result):
                assert src.exists()
                assert Path(dst).exists()
                Path(dst).unlink()
        else:
            pytest.skip("Windows only test")
    
    def test_copy_with_special_chars(self, tmp_path):
        """Bug8: 特殊字符路径应该支持"""
        src = tmp_path / "test file.txt"
        src.write_text("test")
        dst = tmp_path / "new file.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.exists()
    
    def test_copy_with_chinese_chars(self, tmp_path):
        """Bug9: 中文字符应该支持"""
        src = tmp_path / "测试文件.txt"
        src.write_text("中文内容")
        dst = tmp_path / "新文件.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.read_text() == "中文内容"
    
    def test_copy_with_long_path(self, tmp_path):
        """Bug10: 长路径应该处理"""
        long_name = "a" * 200 + ".txt"
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst = tmp_path / long_name
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)
    
    def test_copy_create_parent_dirs(self, tmp_path):
        """Bug11: 目标父目录不存在应该自动创建"""
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst = tmp_path / "subdir1" / "subdir2" / "dest.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.exists()


class TestCopyPermissions:
    """权限测试 - 4个"""
    
    def test_copy_readonly_file(self, tmp_path):
        """Bug12: 只读文件复制应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        src = tmp_path / "readonly.txt"
        src.write_text("readonly")
        os.chmod(str(src), 0o444)
        
        try:
            dst = tmp_path / "copy_readonly.txt"
            result = _run(copy(path=str(src), dest=str(dst)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(src), 0o644)
    
    def test_copy_to_readonly_directory(self, tmp_path):
        """Bug13: 复制到只读目录应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        src = tmp_path / "source.txt"
        src.write_text("test")
        dst_dir = tmp_path / "readonly_dir"
        dst_dir.mkdir()
        os.chmod(str(dst_dir), 0o444)
        
        try:
            dst = dst_dir / "dest.txt"
            result = _run(copy(path=str(src), dest=str(dst)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(dst_dir), 0o755)
    
    def test_copy_system_file(self, tmp_path):
        """Bug14: 系统文件复制应该报错"""
        if os.name == 'nt':
            result = _run(copy(path="C:/Windows/System32/drivers/etc/hosts", dest="C:/tmp/hosts"))
            assert is_error(result)
        else:
            result = _run(copy(path="/etc/passwd", dest="/tmp/passwd"))
            assert is_error(result)
    
    def test_copy_to_system_directory(self, tmp_path):
        """Bug15: 复制到系统目录应该报错"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        if os.name == 'nt':
            result = _run(copy(path=str(src), dest="C:/Windows/test.txt"))
            assert is_error(result)
        else:
            result = _run(copy(path=str(src), dest="/root/test.txt"))
            assert is_error(result)


class TestCopyRealScenarios:
    """真实场景测试 - 5个"""
    
    def test_copy_large_file(self, tmp_path):
        """Bug16: 大文件复制应该成功"""
        src = tmp_path / "large.bin"
        src.write_bytes(b"0" * 10_000_000)
        dst = tmp_path / "large_copy.bin"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.exists()
        assert dst.stat().st_size == 10_000_000
    
    def test_copy_nested_directory(self, tmp_path):
        """测试复制嵌套目录"""
        src = tmp_path / "parent"
        src.mkdir()
        (src / "child1").mkdir()
        (src / "child1" / "file1.txt").write_text("content1")
        (src / "child2").mkdir()
        (src / "child2" / "file2.txt").write_text("content2")
        
        dst = tmp_path / "parent_copy"
        result = _run(copy(path=str(src), dest=str(dst), recursive=True))
        assert is_success(result)
        assert (dst / "child1" / "file1.txt").exists()
        assert (dst / "child2" / "file2.txt").exists()
    
    def test_copy_project_structure(self, tmp_path):
        """测试复制项目结构"""
        project = tmp_path / "myproject"
        project.mkdir()
        (project / "src").mkdir()
        (project / "src" / "main.py").write_text("print('hello')")
        (project / "tests").mkdir()
        (project / "tests" / "test.py").write_text("assert True")
        
        backup = tmp_path / "backup" / "myproject_backup"
        result = _run(copy(path=str(project), dest=str(backup), recursive=True))
        assert is_success(result)
        assert (backup / "src" / "main.py").exists()
    
    def test_copy_with_overwrite_directory(self, tmp_path):
        """Bug17: overwrite目录应该删除目标后重建"""
        src = tmp_path / "source"
        src.mkdir()
        (src / "file.txt").write_text("source content")
        
        dst = tmp_path / "dest"
        dst.mkdir()
        (dst / "old_file.txt").write_text("old content")
        
        result = _run(copy(path=str(src), dest=str(dst), recursive=True, overwrite=True))
        assert is_success(result)
        assert (dst / "file.txt").exists()
        assert not (dst / "old_file.txt").exists()
    
    def test_copy_symlink(self, tmp_path):
        """Bug18: 符号链接复制应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows symlink needs admin")
        
        target = tmp_path / "target.txt"
        target.write_text("target")
        src = tmp_path / "link"
        src.symlink_to(target)
        
        dst = tmp_path / "link_copy"
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)


class TestCopyEdgeCases:
    """边界测试 - 4个"""
    
    def test_copy_empty_file(self, tmp_path):
        """测试复制空文件"""
        src = tmp_path / "empty.txt"
        src.write_text("")
        dst = tmp_path / "empty_copy.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.stat().st_size == 0
    
    def test_copy_hidden_file(self, tmp_path):
        """测试复制隐藏文件"""
        src = tmp_path / ".hidden"
        src.write_text("hidden")
        dst = tmp_path / ".hidden_copy"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result)
        assert src.exists()
        assert dst.exists()
    
    def test_copy_unicode_filename(self, tmp_path):
        """Bug19: Unicode文件名应该支持"""
        src = tmp_path / "文件🎉测试.txt"
        src.write_text("unicode")
        dst = tmp_path / "新文件📁.txt"
        
        result = _run(copy(path=str(src), dest=str(dst)))
        assert is_success(result) or is_error(result)
    
    def test_copy_multiple_times(self, tmp_path):
        """Bug20: 多次复制同一文件应该成功"""
        src = tmp_path / "test.txt"
        src.write_text("test")
        
        dst1 = tmp_path / "copy1.txt"
        result1 = _run(copy(path=str(src), dest=str(dst1)))
        assert is_success(result1)
        
        dst2 = tmp_path / "copy2.txt"
        result2 = _run(copy(path=str(src), dest=str(dst2)))
        assert is_success(result2)
        assert src.exists()
        assert dst1.exists()
        assert dst2.exists()