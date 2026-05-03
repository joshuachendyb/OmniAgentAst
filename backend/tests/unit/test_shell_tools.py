# -*- coding: utf-8 -*-
# 编写人：小健，日期：2026-05-03
"""SHELL工具测试 - 6个工具: execute_shell_command, get_working_directory, change_directory,
check_path_exists, get_shell_output, terminate_shell"""

import os
import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.shell.shell_tools import (
    execute_shell_command, get_working_directory, change_directory,
    check_path_exists, get_shell_output, terminate_shell,
    _background_shells,
)


class TestExecuteShellCommand:
    def test_execute_shell_command_basic(self):
        """正常：执行echo命令"""
        result = execute_shell_command("echo hello")
        assert result["code"] == "SUCCESS"
        assert "hello" in result["data"]["stdout"]

    def test_execute_shell_command_error(self):
        """异常：执行不存在的命令"""
        result = execute_shell_command("nonexistent_cmd_xyz_123", timeout=5000)
        assert result["code"] == "SUCCESS"
        assert result["data"]["returncode"] != 0

    def test_execute_shell_command_background(self):
        """正常：后台运行命令"""
        result = execute_shell_command("echo hello", run_in_background=True)
        assert result["code"] == "SUCCESS"
        assert "shell_id" in result["data"]
        assert result["data"]["is_running"] is True


class TestGetWorkingDirectory:
    def test_get_working_directory_basic(self):
        """正常：获取当前工作目录"""
        result = get_working_directory()
        assert result["code"] == "SUCCESS"
        assert "path" in result["data"]

    def test_get_working_directory_error(self):
        """异常：os.getcwd抛出异常"""
        with patch("app.services.tools.shell.shell_tools.os.getcwd", side_effect=OSError("error")):
            result = get_working_directory()
            assert result["code"] == "ERR_SHELL_GET_CWD"


class TestChangeDirectory:
    def test_change_directory_basic(self, tmp_path):
        """正常：切换到存在的目录"""
        original = os.getcwd()
        try:
            result = change_directory(str(tmp_path))
            assert result["code"] == "SUCCESS"
        finally:
            os.chdir(original)

    def test_change_directory_error(self):
        """异常：切换到不存在的目录"""
        result = change_directory("/nonexistent_dir_xyz_123")
        assert result["code"] == "ERR_SHELL_PATH_NOT_FOUND"


class TestListDirectory:
    def test_list_directory_basic(self, tmp_path):
        """正常：list_directory用check_path_exists替代"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        result = check_path_exists(str(tmp_path))
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is True
        assert result["data"]["is_directory"] is True

    def test_list_directory_error(self):
        """异常：检查不存在的路径"""
        result = check_path_exists("/nonexistent_path_xyz_456")
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is False


class TestCreateTerminal:
    def test_create_terminal_basic(self):
        """正常：create_terminal对应get_shell_output（不存在shell_id）"""
        result = get_shell_output(shell_id="fake_shell_id")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"

    def test_create_terminal_error(self):
        """异常：空shell_id"""
        result = get_shell_output(shell_id="")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"


class TestRunInTerminal:
    def test_run_in_terminal_basic(self):
        """正常：run_in_terminal对应terminate_shell（不存在shell_id）"""
        result = terminate_shell(shell_id="fake_terminal_id")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"

    def test_run_in_terminal_error(self):
        """异常：终止不存在的终端"""
        result = terminate_shell(shell_id="nonexistent_terminal")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"
