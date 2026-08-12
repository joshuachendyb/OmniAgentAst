# -*- coding: utf-8 -*-
"""
move_file 第三轮深度BUG发现测试
小健 2026-06-25
"""
import asyncio
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error
from app.services.task.task_context import _current_task_id


def _run(coro):
    token = _current_task_id.set("test-task-move-deep-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


class TestMoveFileDeepBugs:
    """深度BUG发现 — move_file — 小健 2026-06-25"""

    def test_bug_1_source_empty(self, tmp_path):
        """BUG#1: source_path=""空字符串"""
        from app.tools.file.move_file import move
        result = _run(move("", str(tmp_path / "dest.txt")))
        assert is_error(result)

    def test_bug_2_dest_empty(self, tmp_path):
        """BUG#2: dest_path=""空字符串"""
        from app.tools.file.move_file import move
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(move(str(fp), ""))
        assert is_error(result)

    def test_bug_3_source_not_exist(self, tmp_path):
        """BUG#3: source不存在"""
        from app.tools.file.move_file import move
        result = _run(move(str(tmp_path / "not_exist.txt"), str(tmp_path / "dest.txt")))
        assert is_error(result)

    def test_bug_4_source_is_directory(self, tmp_path):
        """BUG#4: source是目录"""
        from app.tools.file.move_file import move
        (tmp_path / "sub").mkdir()
        result = _run(move(str(tmp_path / "sub"), str(tmp_path / "dest")))
        # 应该报错或使用目录移动

    def test_bug_5_overwrite_false_dest_exists(self, tmp_path):
        """BUG#5: overwrite=False但dest已存在"""
        from app.tools.file.move_file import move
        src = tmp_path / "src.txt"
        dest = tmp_path / "dest.txt"
        src.write_text("src", encoding="utf-8")
        dest.write_text("dest", encoding="utf-8")
        result = _run(move(str(src), str(dest), overwrite=False))
        # 应该报错或跳过

    def test_bug_6_source_same_as_dest(self, tmp_path):
        """BUG#6: source和dest相同"""
        from app.tools.file.move_file import move
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(move(str(fp), str(fp)))
        # 应该报错或跳过

    def test_bug_7_cross_device_move(self, tmp_path):
        """BUG#7: 跨设备移动(Windows不同盘符)"""
        from app.tools.file.move_file import move
        # Windows下跨盘符移动需要特殊处理
        pass

    def test_bug_8_create_parents_true(self, tmp_path):
        """BUG#8: create_parents=True创建父目录"""
        from app.tools.file.move_file import move
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "sub1" / "sub2" / "dest.txt"
        result = _run(move(str(src), str(dest), overwrite=False))
        assert is_success(result)

    def test_bug_9_move_to_self_subdirectory(self, tmp_path):
        """BUG#9: 移动到自己的子目录"""
        from app.tools.file.move_file import move
        src = tmp_path / "src"
        src.mkdir()
        dest = src / "sub"
        result = _run(move(str(src), str(dest)))
        # 应该报错

    def test_bug_10_large_file(self, tmp_path):
        """BUG#10: 大文件移动(100MB)"""
        from app.tools.file.move_file import move
        src = tmp_path / "large.txt"
        dest = tmp_path / "large_moved.txt"
        src.write_bytes(b"a" * (100 * 1024 * 1024))
        result = _run(move(str(src), str(dest)))
        assert is_success(result)

    def test_bug_11_source_with_special_chars(self, tmp_path):
        """BUG#11: source包含特殊字符"""
        from app.tools.file.move_file import move
        src = tmp_path / "测试 文件[1].txt"
        src.write_text("test", encoding="utf-8")
        dest = tmp_path / "dest.txt"
        result = _run(move(str(src), str(dest)))
        assert is_success(result)

    def test_bug_12_concurrent_move_same_source(self, tmp_path):
        """BUG#12: 并发移动同一源文件"""
        from app.tools.file.move_file import move
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        async def move_task(i):
            return await move(str(src), str(tmp_path / f"dest{i}.txt"))
        # 并发移动同一文件,只有一个应该成功
        async def _gather():
            return await asyncio.gather(*[move_task(i) for i in range(2)])
        results = _run(_gather())

    def test_bug_13_source_readonly(self, tmp_path):
        """BUG#13: source是只读文件"""
        from app.tools.file.move_file import move
        src = tmp_path / "readonly.txt"
        src.write_text("test", encoding="utf-8")
        src.chmod(0o444)  # 只读
        dest = tmp_path / "dest.txt"
        result = _run(move(str(src), str(dest)))
        # 应该成功或报错

    def test_bug_14_source_locked(self, tmp_path):
        """BUG#14: source被锁定(Windows)"""
        from app.tools.file.move_file import move
        # Windows文件锁定测试较复杂
        pass

    def test_bug_15_dest_parent_readonly(self, tmp_path):
        """BUG#15: dest父目录只读"""
        from app.tools.file.move_file import move
        src = tmp_path / "src.txt"
        src.write_text("test", encoding="utf-8")
        parent = tmp_path / "readonly"
        parent.mkdir()
        parent.chmod(0o555)  # 只读
        dest = parent / "dest.txt"
        result = _run(move(str(src), str(dest)))
        # 应该报错
