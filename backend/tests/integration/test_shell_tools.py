"""
shell类工具集成测试 - 基于运行中的服务
小健 2026-05-21
"""
import pytest
from tests.integration._helper import ToolClient, assert_success, assert_error, assert_data_key, assert_data_not_empty

TOOL = ToolClient()


class TestExecuteShellCommand:
    """execute_shell_command 多场景测试"""

    def test_simple_echo(self):
        r = TOOL.call("execute_shell_command", {"command": "echo hello", "shell_type": "powershell"})
        assert_success(r)
        data = r.get("data", {})
        output = str(data.get("stdout", "")) + str(data.get("output", ""))
        assert "hello" in output.lower(), f"echo输出应包含hello: {data}"

    def test_dir_command(self):
        r = TOOL.call("execute_shell_command", {"command": "dir", "shell_type": "powershell"})
        assert_success(r)

    def test_timeout_short(self):
        r = TOOL.call("execute_shell_command", {
            "command": "echo fast",
            "shell_type": "powershell",
            "timeout": 5000,
        })
        assert_success(r)

    def test_invalid_command(self):
        r = TOOL.call("execute_shell_command", {
            "command": "nonexistent_command_xyz_12345",
            "shell_type": "powershell",
        })
        assert_error(r)

    def test_with_cwd(self):
        r = TOOL.call("execute_shell_command", {
            "command": "pwd",
            "shell_type": "powershell",
            "cwd": "C:\\",
        })
        assert_success(r)


class TestFindCommand:
    """find_command 多场景测试"""

    def test_find_python(self):
        r = TOOL.call("find_command", {"command": "python"})
        assert_success(r)

    def test_find_nonexistent(self):
        r = TOOL.call("find_command", {"command": "nonexistent_cmd_xyz_12345"})
        assert_success(r)

    def test_find_all_paths(self):
        r = TOOL.call("find_command", {"command": "python", "all_paths": True})
        assert_success(r)


class TestExecutePython:
    """execute_python 多场景测试"""

    def test_simple_print(self):
        r = TOOL.call("execute_python", {"code": "print('hello from python')"})
        assert_success(r)
        data = r.get("data", {})
        output = str(data.get("stdout", "")) + str(data.get("output", ""))
        assert "hello from python" in output, f"python执行输出应包含hello: {data}"

    def test_math_calculation(self):
        r = TOOL.call("execute_python", {"code": "result = 2 + 3; print(result)"})
        assert_success(r)
        data = r.get("data", {})
        output = str(data.get("stdout", "")) + str(data.get("output", ""))
        assert "5" in output, f"2+3应等于5: {data}"

    def test_syntax_error(self):
        r = TOOL.call("execute_python", {"code": "print("})
        assert_error(r)

    def test_with_timeout(self):
        r = TOOL.call("execute_python", {"code": "print('ok')", "timeout": 10})
        assert_success(r)


class TestExecuteJavascript:
    """execute_javascript 多场景测试"""

    def test_simple_console(self):
        r = TOOL.call("execute_javascript", {"code": "console.log('hello from js')"})
        assert_success(r)

    def test_math_calculation(self):
        r = TOOL.call("execute_javascript", {"code": "console.log(2 + 3)"})
        assert_success(r)
        data = r.get("data", {})
        output = str(data.get("stdout", "")) + str(data.get("output", ""))
        assert "5" in output, f"2+3应等于5: {data}"

    def test_syntax_error(self):
        r = TOOL.call("execute_javascript", {"code": "console.log("})
        assert_error(r)
