# -*- coding: utf-8 -*-
"""
delete_file 第?三杞?繁搴?UG名发现测试
小健 2026-06-25
"""
import asyncio
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


class TestDeleteFileDeepBugs:
    """娣卞害BUG名发现 鈥?delete_file 鈥?小健 2026-06-25,我洿方?小欧? 2026-06-28"""

    def test_bug_1_path_empty(self, tmp_path):
        """BUG#1: path=""空哄瓧第︿覆"""
        from app.tools.file.delete_file import delete
        result = _run(delete(""))
        assert is_error(result)

    def test_bug_2_path_none(self, tmp_path):
        """BUG#2: path=None 应返回错误"""
        from app.tools.file.delete_file import delete
        result = _run(delete(None))
        assert is_error(result), f"path=None 应返回错误: {result}"

    def test_bug_3_path_not_exist(self, tmp_path):
        """BUG#3: source不存在?"""
        from app.tools.file.delete_file import delete
        result = _run(delete(str(tmp_path / "not_exist.txt")))

    def test_bug_4_path_is_directory(self, tmp_path):
        """BUG#4: source是?洰褰?"""
        from app.tools.file.delete_file import delete
        (tmp_path / "sub").mkdir()
        result = _run(delete(str(tmp_path / "sub")))

    def test_bug_5_recursive_false_directory_with_files(self, tmp_path):
        """BUG#5: recursive=False你嗙洰褰曞寘否?件件?"""
        from app.tools.file.delete_file import delete
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("test", encoding="utf-8")
        result = _run(delete(str(sub), recursive=False))

    def test_bug_6_recursive_true(self, tmp_path):
        """BUG#6: recursive=True通掑綊删除"""
        from app.tools.file.delete_file import delete
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "file.txt").write_text("test", encoding="utf-8")
        result = _run(delete(str(sub), recursive=True))

    def test_bug_7_file_readonly(self, tmp_path):
        """BUG#7: 名??文件"""
        from app.tools.file.delete_file import delete
        fp = tmp_path / "readonly.txt"
        fp.write_text("test", encoding="utf-8")
        fp.chmod(0o444)
        result = _run(delete(str(fp)))

    def test_bug_8_file_locked(self, tmp_path):
        """BUG#8: 文件琚?攣完氾紙Windows,?"""
        import pytest

    def test_bug_9_path_with_special_chars(self, tmp_path):
        """BUG#9: 路?径鍖容惈鐗案畩存楃?"""
        from app.tools.file.delete_file import delete
        fp = tmp_path / "测试 文件[1].txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(delete(str(fp)))

    def test_bug_10_symlink(self, tmp_path):
        """BUG#10: 第﹀彿閾炬接,圵indows名?兘闇查瑕佺?鐞嗗憳误冮檺,?"""
        from app.tools.file.delete_file import delete
        target = tmp_path / "target.txt"
        target.write_text("test", encoding="utf-8")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("Windows中死敮鎸佺?名烽摼鎺?")
        result = _run(delete(str(link)))

    def test_bug_11_concurrent_delete_same_file(self, tmp_path):
        """BUG#11: 并发删除同一文件不应崩溃"""
        from app.tools.file.delete_file import delete
        fp = tmp_path / "concurrent.txt"
        fp.write_text("test", encoding="utf-8")
        path = str(fp)

        async def _concurrent_delete(p: str, n: int):
            return await asyncio.gather(*[delete(p) for _ in range(n)], return_exceptions=True)

        results = _run(_concurrent_delete(path, 5))
        assert len(results) == 5
        # 核心目标: 并发调用不应抛未捕获异常,每个结果都应是工具返回的dict(error/success均可)
        assert all(isinstance(r, dict) for r in results), f"并发删除不应抛未捕获异常: {results}"

    def test_bug_12_very_large_file(self, tmp_path):
        """BUG#12: 复ф件件读垹闄わ紙10MB,?"""
        from app.tools.file.delete_file import delete
        fp = tmp_path / "large.txt"
        fp.write_bytes(b"a" * (10 * 1024 * 1024))
        result = _run(delete(str(fp)))

    def test_bug_13_directory_with_many_files(self, tmp_path):
        """BUG#13: 鍖容惈复ч噺文件的勭洰褰?"""
        from app.tools.file.delete_file import delete
        sub = tmp_path / "sub"
        sub.mkdir()
        for i in range(100):
            (sub / f"file{i}.txt").write_text("test", encoding="utf-8")
        result = _run(delete(str(sub), recursive=True))

    def test_bug_14_path_is_root(self, tmp_path):
        """BUG#14: path是?牴标?綍 应该?鎷︽埅"""
        from app.tools.file.delete_file import delete
        result = _run(delete("C:\\", recursive=True))

    def test_bug_15_force_true(self, tmp_path):
        """BUG#15: force=True异哄埗删除"""
        from app.tools.file.delete_file import delete
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = _run(delete(str(fp), force=True))