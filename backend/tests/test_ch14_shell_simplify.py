# -*- coding: utf-8 -*-
"""
第14章 Shell分类精简方案 深度测试 - 小健 2026-05-18

覆盖：
- 14.1.2: find_command 合并（check_command_available + locate_command）
- 14.1.3: shell_register.py 双重__all__ Bug修复
- 14.1.3b: shell_session 合并（get_shell_output + terminate_shell）
- 14.1.6: 降级（get_working_directory/change_directory/check_path_exists）
- 14.1.4: Helper层下沉（shell_helper.py）

Author: 小健 - 2026-05-18
"""

import pytest
import sys
import os
import subprocess
import time

sys.path.insert(0, '.')


class TestFindCommand:
    """14.1.2 find_command 合并测试 — 小健 2026-05-18"""

    def test_find_command_all_paths_false_returns_first(self):
        """all_paths=False时应返回第一个匹配路径（原check_command_available行为）"""
        from app.services.tools.shell.shell_tools import find_command
        result = find_command("python", all_paths=False)
        assert result["code"] == "SUCCESS"
        assert result["data"]["available"] is True
        assert result["data"]["path"] is not None
        assert "python" in result["data"]["path"].lower()

    def test_find_command_all_paths_false_not_found(self):
        """all_paths=False时命令不存在应返回available=False"""
        from app.services.tools.shell.shell_tools import find_command
        result = find_command("nonexistent_cmd_xyz_12345", all_paths=False)
        assert result["code"] == "SUCCESS"
        assert result["data"]["available"] is False
        assert result["data"]["path"] is None

    def test_find_command_all_paths_true_returns_all(self):
        """all_paths=True时应返回全部匹配路径（原locate_command行为）"""
        from app.services.tools.shell.shell_tools import find_command
        result = find_command("python", all_paths=True)
        assert result["code"] == "SUCCESS"
        assert isinstance(result["data"]["paths"], list)
        assert result["data"]["count"] >= 1
        assert len(result["data"]["paths"]) == result["data"]["count"]

    def test_find_command_all_paths_true_not_found(self):
        """all_paths=True时命令不存在应返回空列表"""
        from app.services.tools.shell.shell_tools import find_command
        result = find_command("nonexistent_cmd_xyz_12345", all_paths=True)
        assert result["code"] == "SUCCESS"
        assert result["data"]["paths"] == []
        assert result["data"]["count"] == 0

    def test_find_command_default_all_paths_is_false(self):
        """默认all_paths应为False"""
        from app.services.tools.shell.shell_tools import find_command
        result = find_command("python")
        assert "available" in result["data"]

    def test_check_command_available_delegates_to_find_command(self):
        """check_command_available应委托给find_command(all_paths=False)"""
        from app.services.tools.shell.shell_tools import check_command_available, find_command
        r1 = check_command_available("python")
        r2 = find_command("python", all_paths=False)
        assert r1["code"] == r2["code"]
        assert r1["data"]["available"] == r2["data"]["available"]

    def test_locate_command_delegates_to_find_command(self):
        """locate_command应委托给find_command(all_paths=True)"""
        from app.services.tools.shell.shell_tools import locate_command, find_command
        r1 = locate_command("python")
        r2 = find_command("python", all_paths=True)
        assert r1["code"] == r2["code"]
        assert r1["data"]["count"] == r2["data"]["count"]


class TestShellRegisterAllExport:
    """14.1.3 shell_register.py __all__导出严格检查 — 小健 2026-05-18"""

    def test_no_duplicate_all_definition(self):
        """__all__只能定义一次（P0 Bug修复验证）"""
        import ast
        register_path = os.path.join(
            os.path.dirname(__file__),
            "..", "app", "services", "tools", "shell", "shell_register.py"
        )
        register_path = os.path.normpath(register_path)
        with open(register_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        all_assigns = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
        ]
        assert len(all_assigns) == 1, f"__all__定义了{len(all_assigns)}次，应为1次"

    def test_register_all_exact_contents(self):
        """shell_register.__all__必须精确包含新合并工具，不含旧工具"""
        from app.services.tools.shell import shell_register
        expected = ["_register_shell_tools", "execute_shell_command", "find_command", "shell_session"]
        assert shell_register.__all__ == expected, (
            f"shell_register.__all__={shell_register.__all__}, 期望={expected}"
        )

    def test_register_all_no_legacy_tools(self):
        """shell_register.__all__不应含get_shell_output/terminate_shell（已合并为shell_session）"""
        from app.services.tools.shell import shell_register
        assert "get_shell_output" not in shell_register.__all__, "get_shell_output已合并，不应在__all__中"
        assert "terminate_shell" not in shell_register.__all__, "terminate_shell已合并，不应在__all__中"

    def test_register_only_3_llm_tools(self):
        """shell_register只注册3个LLM工具描述（execute_shell_command/find_command/shell_session）"""
        from app.services.tools.shell.shell_register import SHELL_TOOL_DESCRIPTIONS
        expected_keys = {"execute_shell_command", "find_command", "shell_session"}
        assert set(SHELL_TOOL_DESCRIPTIONS.keys()) == expected_keys, (
            f"LLM工具描述={set(SHELL_TOOL_DESCRIPTIONS.keys())}, 期望={expected_keys}"
        )


class TestShellSession:
    """14.1.3b shell_session 合并测试 — 小健 2026-05-18"""

    def test_shell_session_output_delegates_to_get_shell_output(self):
        """action='output'应委托给get_shell_output"""
        from app.services.tools.shell.shell_tools import shell_session, _background_shells
        shell_id = "test_ss_output_001"
        process = subprocess.Popen(
            ["echo", "hello"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        _background_shells[shell_id] = {
            "process": process, "command": "echo hello",
            "started_at": time.time()
        }
        try:
            result = shell_session(shell_id, action="output")
            assert result["code"] == "SUCCESS"
            assert "stdout" in result["data"]
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]

    def test_shell_session_terminate_delegates_to_terminate_shell(self):
        """action='terminate'应委托给terminate_shell"""
        from app.services.tools.shell.shell_tools import shell_session, _background_shells
        shell_id = "test_ss_term_001"
        process = subprocess.Popen(
            ["ping", "-n", "10", "localhost"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        _background_shells[shell_id] = {
            "process": process, "command": "ping -n 10 localhost",
            "started_at": time.time()
        }
        try:
            time.sleep(0.3)
            result = shell_session(shell_id, action="terminate", force=True)
            assert result["code"] == "SUCCESS"
            assert result["data"]["terminated"] is True
            assert shell_id not in _background_shells
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]

    def test_shell_session_default_action_is_output(self):
        """默认action应为'output'"""
        from app.services.tools.shell.shell_tools import shell_session, _background_shells
        shell_id = "test_ss_default_001"
        process = subprocess.Popen(
            ["echo", "test"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        _background_shells[shell_id] = {
            "process": process, "command": "echo test",
            "started_at": time.time()
        }
        try:
            result = shell_session(shell_id)
            assert result["code"] == "SUCCESS"
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]

    def test_shell_session_invalid_action(self):
        """无效action应返回ERR_INVALID_ACTION"""
        from app.services.tools.shell.shell_tools import shell_session, _background_shells
        shell_id = "test_ss_invalid_001"
        process = subprocess.Popen(
            ["echo", "x"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        _background_shells[shell_id] = {
            "process": process, "command": "echo x",
            "started_at": time.time()
        }
        try:
            result = shell_session(shell_id, action="invalid_action")
            assert result["code"] == "ERR_INVALID_ACTION"
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]

    def test_shell_session_output_with_filter(self):
        """action='output'带filter参数应正常过滤"""
        from app.services.tools.shell.shell_tools import shell_session, _background_shells
        shell_id = "test_ss_filter_001"
        process = subprocess.Popen(
            ["echo", "ERROR: fail\nOK: success\nERROR: another"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
        )
        _background_shells[shell_id] = {
            "process": process, "command": "echo test",
            "started_at": time.time()
        }
        try:
            result = shell_session(shell_id, action="output", filter="ERROR")
            assert result["code"] == "SUCCESS"
        finally:
            if shell_id in _background_shells:
                del _background_shells[shell_id]

    def test_shell_session_nonexistent_shell(self):
        """不存在的shell_id应返回ERR_SHELL_NOT_FOUND"""
        from app.services.tools.shell.shell_tools import shell_session
        result = shell_session("nonexistent_shell_xyz", action="output")
        assert result["code"] == "ERR_SHELL_NOT_FOUND"


class TestDemotedTools:
    """14.1.6 降级工具测试 — 小健 2026-05-18"""

    def test_internal_get_working_directory_exists(self):
        """_get_working_directory内部辅助函数应存在且正常工作"""
        from app.services.tools.shell.shell_tools import _get_working_directory
        result = _get_working_directory()
        assert result["code"] == "SUCCESS"
        assert result["data"]["path"] == os.getcwd()

    def test_internal_check_path_exists_exists(self):
        """_check_path_exists内部辅助函数应存在且正常工作"""
        from app.services.tools.shell.shell_tools import _check_path_exists
        result = _check_path_exists(".")
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is True

    def test_internal_check_path_not_exists(self):
        """_check_path_exists对不存在路径应返回exists=False"""
        from app.services.tools.shell.shell_tools import _check_path_exists
        result = _check_path_exists("/nonexistent/path/xyz_12345")
        assert result["code"] == "SUCCESS"
        assert result["data"]["exists"] is False

    def test_get_working_directory_still_callable(self):
        """原get_working_directory仍可调用（兼容保留在shell_tools.py）"""
        from app.services.tools.shell.shell_tools import get_working_directory
        result = get_working_directory()
        assert result["code"] == "SUCCESS"

    def test_change_directory_still_callable(self):
        """原change_directory仍可调用（兼容保留在shell_tools.py）"""
        from app.services.tools.shell.shell_tools import change_directory
        original_cwd = os.getcwd()
        try:
            result = change_directory(original_cwd)
            assert result["code"] == "SUCCESS"
        finally:
            os.chdir(original_cwd)

    def test_check_path_exists_still_callable(self):
        """原check_path_exists仍可调用（兼容保留在shell_tools.py）"""
        from app.services.tools.shell.shell_tools import check_path_exists
        result = check_path_exists(".")
        assert result["code"] == "SUCCESS"

    def test_demoted_tools_not_in_llm_descriptions(self):
        """降级工具不应出现在LLM工具描述中"""
        from app.services.tools.shell.shell_register import SHELL_TOOL_DESCRIPTIONS
        assert "get_working_directory" not in SHELL_TOOL_DESCRIPTIONS
        assert "change_directory" not in SHELL_TOOL_DESCRIPTIONS
        assert "check_path_exists" not in SHELL_TOOL_DESCRIPTIONS

    def test_demoted_schemas_marked_deprecated(self):
        """降级Schema应标注已弃用"""
        from app.services.tools.shell.shell_schema import (
            GetWorkingDirectoryInput, ChangeDirectoryInput, CheckPathExistsInput
        )
        assert "弃用" in GetWorkingDirectoryInput.__doc__
        assert "弃用" in ChangeDirectoryInput.__doc__
        assert "弃用" in CheckPathExistsInput.__doc__


class TestShellHelperMigration:
    """14.1.4 Helper层下沉测试 — 小健 2026-05-18"""

    def test_shell_helper_has_check_shell_injection(self):
        """shell_helper.py应有_check_shell_injection"""
        from app.services.tools.toolhelper.shell_helper import _check_shell_injection
        assert callable(_check_shell_injection)

    def test_shell_helper_has_read_stream_nonblocking(self):
        """shell_helper.py应有_read_stream_nonblocking"""
        from app.services.tools.toolhelper.shell_helper import _read_stream_nonblocking
        assert callable(_read_stream_nonblocking)

    def test_shell_helper_injection_detection(self):
        """shell_helper的注入检测应正确工作"""
        from app.services.tools.toolhelper.shell_helper import _check_shell_injection
        assert _check_shell_injection("$(whoami)") is not None
        assert _check_shell_injection("`id`") is not None
        assert _check_shell_injection("ls -la") is None
        assert _check_shell_injection("") is None

    def test_shell_helper_injection_patterns_same_as_tools(self):
        """shell_helper和shell_tools的注入模式应一致"""
        from app.services.tools.toolhelper.shell_helper import SHELL_INJECTION_PATTERNS as helper_patterns
        from app.services.tools.shell.shell_tools import SHELL_INJECTION_PATTERNS as tools_patterns
        assert len(helper_patterns) == len(tools_patterns)
        for (p1, d1), (p2, d2) in zip(helper_patterns, tools_patterns):
            assert p1 == p2
            assert d1 == d2


class TestShellInitPyAllStrict:
    """shell __init__.py __all__严格导出检查 — 小健 2026-05-18"""

    def test_init_all_exact_contents(self):
        """shell/__init__.py的__all__必须精确包含新工具"""
        from app.services.tools import shell
        expected = ["execute_shell_command", "find_command", "shell_session"]
        assert shell.__all__ == expected, (
            f"shell/__init__.py __all__={shell.__all__}, 期望={expected}"
        )

    def test_init_all_no_legacy_names(self):
        """shell/__init__.py的__all__不应含旧工具名"""
        from app.services.tools import shell
        assert "check_command_available" not in shell.__all__
        assert "locate_command" not in shell.__all__
        assert "get_shell_output" not in shell.__all__
        assert "terminate_shell" not in shell.__all__

    def test_init_all_importable(self):
        """__all__中的名字都能通过from shell import *导入"""
        from app.services.tools.shell import execute_shell_command, find_command, shell_session
        assert callable(execute_shell_command)
        assert callable(find_command)
        assert callable(shell_session)


class TestShellSchemaConsistency:
    """Schema与实现一致性检查 — 小健 2026-05-18"""

    def test_find_command_input_schema(self):
        """FindCommandInput schema字段应与find_command函数参数一致"""
        from app.services.tools.shell.shell_schema import FindCommandInput
        fields = FindCommandInput.model_fields
        assert "command" in fields
        assert "all_paths" in fields
        assert fields["all_paths"].default is False

    def test_shell_session_input_schema(self):
        """ShellSessionInput schema字段应与shell_session函数参数一致"""
        from app.services.tools.shell.shell_schema import ShellSessionInput
        fields = ShellSessionInput.model_fields
        assert "shell_id" in fields
        assert "action" in fields
        assert "filter" in fields
        assert "encoding" in fields
        assert "max_lines" in fields
        assert "tail" in fields
        assert "force" in fields
        assert "cleanup" in fields

    def test_deprecated_schemas_still_importable(self):
        """弃用的Schema仍应可导入（向下兼容）"""
        from app.services.tools.shell.shell_schema import (
            CheckCommandAvailableInput, LocateCommandInput,
            GetShellOutputInput, TerminateShellInput
        )
        assert CheckCommandAvailableInput is not None
        assert LocateCommandInput is not None
        assert GetShellOutputInput is not None
        assert TerminateShellInput is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
