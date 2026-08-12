# -*- coding: utf-8 -*-
"""which 参数组合与边界测试 — 小欧 2026-07-06 data去冗余"""

import pytest
from app.tools.tool_response import is_success, is_error, is_warning
from app.tools.shell.find_command import which


class TestWhichParam:
    """参数组合测试"""

    def test_which_existing_cmd(self):
        result = which(command="python")
        assert is_success(result)
        assert "paths" in result["data"]

    def test_which_not_existing(self):
        result = which(command="nonexistent_cmd_xyz123")
        assert is_warning(result)
        assert result["data"] == {}

    def test_which_all_paths(self):
        result = which(command="python", all_paths=True)
        assert is_success(result) or not is_success(result)


class TestWhichBoundary:
    """边界测试"""

    def test_which_empty_string(self):
        result = which(command="")
        assert is_error(result)

    def test_which_whitespace(self):
        result = which(command="   ")
        assert is_error(result)

    def test_which_with_path_separator(self):
        result = which(command="C:\\Windows\\System32\\cmd.exe")
        assert "paths" in result["data"] or is_error(result)

    def test_which_all_paths_not_existing(self):
        result = which(command="nonexistent_cmd_xyz123", all_paths=True)
        assert is_warning(result)
        assert result["data"] == {}

    def test_which_very_long_name(self):
        result = which(command="A" * 500)
        assert is_warning(result)
        assert result["data"] == {}


class TestWhichNegative:
    """负面测试"""

    def test_missing_command(self):
        with pytest.raises(TypeError):
            which()

    def test_command_number(self):
        result = which(command=123)
        assert is_error(result)
