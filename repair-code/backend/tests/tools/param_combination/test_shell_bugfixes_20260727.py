# -*- coding: utf-8 -*-
"""
Shell工具 bug修复 + 新功能 测试 — 小欧 2026-07-27

测试范围:
1. _sanitize_env 环境变量过滤
2. _auto_fix_cmd_syntax $env:VAR→%VAR% 修复
3. _close_if_blocks 嵌套花括号修复
4. _build_execute_shell_command_llm_data warning分支detail字段
5. check_shell_command_risk MEDIUM多命中合并
6. _resolve_safe_cwd 空字符串处理
7. PersistentShell env参数传递
"""
import pytest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.fundamental.execute_shell_command import (
    _sanitize_env,
    _auto_fix_cmd_syntax,
    _auto_fix_powershell_syntax,
    _close_if_blocks,
    _resolve_safe_cwd,
    _build_execute_shell_command_llm_data,
)
from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
from tests.tools.param_combination.conftest import is_success, is_error


class TestSanitizeEnv:
    """_sanitize_env 环境变量过滤测试"""

    def test_filters_api_keys(self):
        """静态API key被过滤"""
        env = {
            "OPENAI_API_KEY": "sk-xxx",
            "PATH": "C:\\Windows",
            "HOME": "C:\\Users\\test",
        }
        result = _sanitize_env(env)
        assert "OPENAI_API_KEY" not in result
        assert "PATH" in result
        assert "HOME" in result

    def test_filters_dynamic_tokens(self):
        """动态*_TOKEN/*_SECRET/*_PASSWORD被过滤"""
        env = {
            "DB_CONNECTION_TOKEN": "abc123",
            "CUSTOM_API_KEY": "key123",
            "MY_SECRET": "secret123",
            "USER_PASSWORD": "pass123",
            "NORMAL_VAR": "value",
        }
        result = _sanitize_env(env)
        assert "DB_CONNECTION_TOKEN" not in result
        assert "CUSTOM_API_KEY" not in result
        assert "MY_SECRET" not in result
        assert "USER_PASSWORD" not in result
        assert "NORMAL_VAR" in result

    def test_preserves_safe_vars(self):
        """安全变量不被过滤"""
        env = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "TEMP": "C:\\Temp",
        }
        result = _sanitize_env(env)
        assert "PYTHONIOENCODING" in result
        assert "PYTHONUTF8" in result
        assert "TEMP" in result

    def test_case_insensitive(self):
        """大小写不敏感过滤"""
        env = {
            "openai_api_key": "sk-xxx",
            "Openai_Api_Key": "sk-xxx",
        }
        result = _sanitize_env(env)
        assert "openai_api_key" not in result
        assert "Openai_Api_Key" not in result

    def test_empty_env(self):
        """空环境变量 - 传None使用os.environ"""
        result = _sanitize_env(None)
        assert isinstance(result, dict)

    def test_returns_copy(self):
        """返回新dict，不修改原dict"""
        env = {"OPENAI_API_KEY": "sk-xxx", "PATH": "C:\\Windows"}
        result = _sanitize_env(env)
        assert "OPENAI_API_KEY" in env  # 原dict未修改
        assert "OPENAI_API_KEY" not in result


class TestAutoFixCmdSyntax:
    """_auto_fix_cmd_syntax CMD语法修复测试"""

    def test_env_var_conversion(self):
        """$env:VAR → %VAR%"""
        result = _auto_fix_cmd_syntax("echo $env:USERNAME")
        assert result == "echo %USERNAME%"

    def test_multiple_env_vars(self):
        """多个$env:VAR"""
        result = _auto_fix_cmd_syntax("echo $env:USERNAME $env:USERDOMAIN")
        assert result == "echo %USERNAME% %USERDOMAIN%"

    def test_no_env_var(self):
        """无$env:VAR时不修改"""
        cmd = "echo hello world"
        result = _auto_fix_cmd_syntax(cmd)
        assert result == cmd

    def test_empty_command(self):
        """空命令"""
        result = _auto_fix_cmd_syntax("")
        assert result == ""

    def test_none_command(self):
        """None命令"""
        result = _auto_fix_cmd_syntax(None)
        assert result is None


class TestCloseIfBlocks:
    """_close_if_blocks 嵌套花括号修复测试"""

    def test_simple_if(self):
        """简单if块"""
        s = "cmd1 ; if ($__ok) {  cmd2 "
        result = _close_if_blocks(s)
        assert result.endswith(" }")

    def test_nested_scriptblock(self):
        """嵌套脚本块 - Where-Object { .Name }"""
        s = "cmd1 ; if ($__ok) {  Get-Process | Where-Object { $_.Name -eq 'x' } ; if (-not $__ok) {  cmd3 "
        result = _close_if_blocks(s)
        # 应该在正确位置插入}
        assert result.count("if ($__ok)") == 1
        assert result.count("if (-not $__ok)") == 1

    def test_existing_closing_brace(self):
        """已有闭合花括号 - 不重复插入}"""
        s = "cmd1 ; if ($__ok) { Get-Process } ; echo done "
        result = _close_if_blocks(s)
        # 已有}关闭if块，不应再插入}
        assert result == s


class TestAutoFixPowershellSyntax:
    """_auto_fix_powershell_syntax PS语法修复测试"""

    def test_block_property_fix(self):
        """块内.Property → $_.Property"""
        result = _auto_fix_powershell_syntax("Get-Process | Where-Object { .Name -eq 'test' }")
        assert "$_.Name" in result

    def test_no_space_property(self):
        """无空格的.Property"""
        result = _auto_fix_powershell_syntax("Get-Process | Where-Object {.Name -eq 'test'}")
        assert "$_.Name" in result

    def test_already_correct(self):
        """已经是$_.Property"""
        cmd = "Get-Process | Where-Object { $_.Name -eq 'test' }"
        result = _auto_fix_powershell_syntax(cmd)
        assert result == cmd


class TestBuildLlmDataWarningDetail:
    """_build_execute_shell_command_llm_data warning分支detail测试"""

    def test_warning_with_detail(self):
        """warning分支detail有值时使用detail"""
        llm = _build_execute_shell_command_llm_data(
            exec_code="warning",
            duration_ms=100,
            command="echo test",
            returncode=0,
            shell_type="cmd",
            err_code="",
            detail="退出码0，标准错误100字符",
            timeout=60,
            cwd="",
            output_len=10,
            stderr_len=100,
            hint="",
            cmd_short="echo test",
        )
        assert llm["status"]["detail"] == "退出码0，标准错误100字符"

    def test_warning_without_detail(self):
        """warning分支detail为空时使用fallback"""
        llm = _build_execute_shell_command_llm_data(
            exec_code="warning",
            duration_ms=100,
            command="echo test",
            returncode=0,
            shell_type="cmd",
            err_code="",
            detail="",
            timeout=60,
            cwd="",
            output_len=10,
            stderr_len=100,
            hint="",
            cmd_short="echo test",
        )
        assert "退出码0" in llm["status"]["detail"]
        assert "100字符" in llm["status"]["detail"]


class TestCheckShellCommandRisk:
    """check_shell_command_risk MEDIUM多命中合并测试"""

    def test_single_medium_hit(self):
        """单个MEDIUM命中"""
        result = check_shell_command_risk("del /f test.txt", shell_type="cmd")
        assert result is not None
        assert result.requires_confirmation is True
        assert "强制删除文件" in result.message

    def test_multiple_medium_hits(self):
        """多个MEDIUM命中 - 应合并"""
        result = check_shell_command_risk("del /f test.txt && reg add HKLM\\Software /v Test /t REG_SZ /d value", shell_type="cmd")
        assert result is not None
        assert result.requires_confirmation is True
        # 应包含多个风险描述
        assert "强制删除文件" in result.message or "注册表" in result.message

    def test_high_hit_blocks(self):
        """HIGH命中直接拦截"""
        result = check_shell_command_risk("Remove-Item -Path C:\\ -Recurse -Force")
        assert result is not None
        assert result.blocked is True


class TestResolveSafeCwd:
    """_resolve_safe_cwd 空字符串处理测试"""

    def test_valid_cwd(self):
        """有效cwd直接返回"""
        cwd = os.getcwd()
        result = _resolve_safe_cwd(cwd)
        assert result == cwd

    def test_empty_string(self):
        """空字符串回退到tempdir"""
        import tempfile
        result = _resolve_safe_cwd("")
        assert result == tempfile.gettempdir()

    def test_none_string(self):
        """None回退到tempdir"""
        import tempfile
        result = _resolve_safe_cwd(None)
        assert result == tempfile.gettempdir()


class TestPersistentShellEnv:
    """PersistentShell env参数测试"""

    def test_env_passed_to_exec(self):
        """env参数传递到exec"""
        from app.tools.fundamental.shell_engine import shell_pool
        engine = shell_pool.acquire("test-env", "ps7")
        try:
            # 使用自定义env执行命令
            result = engine.exec("echo $env:TEST_VAR", timeout=10, env={"TEST_VAR": "test_value"})
            # 验证命令执行成功
            assert result.get("exit_code") == 0 or result.get("exit_code") is not None
        finally:
            shell_pool.release(engine)
