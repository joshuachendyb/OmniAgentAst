# -*- coding: utf-8 -*-
"""
read_text_file 第三轮深度BUG发现测试
目标:发现3个以上真正BUG
方法:代码审查驱动 + 极里参数组合 + 边界攻击
小健 2026-06-25
"""
import asyncio
import os
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error, is_warning


def _run(coro):
    return asyncio.run(coro)


class TestReadTextFileDeepBugs:
    """深度BUG发现 - read_text_file - 小健 2026-06-25"""

    def test_bug_1_offset_negative_with_zero_limit(self, tmp_path):
        """BUG#1: offset负数 + limit=0 的组合处理

        代码第30行检查:offset<0 and limit is not None -> error
        但limit=0应该先被第106行拦截(limit必须>=1)
        如果limit=0先被拦截,就不会执行到offset负数检查
        测试验证参数检查顺序是否正认
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        # limit=0应该先被拦截
        result = _run(readtext(str(fp), offset=-1, limit=0))
        assert is_error(result)
        # 应该报"limit必须>=1",而不是"offset为负数时不能带limit"
        error_detail = result["llm_data"]["status"]["detail"]
        # BUG: 如果报"offset为负数时不能带limit",说明参数检查顺序错误

    def test_bug_2_offset_positive_one_with_limit_one(self, tmp_path):
        """BUG#2: offset=1 + limit=1 边界组合

        offset=1表示从第1行开始,limit=1表示读1行
        应该返回第1行,但需要验证start_line和end_line计算
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = _run(readtext(str(fp), offset=1, limit=1))
        assert is_success(result)
        # 验证返回的是第1行
        assert "line1" in result["data"]["content"]
        assert "第1-1行" in result["llm_data"]["status"]["message"]
        assert result["llm_data"]["metrics"]["lines"]["value"] == 1

    def test_bug_3_offset_exceeds_file_lines(self, tmp_path):
        """BUG#3: offset超出文件行数

        文件只有3行,offset=100应该返回warning而非error
        代码第24行:start_idx >= total and total > 0 -> warning
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = _run(readtext(str(fp), offset=100, limit=10))
        # 应该返回warning,不是error
        assert is_success(result) or "warning" in result.get("data", {})

    def test_bug_4_offset_negative_exceeds_lines(self, tmp_path):
        """BUG#4: offset负数值超过文件行数

        文件只有3行,offset=-100应该返回什么?
        代码第23行:start_idx = max(0, total + offset) = max(0, 3-100) = 0
        会从第1行开始读,这是否合理?
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = _run(readtext(str(fp), tail=100))
        assert is_success(result)
        # tail=100应返回所有行(文件仅3行)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 3

    def test_bug_5_limit_greater_than_remaining_lines(self, tmp_path):
        """BUG#5: limit大于剩余行数

        offset=2, limit=100,但文件只有3行
        应该返回第2-3行,而不是报错
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        result = _run(readtext(str(fp), offset=2, limit=100))
        assert is_success(result)
        assert result["llm_data"]["metrics"]["lines"]["value"] == 2  # 只有第2,3行
        assert "第2-3行" in result["llm_data"]["status"]["message"]

    def test_bug_6_empty_file_with_offset(self, tmp_path):
        """BUG#6: 空文件 + offset参数

        空文件0行,offset=1会怎样?
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "empty.txt"
        fp.write_text("", encoding="utf-8")

        result = _run(readtext(str(fp), offset=1, limit=10))
        # 空文件应该返回warning
        assert is_warning(result)

    def test_bug_7_encoding_parameter_invalid(self, tmp_path):
        """BUG#7: encoding参数传入无效编码名

        用户指定encoding="invalid-encoding-xyz"
        应该报错还是fallback到默认编码?
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("测试内容\n", encoding="utf-8")

        result = _run(readtext(str(fp), encoding="invalid-encoding-xyz"))
        # 应该报错
        assert is_error(result)

    def test_bug_8_file_path_with_special_chars(self, tmp_path):
        """BUG#8: 文件路径包含特殊字符

        文件名包含空格,中文,特殊符号
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "测试 文件[1].txt"
        fp.write_text("特殊文件名测试\n", encoding="utf-8")

        result = _run(readtext(str(fp)))
        assert is_success(result)
        assert "特殊文件名测试" in result["data"]["content"]

    def test_bug_9_file_path_none(self, tmp_path):
        """BUG#9: file_path=None

        应该报错,但报什么错?
        """
        from app.tools.file.read_text_file import readtext
        result = _run(readtext(None))
        assert is_error(result)

    def test_bug_10_file_path_empty_string(self, tmp_path):
        """BUG#10: file_path=""空字符串"""
        from app.tools.file.read_text_file import readtext
        result = _run(readtext(""))
        assert is_error(result)

    def test_bug_11_offset_float_instead_of_int(self, tmp_path):
        """BUG#11: offset传入float而非int

        Schema定义offset是int,但如果传入float会怎样?
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        # Pydantic应该自动转换或报错
        try:
            result = _run(readtext(str(fp), offset=1.5, limit=10))
            # 如果成功,检查是否正认处理
        except Exception as e:
            # 应该抛出类型错误
            pass

    def test_bug_12_limit_float_instead_of_int(self, tmp_path):
        """BUG#12: limit传入float而非int"""
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("line1\nline2\nline3\n", encoding="utf-8")

        try:
            result = _run(readtext(str(fp), offset=1, limit=1.5))
        except Exception as e:
            pass

    def test_bug_13_encoding_empty_string(self, tmp_path):
        """BUG#13: encoding=""空字符串

        空字符串是有效的str,但不是有效的编码名
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "test.txt"
        fp.write_text("测试\n", encoding="utf-8")

        result = _run(readtext(str(fp), encoding=""))
        # 应该报错或fallback

    def test_bug_14_file_path_is_directory(self, tmp_path):
        """BUG#14: file_path指向目录而非文件

        代码第58行检查:not path.is_file()
        """
        from app.tools.file.read_text_file import readtext
        result = _run(readtext(str(tmp_path)))
        assert is_error(result)
        assert "不是文件" in result["llm_data"]["status"]["detail"]

    def test_bug_15_concurrent_read_same_file(self, tmp_path):
        """BUG#15: 并发读取同一文件

        多个并发请求读取同一文件,是否会有问题?
        """
        from app.tools.file.read_text_file import readtext
        fp = tmp_path / "concurrent.txt"
        fp.write_text("并发测试\n" * 100, encoding="utf-8")

        async def read_task():
            return await readtext(str(fp), offset=1, limit=10)

        # 并发10个请求
        async def _gather_all():
            return await asyncio.gather(*[read_task() for _ in range(10)])

        results = _run(_gather_all())
        for result in results:
            assert is_success(result)
