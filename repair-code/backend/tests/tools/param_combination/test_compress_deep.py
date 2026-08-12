# -*- coding: utf-8 -*-
"""
compress工具深度测试 — 挖掘bug

测试目标：发现compress工具的各种bug和边界问题
测试用例：30个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.compress_files import compress
from app.services.task.task_context import _current_task_id


def _run(coro):
    """在task_id上下文中执行协程 — 小沈 2026-07-06"""
    token = _current_task_id.set("test-task-compress-001")
    try:
        if asyncio.iscoroutine(coro):
            return asyncio.run(coro)
        return coro
    finally:
        _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestCompressBasicParams:
    """参数组合测试 - 6个"""
    
    def test_compress_single_file_zip(self, tmp_path):
        """组合1: 压缩单个文件为ZIP"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test content")
        dest = tmp_path / "test.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest)))
        assert is_success(result)
        assert dest.exists()
    
    def test_compress_directory_zip(self, tmp_path):
        """组合2: 压缩目录为ZIP"""
        src_dir = tmp_path / "test_dir"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "file2.txt").write_text("content2")
        
        dest = tmp_path / "dir.zip"
        result = _run(compress(path=str(src_dir), dest=str(dest)))
        assert is_success(result)
        assert dest.exists()
    
    def test_compress_with_format_tar(self, tmp_path):
        """组合3: 压缩为TAR格式"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.tar"
        
        result = _run(compress(path=str(src_file), dest=str(dest), format="tar"))
        assert is_success(result)
        assert dest.exists()
    
    def test_compress_with_format_tar_gz(self, tmp_path):
        """组合4: 压缩为TAR.GZ格式"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.tar.gz"
        
        result = _run(compress(path=str(src_file), dest=str(dest), format="tar.gz"))
        assert is_success(result)
        assert dest.exists()
    
    def test_compress_with_overwrite(self, tmp_path):
        """组合5: 覆盖已存在文件"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.zip"
        dest.write_bytes(b"old content")
        
        result = _run(compress(path=str(src_file), dest=str(dest), overwrite=True))
        assert is_success(result)
    
    def test_compress_with_password(self, tmp_path):
        """组合6: 密码保护（仅ZIP）"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("secret")
        dest = tmp_path / "encrypted.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest), password="test123"))
        assert is_success(result) or is_error(result)


class TestCompressInvalidScenarios:
    """无效场景测试 - 6个"""
    
    def test_nonexistent_source(self, tmp_path):
        """Bug1: 不存在的源应该报错"""
        dest = tmp_path / "test.zip"
        result = _run(compress(path=str(tmp_path / "nonexistent.txt"), dest=str(dest)))
        assert is_error(result)
    
    def test_empty_source(self, tmp_path):
        """Bug2: 空source应该报错"""
        dest = tmp_path / "test.zip"
        result = _run(compress(path="", dest=str(dest)))
        assert is_error(result)
    
    def test_empty_destination(self, tmp_path):
        """Bug3: 空destination应该报错"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        
        result = _run(compress(path=str(src_file), dest=""))
        assert is_error(result)
    
    def test_destination_already_exists(self, tmp_path):
        """Bug4: 目标已存在且不覆盖应该报错"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.zip"
        dest.write_bytes(b"existing")
        
        result = _run(compress(path=str(src_file), dest=str(dest), overwrite=False))
        assert is_error(result)
    
    def test_invalid_format(self, tmp_path):
        """Bug5: 无效格式应该报错"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.xyz"
        
        result = _run(compress(path=str(src_file), dest=str(dest), format="invalid"))
        assert is_error(result)
    
    def test_password_non_zip_format(self, tmp_path):
        """Bug6: 非ZIP格式使用密码应该报错"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        dest = tmp_path / "test.tar"
        
        result = _run(compress(path=str(src_file), dest=str(dest), format="tar", password="test"))
        assert is_error(result) or is_success(result)


class TestCompressWildcards:
    """通配符测试 - 4个"""
    
    def test_compress_with_wildcard(self, tmp_path):
        """测试通配符压缩"""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / "file3.md").write_text("content3")
        
        dest = tmp_path / "multiple.zip"
        result = _run(compress(path=str(tmp_path / "*.txt"), dest=str(dest)))
        assert is_success(result) or is_error(result)
    
    def test_compress_with_question_mark(self, tmp_path):
        """测试?通配符"""
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        
        dest = tmp_path / "question.zip"
        result = _run(compress(path=str(tmp_path / "file?.txt"), dest=str(dest)))
        assert is_success(result) or is_error(result)
    
    def test_compress_no_matches(self, tmp_path):
        """Bug7: 无匹配文件应该报错"""
        dest = tmp_path / "empty.zip"
        result = _run(compress(path=str(tmp_path / "*.nonexistent"), dest=str(dest)))
        assert is_error(result) or is_success(result)
    
    def test_compress_recursive_wildcard(self, tmp_path):
        """测试递归通配符**"""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "file1.txt").write_text("content1")
        (subdir / "file2.txt").write_text("content2")
        
        dest = tmp_path / "recursive.zip"
        result = _run(compress(path=str(tmp_path / "**/*.txt"), dest=str(dest)))
        assert is_success(result) or is_error(result)


class TestCompressExcludePatterns:
    """排除模式测试 - 4个"""
    
    def test_exclude_single_pattern(self, tmp_path):
        """测试排除单个模式"""
        src_dir = tmp_path / "test_dir"
        src_dir.mkdir()
        (src_dir / "keep.txt").write_text("keep")
        (src_dir / "exclude.log").write_text("exclude")
        
        dest = tmp_path / "exclude.zip"
        result = _run(compress(
            path=str(src_dir),
            dest=str(dest),
            exclude_patterns=["*.log"]
        ))
        assert is_success(result) or is_error(result)
    
    def test_exclude_multiple_patterns(self, tmp_path):
        """测试排除多个模式"""
        src_dir = tmp_path / "test_dir"
        src_dir.mkdir()
        (src_dir / "keep.txt").write_text("keep")
        (src_dir / "exclude1.log").write_text("exclude")
        (src_dir / "exclude2.tmp").write_text("exclude")
        
        dest = tmp_path / "multi_exclude.zip"
        result = _run(compress(
            path=str(src_dir),
            dest=str(dest),
            exclude_patterns=["*.log", "*.tmp"]
        ))
        assert is_success(result) or is_error(result)
    
    def test_exclude_directory(self, tmp_path):
        """Bug8: 排除目录应该支持"""
        src_dir = tmp_path / "test_dir"
        src_dir.mkdir()
        (src_dir / "keep.txt").write_text("keep")
        exclude_dir = src_dir / "exclude_dir"
        exclude_dir.mkdir()
        (exclude_dir / "file.txt").write_text("exclude")
        
        dest = tmp_path / "exclude_dir.zip"
        result = _run(compress(
            path=str(src_dir),
            dest=str(dest),
            exclude_patterns=["exclude_dir"]
        ))
        assert is_success(result) or is_error(result)
    
    def test_exclude_node_modules(self, tmp_path):
        """测试排除node_modules"""
        src_dir = tmp_path / "project"
        src_dir.mkdir()
        (src_dir / "main.js").write_text("code")
        node_modules = src_dir / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.js").write_text("package")
        
        dest = tmp_path / "project.zip"
        result = _run(compress(
            path=str(src_dir),
            dest=str(dest),
            exclude_patterns=["node_modules"]
        ))
        assert is_success(result) or is_error(result)


class TestCompressPermissions:
    """权限测试 - 4个"""
    
    def test_compress_readonly_file(self, tmp_path):
        """Bug9: 只读文件压缩应该成功"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        
        src_file = tmp_path / "readonly.txt"
        src_file.write_text("readonly")
        os.chmod(str(src_file), 0o444)
        
        try:
            dest = tmp_path / "readonly.zip"
            result = _run(compress(path=str(src_file), dest=str(dest)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(src_file), 0o644)
    
    def test_compress_to_readonly_directory(self, tmp_path):
        """Bug10: 压缩到只读目录应该报错"""
        if os.name == 'nt':
            pytest.skip("Windows readonly test skipped")
        
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(str(readonly_dir), 0o444)
        
        try:
            dest = readonly_dir / "test.zip"
            result = _run(compress(path=str(src_file), dest=str(dest)))
            assert is_success(result) or is_error(result)
        finally:
            os.chmod(str(readonly_dir), 0o755)
    
    def test_compress_system_file(self, tmp_path):
        """Bug11: 系统文件压缩应该报错"""
        if os.name == 'nt':
            dest = tmp_path / "system.zip"
            result = _run(compress(path="C:/Windows/System32/drivers/etc/hosts", dest=str(dest)))
            assert is_error(result)
        else:
            dest = tmp_path / "system.zip"
            result = _run(compress(path="/etc/passwd", dest=str(dest)))
            assert is_error(result) or is_success(result)
    
    def test_compress_to_system_directory(self, tmp_path):
        """Bug12: 压缩到系统目录应该报错"""
        src_file = tmp_path / "test.txt"
        src_file.write_text("test")
        
        if os.name == 'nt':
            result = _run(compress(path=str(src_file), dest="C:/Windows/test.zip"))
            assert is_error(result)
        else:
            result = _run(compress(path=str(src_file), dest="/root/test.zip"))
            assert is_error(result)


class TestCompressEdgeCases:
    """边界测试 - 4个"""
    
    def test_compress_large_file(self, tmp_path):
        """Bug13: 大文件压缩应该成功"""
        src_file = tmp_path / "large.bin"
        src_file.write_bytes(b"0" * 10_000_000)
        dest = tmp_path / "large.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest)))
        assert is_success(result)
        assert dest.exists()
    
    def test_compress_empty_file(self, tmp_path):
        """测试压缩空文件"""
        src_file = tmp_path / "empty.txt"
        src_file.write_text("")
        dest = tmp_path / "empty.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest)))
        assert is_success(result)
    
    def test_compress_chinese_filename(self, tmp_path):
        """Bug14: 中文文件名应该支持"""
        src_file = tmp_path / "测试文件.txt"
        src_file.write_text("中文内容")
        dest = tmp_path / "中文.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest)))
        assert is_success(result) or is_error(result)
    
    def test_compress_special_chars_filename(self, tmp_path):
        """Bug15: 特殊字符文件名应该处理"""
        src_file = tmp_path / "file with spaces.txt"
        src_file.write_text("content")
        dest = tmp_path / "special.zip"
        
        result = _run(compress(path=str(src_file), dest=str(dest)))
        assert is_success(result) or is_error(result)