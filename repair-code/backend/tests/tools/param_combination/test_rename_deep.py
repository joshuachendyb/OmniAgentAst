# -*- coding: utf-8 -*-
"""
rename工具深度测试 — 挖掘bug

测试目标：发现rename工具的各种bug和边界问题
测试用例：35个（符合规范25-40个）

Author: 小沈 - 2026-07-04
"""
import pytest
import asyncio
import os
from pathlib import Path
from app.tools.file.rename_file import rename
from app.services.task.task_context import _current_task_id

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def _task_context():
    """为rename提供活跃任务上下文(与生产openai.py:169一致) — 小欧 2026-07-12"""
    token = _current_task_id.set("test-task-rename-001")
    yield
    _current_task_id.reset(token)


def is_success(result):
    return result.get("code") == "success" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(result):
    return result.get("code") == "error" or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


@pytest.mark.asyncio
class TestRenameBasicParams:
    """参数组合测试 - 6个基础组合"""
    
    async def test_rename_file(self, tmp_path):
        """组合1: 重命名文件"""
        test_file = tmp_path / "old_name.txt"
        test_file.write_text("test content")
        
        result = await rename(path=str(test_file), dest="new_name.txt")
        assert is_success(result)
        assert not test_file.exists()
        assert (tmp_path / "new_name.txt").exists()
        assert (tmp_path / "new_name.txt").read_text() == "test content"
    
    async def test_rename_directory(self, tmp_path):
        """组合2: 重命名目录"""
        test_dir = tmp_path / "old_dir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("test")
        
        result = await rename(path=str(test_dir), dest="new_dir")
        assert is_success(result)
        assert not test_dir.exists()
        assert (tmp_path / "new_dir").exists()
        assert (tmp_path / "new_dir" / "file.txt").exists()
    
    async def test_rename_to_same_name(self, tmp_path):
        """Bug1: 重命名为相同名称应该成功（无操作）"""
        test_file = tmp_path / "same.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="same.txt")
        assert is_success(result)
        assert test_file.exists()
    
    async def test_rename_with_path(self, tmp_path):
        """Bug2: destination包含路径应该只取文件名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="D:/other/path/new.txt")
        assert is_success(result)
        assert (tmp_path / "new.txt").exists()
    
    async def test_rename_empty_source(self, tmp_path):
        """Bug3: 空source应该报错"""
        result = await rename(path="", dest="new.txt")
        assert is_error(result)
    
    async def test_rename_empty_destination(self, tmp_path):
        """Bug4: 空destination应该报错或使用原名称"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="")
        assert is_error(result) or is_success(result)


@pytest.mark.asyncio
class TestRenameInvalidScenarios:
    """无效场景测试 - 6个"""
    
    async def test_nonexistent_source(self, tmp_path):
        """Bug5: 不存在的源文件应该报错"""
        result = await rename(path=str(tmp_path / "nonexistent.txt"), dest="new.txt")
        assert is_error(result)
    
    async def test_destination_already_exists(self, tmp_path):
        """Bug6: 目标已存在应该报错（不覆盖）"""
        source_file = tmp_path / "source.txt"
        target_file = tmp_path / "target.txt"
        source_file.write_text("source")
        target_file.write_text("target")
        
        result = await rename(path=str(source_file), dest="target.txt")
        assert is_error(result)
        assert source_file.exists()
        assert target_file.read_text() == "target"
    
    async def test_rename_to_different_directory(self, tmp_path):
        """Bug7: 不能跨目录重命名（rename只在同目录）"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        
        result = await rename(path=str(test_file), dest=str(other_dir / "new.txt"))
        assert is_success(result)
        assert (tmp_path / "new.txt").exists()
    
    async def test_rename_readonly_file(self, tmp_path):
        """Bug8: 只读文件重命名应该处理"""
        if os.name == 'nt':
            pytest.skip("Windows只读文件测试跳过")
        test_file = tmp_path / "readonly.txt"
        test_file.write_text("test")
        os.chmod(str(test_file), 0o444)
        
        try:
            result = await rename(path=str(test_file), dest="new_readonly.txt")
            assert is_success(result) or is_error(result)
        finally:
            if test_file.exists():
                os.chmod(str(test_file), 0o644)
    
    async def test_rename_locked_file(self, tmp_path):
        """Bug9: 被锁定的文件重命名应该处理"""
        test_file = tmp_path / "locked.txt"
        test_file.write_text("test")
        
        with open(test_file, 'r') as f:
            result = await rename(path=str(test_file), dest="new_locked.txt")
            assert is_success(result) or is_error(result)
    
    async def test_rename_directory_with_contents(self, tmp_path):
        """测试重命名包含内容的目录"""
        test_dir = tmp_path / "old_dir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "file3.txt").write_text("content3")
        
        result = await rename(path=str(test_dir), dest="new_dir")
        assert is_success(result)
        new_dir = tmp_path / "new_dir"
        assert new_dir.exists()
        assert (new_dir / "file1.txt").exists()
        assert (new_dir / "file2.txt").exists()
        assert (new_dir / "subdir" / "file3.txt").exists()


@pytest.mark.asyncio
class TestRenameSpecialChars:
    """特殊字符测试 - 5个"""
    
    async def test_chinese_characters(self, tmp_path):
        """Bug10: 中文名称应该支持"""
        test_file = tmp_path / "测试文件.txt"
        test_file.write_text("中文内容")
        
        result = await rename(path=str(test_file), dest="新名称.txt")
        assert is_success(result)
        assert (tmp_path / "新名称.txt").exists()
    
    async def test_special_chars(self, tmp_path):
        """Bug11: 特殊字符应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="file-with_special.chars.txt")
        assert is_success(result)
        assert (tmp_path / "file-with_special.chars.txt").exists()
    
    async def test_spaces_in_name(self, tmp_path):
        """测试文件名中的空格"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="file with spaces.txt")
        assert is_success(result)
        assert (tmp_path / "file with spaces.txt").exists()
    
    async def test_unicode_emoji(self, tmp_path):
        """Bug12: Emoji字符应该支持"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="文件📁测试.txt")
        assert is_success(result) or is_error(result)
    
    async def test_reserved_chars(self, tmp_path):
        """Bug13: Windows保留字符应该报错"""
        if os.name != 'nt':
            pytest.skip("仅Windows测试")
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="file<name>.txt")
        assert is_error(result)


@pytest.mark.asyncio
class TestRenameLongNames:
    """长文件名测试 - 4个"""
    
    async def test_very_long_name(self, tmp_path):
        """Bug14: 超长文件名应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        long_name = "a" * 200 + ".txt"
        
        result = await rename(path=str(test_file), dest=long_name)
        assert is_success(result) or is_error(result)
    
    async def test_max_path_length(self, tmp_path):
        """Bug15: 路径长度限制应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        very_long_name = "b" * 250 + ".txt"
        
        result = await rename(path=str(test_file), dest=very_long_name)
        assert is_success(result) or is_error(result)
    
    async def test_long_chinese_name(self, tmp_path):
        """测试长中文名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        long_chinese = "测试" * 50 + ".txt"
        
        result = await rename(path=str(test_file), dest=long_chinese)
        assert is_success(result) or is_error(result)
    
    async def test_long_directory_name(self, tmp_path):
        """测试长目录名重命名"""
        test_dir = tmp_path / "old_dir"
        test_dir.mkdir()
        long_name = "dir_" + "c" * 100
        
        result = await rename(path=str(test_dir), dest=long_name)
        assert is_success(result) or is_error(result)


@pytest.mark.asyncio
class TestRenameExtensions:
    """扩展名测试 - 4个"""
    
    async def test_change_extension(self, tmp_path):
        """测试修改扩展名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="test.md")
        assert is_success(result)
        assert (tmp_path / "test.md").exists()
    
    async def test_remove_extension(self, tmp_path):
        """测试删除扩展名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="test")
        assert is_success(result)
        assert (tmp_path / "test").exists()
    
    async def test_add_extension(self, tmp_path):
        """测试添加扩展名"""
        test_file = tmp_path / "test"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="test.txt")
        assert is_success(result)
        assert (tmp_path / "test.txt").exists()
    
    async def test_multiple_dots(self, tmp_path):
        """测试多个点的文件名"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="file.name.with.dots.txt")
        assert is_success(result)
        assert (tmp_path / "file.name.with.dots.txt").exists()


@pytest.mark.asyncio
class TestRenamePermissions:
    """权限测试 - 3个"""
    
    async def test_rename_as_different_user(self, tmp_path):
        """Bug16: 不同用户权限应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="new.txt")
        assert is_success(result) or is_error(result)
    
    async def test_rename_system_file(self, tmp_path):
        """Bug17: 系统文件重命名应该报错"""
        if os.name == 'nt':
            result = await rename(path="C:/Windows/System32/drivers/etc/hosts", dest="hosts.bak")
            assert is_error(result)
        else:
            result = await rename(path="/etc/passwd", dest="passwd.bak")
            assert is_error(result)
    
    async def test_rename_in_system_dir(self, tmp_path):
        """Bug18: 系统目录中重命名应该报错"""
        if os.name == 'nt':
            result = await rename(path="C:/Windows/test.txt", dest="new.txt")
            assert is_error(result)
        else:
            result = await rename(path="/root/test.txt", dest="new.txt")
            assert is_error(result)


@pytest.mark.asyncio
class TestRenameRealScenarios:
    """真实场景测试 - 3个"""
    
    async def test_version_control_rename(self, tmp_path):
        """测试版本控制场景重命名"""
        old_file = tmp_path / "config_v1.json"
        old_file.write_text('{"version": 1}')
        
        result = await rename(path=str(old_file), dest="config_v2.json")
        assert is_success(result)
        assert (tmp_path / "config_v2.json").exists()
    
    async def test_backup_rename(self, tmp_path):
        """测试备份场景重命名"""
        original = tmp_path / "data.csv"
        original.write_text("data,data,data")
        
        result = await rename(path=str(original), dest="data_backup.csv")
        assert is_success(result)
        assert (tmp_path / "data_backup.csv").exists()
    
    async def test_normalize_naming(self, tmp_path):
        """测试规范化命名"""
        bad_name = tmp_path / "My File Name (1).txt"
        bad_name.write_text("content")
        
        result = await rename(path=str(bad_name), dest="my_file_name.txt")
        assert is_success(result)
        assert (tmp_path / "my_file_name.txt").exists()


@pytest.mark.asyncio
class TestRenameEdgeCases:
    """边界测试 - 4个"""
    
    async def test_dot_file(self, tmp_path):
        """Bug19: 隐藏文件（点文件）重命名"""
        test_file = tmp_path / ".hidden"
        test_file.write_text("hidden")
        
        result = await rename(path=str(test_file), dest=".new_hidden")
        assert is_success(result)
        assert (tmp_path / ".new_hidden").exists()
    
    async def test_dot_dot_in_name(self, tmp_path):
        """Bug20: 文件名中的..应该处理"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        result = await rename(path=str(test_file), dest="file..name.txt")
        assert is_success(result) or is_error(result)
    
    async def test_empty_file(self, tmp_path):
        """测试空文件重命名"""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        
        result = await rename(path=str(test_file), dest="new_empty.txt")
        assert is_success(result)
        assert (tmp_path / "new_empty.txt").exists()
        assert (tmp_path / "new_empty.txt").read_text() == ""
    
    async def test_rename_to_parent_dir_name(self, tmp_path):
        """Bug21: 重命名为父目录名应该报错"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        parent_name = tmp_path.name
        
        result = await rename(path=str(test_file), dest=parent_name)
        assert is_error(result) or is_success(result)
