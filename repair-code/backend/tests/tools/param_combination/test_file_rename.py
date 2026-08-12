# -*- coding: utf-8 -*-
"""rename参数组合测试 - 小欧 2026-07-04

测试重命名工具schema验证、错误路径
注意：rename需要会话ID，实际重命名操作会失败
"""

import asyncio
import os
import pytest
from pydantic import ValidationError
from app.tools.file.rename_file import rename
from app.tools.file.file_schema import RenameInput
from app.tools.tool_response import is_success, is_error


def _run(coro):
    return asyncio.run(coro)


class TestRenameSchema:
    """Schema参数验证"""

    def test_schema_empty_source(self):
        with pytest.raises(ValidationError):
            RenameInput(path="", dest="new.txt")

    def test_schema_empty_destination(self):
        with pytest.raises(ValidationError):
            RenameInput(path="/tmp/test.txt", dest="")

    def test_schema_missing_source(self):
        with pytest.raises(ValidationError):
            RenameInput(dest="new.txt")

    def test_schema_missing_destination(self):
        with pytest.raises(ValidationError):
            RenameInput(path="/tmp/test.txt")

    def test_schema_valid(self):
        inp = RenameInput(path="C:/test.txt", dest="new.txt")
        assert inp.path == "C:/test.txt"
        assert inp.dest == "new.txt"


class TestRenameErrorPath:
    """错误场景（不依赖会话ID）"""

    def test_non_existent_source(self):
        result = _run(rename(path="Z:/non_existent_file_12345.txt", dest="new.txt"))
        assert is_error(result)

    def test_empty_source(self):
        result = _run(rename(path="", dest="new.txt"))
        assert is_error(result)

    def test_empty_destination(self, temp_output_dir):
        src = temp_output_dir / "test.txt"
        src.write_text("test")
        result = _run(rename(path=str(src), dest=""))
        assert is_error(result)
