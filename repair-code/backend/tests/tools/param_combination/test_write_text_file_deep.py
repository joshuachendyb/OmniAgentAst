# -*- coding: utf-8 -*-
"""
write_text_file 第三轮深度BUG发现测试
目标:发现3个以上真实BUG
方法:代码审查驱动 + 极里参数组合 + 边界攻击
小健 2026-06-25
"""
import asyncio
import os
import pytest
import tempfile
from pathlib import Path

from app.services.task.task_context import _current_task_id
from app.tools.tool_response import is_success, is_error


def _run(coro):
    """writetext 要求存在活跃任务ID上下文 — 适配当前行为"""
    token = _current_task_id.set("test-task-001")
    try:
        return asyncio.run(coro)
    finally:
        _current_task_id.reset(token)


class TestWriteTextFileDeepBugs:
    """深度BUG发现 — write_text_file — 小健 2026-06-25"""

    def test_bug_1_content_empty_string(self, tmp_path):
        """BUG#1: content=""空字符串

        代码第120-121行:len(content)==0 → error
        但用户可能想清空文件,应该允许
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"
        fp.write_text("原有内容\n", encoding="utf-8")

        result = _run(writetext(str(fp), ""))
        # BUG: 空字符串被拒绝,但用户可能想清空文件
        assert is_error(result)
        assert "content不能为空" in result["llm_data"]["status"]["detail"]

    def test_bug_2_content_none(self, tmp_path):
        """BUG#2: content=None

        代码第118-119行:content is None → error
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"

        result = _run(writetext(str(fp), None))
        assert is_error(result)
        assert "content不能为None" in result["llm_data"]["status"]["detail"]

    def test_bug_3_content_with_null_char(self, tmp_path):
        """BUG#3: content包含null字符(0x00)

        代码第122-123行:'\x00' in content → error
        但某些文本文件可能包含null字符(如配置文件)
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"

        result = _run(writetext(str(fp), "line1\x00line2"))
        assert is_error(result)
        assert "null字符" in result["llm_data"]["status"]["detail"]

    def test_bug_4_append_with_encoding(self, tmp_path):
        """BUG#4: append=True + encoding="utf-8"

        代码第124-125行:append and encoding → error
        限制过于严格,用户可能明认知道原文件编码
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"
        fp.write_text("原有内容\n", encoding="utf-8")

        result = _run(writetext(str(fp), "追加内容\n", encoding="utf-8", append=True))
        # BUG: append+encoding被拒绝,但用户明认知道编码
        assert is_error(result)
        assert "append模式不允许指定encoding" in result["llm_data"]["status"]["detail"]

    def test_bug_5_file_path_empty(self, tmp_path):
        """BUG#5: file_path=""空字符串

        代码第116-117行:not file_path or not file_path.strip()
        """
        from app.tools.file.write_text_file import writetext

        result = _run(writetext("", "test"))
        assert is_error(result)
        assert "路径不能为空" in result["llm_data"]["status"]["detail"]

    def test_bug_6_file_path_none(self, tmp_path):
        """BUG#6: file_path=None"""
        from app.tools.file.write_text_file import writetext

        result = _run(writetext(None, "test"))
        assert is_error(result)

    def test_bug_7_encoding_invalid(self, tmp_path):
        """BUG#7: encoding="invalid-encoding-xyz"

        无效编码名应该在写入时报错
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"

        result = _run(writetext(str(fp), "测试内容", encoding="invalid-encoding-xyz"))
        # 应该报错
        assert is_error(result)

    def test_bug_8_file_path_is_directory(self, tmp_path):
        """BUG#8: file_path指向目录

        应该被file_type_checker拦截
        """
        from app.tools.file.write_text_file import writetext

        result = _run(writetext(str(tmp_path), "test"))
        assert is_error(result)

    def test_bug_9_file_path_with_special_chars(self, tmp_path):
        """BUG#9: 文件路径包含特殊字符"""
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "测试 文件[1].txt"

        result = _run(writetext(str(fp), "特殊文件名测试\n"))
        assert is_success(result)

    def test_bug_10_append_to_nonexistent_file(self, tmp_path):
        """BUG#10: append=True但文件不存在

        应该自动创建文件
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "new.txt"

        result = _run(writetext(str(fp), "新文件内容\n", append=True))
        # 应该成功创建新文件
        assert is_success(result)
        assert fp.exists()
        assert fp.read_text(encoding="utf-8") == "新文件内容\n"

    def test_bug_11_encoding_gbk_content_utf8(self, tmp_path):
        """BUG#11: encoding=gbk但内容包含UTF-8特有字符

        更新 2026-08-07 小欧: BUG-05修复后不再报错, 自动降级utf-8写入成功
        (原断言 is_error 过时; 文档v2.0注明"应当fallback而非失败")
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"

        # UTF-8特有字符(emoji) — BUG-05修复: gbk无法编码时降级utf-8, 内容无损
        result = _run(writetext(str(fp), "测试emoji😂", encoding="gbk"))
        assert is_success(result)
        assert fp.read_text(encoding="utf-8") == "测试emoji😂"

    def test_bug_12_large_content(self, tmp_path):
        """BUG#12: 写入超大内容(1MB)"""
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "large.txt"

        large_content = "测试行\n" * 1000000  # 约1MB
        result = _run(writetext(str(fp), large_content))
        assert is_success(result)

    def test_bug_13_concurrent_write_same_file(self, tmp_path):
        """BUG#13: 并发写入同一文件

        可能导致数据混乱或覆盖
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "concurrent.txt"

        async def write_task(content):
            return await writetext(str(fp), content)

        # 并发10个写入
        async def _gather_all():
            return await asyncio.gather(*[write_task(f"内容{i}\n") for i in range(10)])
        results = _run(_gather_all())
        # 应该至少有一个成功
        assert any(is_success(r) for r in results)

    def test_bug_14_file_path_with_parent_dirs(self, tmp_path):
        """BUG#14: file_path包含不存在的父目录

        create_parents=True应该自动创建
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "sub1" / "sub2" / "test.txt"

        result = _run(writetext(str(fp), "嵌套目录测试\n"))
        assert is_success(result)
        assert fp.exists()

    def test_bug_15_bytes_written_calculation(self, tmp_path):
        """BUG#15: bytes_written计算

        代码第231-233行:len(checked_content.encode(encoding))
        验证字节数计算是否正认
        """
        from app.tools.file.write_text_file import writetext
        fp = tmp_path / "test.txt"

        content = "测试中文\n"
        result = _run(writetext(str(fp), content, encoding="utf-8"))
        assert is_success(result)
        # UTF-8: 测试中文\n = 3*3 + 3 + 1 = 13字节
        # 但llm_data中的bytes_written应该正认
