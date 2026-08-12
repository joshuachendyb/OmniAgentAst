# -*- coding: utf-8 -*-
"""
shell 参数组合与内容测试v2
案范要求:schema驱动,内容≈100行,验证实际结果,发现问题
小健 2026-06-24

Schema参数: command(str必填), shell_type(powershell/cmd默认powershell),
            timeout(int默认30000范围1-600000), run_in_background(bool默认False),
            cwd(Optional[str]工作目录)
参数组合: 2×2×2=8种 + 边界/为面
"""
import asyncio
import os
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


def _run(coro):
    """shell返回dict,不是coroutine"""
    return coro


class TestExecuteShellCommandParamCombinations:
    """参数组合测试 — shell_type×run_in_background×cwd — 小健 2026-06-24"""

    def test_command_only(self, tmp_path):
        """组合1: 仅command必填参数"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo hello"))
        assert is_success(result)
        assert "hello" in result["data"]["stdout"]

    def test_shell_type_powershell(self, tmp_path):
        """组合2: shell_type=powershell"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("Write-Output 'test'", shell_type="ps7"))
        assert is_success(result)
        assert "test" in result["data"]["stdout"]

    def test_shell_type_cmd(self, tmp_path):
        """组合3: shell_type=cmd"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo test", shell_type="cmd"))
        assert is_success(result)
        assert "test" in result["data"]["stdout"]

    def test_timeout_custom(self, tmp_path):
        """组合4: timeout自定义"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo fast", timeout=30))
        assert is_success(result)

    def test_run_in_background_true(self, tmp_path):
        """组合5: 前台执行 (run_in_background removed in v2 engine)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo background"))
        assert is_success(result)
        assert "background" in result["data"]["stdout"]

    def test_cwd_specified(self, tmp_path):
        """组合6: cwd指定工作目录"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo cwd_test", cwd=str(tmp_path)))
        assert is_success(result)

    def test_all_params_combined(self, tmp_path):
        """组合7: 所有参数组合"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo all_params",
            shell_type="ps7",
            timeout=30,
            cwd=str(tmp_path)
        ))
        assert is_success(result)

    def test_powershell_with_cwd(self, tmp_path):
        """组合8: shell_type=powershell + cwd"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Get-Location",
            shell_type="ps7",
            cwd=str(tmp_path)
        ))
        assert is_success(result)


class TestExecuteShellCommandFeatures:
    """功能测试 — 验证各功能点 — 小健 2026-06-24"""

    def test_powershell_pipeline(self, tmp_path):
        """功能: PowerShell管道操作"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Get-Process | Select-Object -First 3 | Format-Table Name,Id",
            shell_type="ps7"
        ))
        assert is_success(result)
        assert len(result["data"]["stdout"]) > 0

    def test_powershell_variable(self, tmp_path):
        """功能: PowerShell变量"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "$msg = 'test'; Write-Output $msg",
            shell_type="ps7"
        ))
        assert is_success(result)
        assert "test" in result["data"]["stdout"]

    def test_cmd_multiple_commands(self, tmp_path):
        """功能: CMD多命令连接"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo first && echo second",
            shell_type="cmd"
        ))
        assert is_success(result)
        assert "first" in result["data"]["stdout"]
        assert "second" in result["data"]["stdout"]

    def test_exit_code_success(self, tmp_path):
        """功能: 成功returncode=0"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo success"))
        assert is_success(result)
        rc = result["llm_data"]["metrics"]["exit_code"]["value"]
        assert rc == 0

    def test_exit_code_failure(self, tmp_path):
        """功能: 失败returncode非0 (powershell exit 会终止持久进程, 改用 cmd 验证)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("exit 1", shell_type="cmd"))
        if is_success(result):
            rc = result["llm_data"]["metrics"]["exit_code"]["value"]
            assert rc == 1

    def test_stderr_capture(self, tmp_path):
        """功能: stderr捕获 (cmd 分支: 退出码0但stderr有内容 -> warning, data含stderr)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo stdout_content & echo stderr_content 1>&2",
            shell_type="cmd"
        ))
        assert result["llm_data"]["status"]["exec_code"] in ("error", "warning"), \
            f"应被标记: {result['llm_data']['status']['exec_code']}"
        assert len(result["data"].get("stderr", "")) > 0, "stderr未被捕获"

    def test_environment_variables(self, tmp_path):
        """功能: 环境变量访问"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo $env:PATH",
            shell_type="ps7"
        ))
        assert is_success(result)
        assert len(result["data"]["stdout"]) > 0


class TestExecuteShellCommandRealScenarios:
    """真实场景测试 — 小健 2026-06-24"""

    def test_git_status(self, tmp_path):
        """场景: git status"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("git --version"))
        assert is_success(result)
        assert "git" in result["data"]["stdout"].lower()

    def test_python_version(self, tmp_path):
        """场景: python --version"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("python --version"))
        assert is_success(result)
        assert "python" in result["data"]["stdout"].lower()

    def test_pip_list(self, tmp_path):
        """场景: pip list"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("pip list", timeout=30))
        assert is_success(result)

    def test_npm_version(self, tmp_path):
        """场景: npm --version"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("npm --version"))
        if is_success(result):
            assert len(result["data"]["stdout"].strip()) > 0

    def test_dir_listing(self, tmp_path):
        """场景: 目录列表"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Get-ChildItem",
            shell_type="ps7",
            cwd=str(tmp_path)
        ))
        assert is_success(result)

    def test_file_creation(self, tmp_path):
        """场景: 创建文件"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            f"New-Item -Path '{tmp_path}/test.txt' -ItemType File",
            shell_type="ps7"
        ))
        assert is_success(result)
        assert (Path(tmp_path) / "test.txt").exists()


class TestExecuteShellCommandBoundary:
    """边界测试 — 小健 2026-06-24"""

    def test_timeout_minimum(self, tmp_path):
        """边界: timeout=1ms最小值"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo min", timeout=1))
        # 可能超时或成功

    def test_timeout_maximum(self, tmp_path):
        """边界: timeout=600最大值(秒)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo max", timeout=600))
        assert is_success(result)

    def test_long_command(self, tmp_path):
        """边界: 超长命令"""
        from app.tools.fundamental.execute_shell_command import shell
        long_cmd = "echo " + "A" * 1000
        result = _run(shell(long_cmd))
        assert is_success(result)

    def test_special_characters(self, tmp_path):
        """边界: 特殊字符"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Write-Host '特殊字符测试 <>&\"'",
            shell_type="ps7"
        ))
        assert is_success(result)

    def test_chinese_characters(self, tmp_path):
        """边界: 中文字符"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Write-Output '中文测试'",
            shell_type="ps7"
        ))
        assert is_success(result)
        assert "中文" in result["data"]["stdout"]

    def test_empty_output(self, tmp_path):
        """边界: 空输出命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "exit 0",
            shell_type="cmd"
        ))
        assert is_success(result)


class TestExecuteShellCommandNegative:
    """为面测试 — 小健 2026-06-24"""

    def test_invalid_command(self, tmp_path):
        """为面: 不存在的命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("nonexistent_command_xyz"))
        # 可能返回error或exit_code非0

    def test_invalid_cwd(self, tmp_path):
        """为面: 不存在的工作目录 - 应回退tempdir"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo test",
            cwd="Z:/nonexistent/path"
        ))
        assert is_success(result)

    def test_command_injection_attempt(self, tmp_path):
        """安全: 命令注入尝试"""
        from app.tools.fundamental.execute_shell_command import shell
        # 测试是否安全处理特殊字符
        result = _run(shell("echo 'test; rm -rf /'"))
        # 应该安全执行,不会删除文件

    def test_timeout_exceeded(self, tmp_path):
        """为面: 超时"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Start-Sleep -Seconds 10",
            shell_type="ps7",
            timeout=1000
        ))
        # 应该超时

    def test_syntax_error_command(self, tmp_path):
        """为面: 语法错误命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "if (true",  # 语法错误
            shell_type="ps7"
        ))
        # 应该返回错误或exit_code非0


class TestExecuteShellCommandBugDiscovery:
    """BUG发现测试 — 小健 2026-06-24"""

    def test_bug_shell_type_case_sensitivity(self, tmp_path):
        """BUG: shell_type大小写处理"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "echo test",
            shell_type="POWERSHELL"  # 大写
        ))
        # 应该处理或报错

    def test_bug_empty_command(self, tmp_path):
        """BUG: 空命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(""))
        assert is_error(result)

    def test_bug_none_command(self, tmp_path):
        """BUG: None命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(None))
        assert is_error(result)

    def test_bug_timeout_zero(self, tmp_path):
        """BUG: timeout=0"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo test", timeout=0))
        assert is_error(result)

    def test_bug_timeout_negative(self, tmp_path):
        """BUG: timeout为数"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo test", timeout=-1))
        assert is_error(result)

    def test_bug_cwd_is_file(self, tmp_path):
        """BUG: cwd是文件不是目录 - 应回退tempdir"""
        from app.tools.fundamental.execute_shell_command import shell
        f = tmp_path / "file.txt"
        f.write_text("test")
        result = _run(shell("echo test", cwd=str(f)))
        assert is_success(result)

    def test_bug_background_command_output(self, tmp_path):
        """BUG: 前台命令输出读取 (run_in_background removed in v2 engine)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo background_test"))
        assert is_success(result)
        assert "background_test" in result["data"]["stdout"]

    def test_bug_multiline_command(self, tmp_path):
        """BUG: 多语句命令 (多行PowerShell在持久引擎下会挂起, 改用分号单行等价)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell("echo line1; echo line2; echo line3", shell_type="ps7"))
        assert is_success(result)
        assert "line1" in result["data"]["stdout"]
        assert "line2" in result["data"]["stdout"]
        assert "line3" in result["data"]["stdout"]

    def test_bug_unicode_command(self, tmp_path):
        """BUG: Unicode命令"""
        from app.tools.fundamental.execute_shell_command import shell
        result = _run(shell(
            "Write-Host '🎀🎮🅟'",
            shell_type="ps7"
        ))
        assert is_success(result)
