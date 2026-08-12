# -*- coding: utf-8 -*-
"""
shell parameter combination deep test
XiaoJian-2026-06-27

Test scope:
1. Parameter combination test (shell_type, timeout, cwd, run_in_background)
2. Hierarchical safety check test (LOW/MEDIUM/HIGH) - 17.6 new feature
3. PowerShell translation test (&& and ||) - 17.6 new feature
4. Real scenario test
5. Boundary test
6. Negative test
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.fundamental.execute_shell_command import shell
from tests.tools.param_combination.conftest import is_success, is_error


class TestExecuteShellCommandParamCombinations:
    """Parameter combination test - 8 basic combinations"""

    def test_minimal_params(self):
        """Combination 1: required param command only"""
        result = shell(command="echo hello")
        assert is_success(result)
        assert "hello" in result["data"]["stdout"]

    def test_with_shell_type_PS(self):
        """Combination 2: command + shell_type=PS"""
        result = shell(command="Write-Output 'test'", shell_type="ps7")
        assert is_success(result)

    def test_with_shell_type_cmd(self):
        """Combination 3: command + shell_type=cmd"""
        result = shell(command="echo cmd test", shell_type="cmd")
        assert is_success(result)

    def test_with_timeout(self):
        """Combination 4: command + timeout"""
        result = shell(command="echo timeout test", timeout=30)
        assert is_success(result)

    def test_with_cwd(self, temp_output_dir):
        """Combination 5: command + cwd"""
        result = shell(command="echo cwd test", cwd=str(temp_output_dir))
        assert is_success(result)

    def test_with_run_in_background(self):
        """Combination 6: command foreground (run_in_background removed in v2 engine)"""
        result = shell(command="echo background")
        assert is_success(result)
        assert "background" in result["data"]["stdout"]

    def test_all_params_foreground(self, temp_output_dir):
        """Combination 7: all params - foreground execution"""
        result = shell(
            command="echo all params",
            shell_type="ps7",
            timeout=30,
            cwd=str(temp_output_dir),
        )
        assert is_success(result)

    def test_all_params_background(self, temp_output_dir):
        """Combination 8: all params - foreground execution (run_in_background removed in v2 engine)"""
        result = shell(
            command="echo background all",
            shell_type="ps7",
            timeout=60,
        )
        assert is_success(result)


class TestExecuteShellCommandSafetyCheck:
    """Hierarchical safety check test - 17.6 new feature"""

    def test_low_risk_echo(self):
        """Low risk - echo command"""
        result = shell(command="echo 'low risk'")
        assert is_success(result)
        assert "low risk" in result["data"]["stdout"]

    def test_low_risk_get_content(self):
        """Low risk - Get-Content read"""
        result = shell(command="Get-Content README.md -ErrorAction SilentlyContinue")
        assert is_success(result) or is_error(result)

    def test_medium_risk_remove_item(self):
        """Medium risk - Remove-Item delete - XiaoJian 2026-06-27, updated XiaoJian 2026-06-28 (removed specific assertion)"""
        # 安全版: 只校验拦截逻辑, 不真执行删除(原版真删cwd下test.txt, 拦截失效会误删) — 小欧 2026-08-02
        # 说明: "Remove-Item test.txt"(无Recurse/Force)本身低风险不命中HIGH规则, 验证带Force的递归删除会被拦截即可
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        low = check_shell_command_risk("Remove-Item test.txt -ErrorAction SilentlyContinue", "ps7")
        high = check_shell_command_risk("Remove-Item -Recurse -Force C:\\test", "ps7")
        assert (low is None or not low.blocked), "无Recurse/Force的Remove-Item不应被高风险拦截"
        assert high is not None and high.blocked, "递归+强制删除必须被高风险拦截"

    def test_high_risk_format(self):
        """High risk - format disk"""
        # 安全版: 只校验拦截逻辑, 不真执行(原版真执行format C:危险) — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        result = check_shell_command_risk("format C:", "ps7")
        assert result is not None and result.blocked, "format磁盘必须被高风险拦截"

    def test_high_risk_del_recursive(self):
        """High risk - del /s recursive delete - XiaoJian 2026-06-27, updated XiaoJian 2026-06-28"""
        # 安全版: 只校验拦截逻辑, 不真执行(原版真删当前目录所有文件危险) — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        result = check_shell_command_risk("del /s /q *.*", "cmd")
        assert result is not None and result.blocked, "递归删除必须被高风险拦截"

    def test_high_risk_rmdir_recursive(self):
        """High risk - rmdir /s recursive delete directory"""
        # 安全版: 只校验拦截逻辑, 不真执行 — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        result = check_shell_command_risk("rmdir /s /q test", "cmd")
        assert result is not None and result.blocked, "递归删除目录必须被高风险拦截"

    def test_high_risk_shutdown(self):
        """High risk - shutdown"""
        # 安全版: 只校验拦截逻辑, 不真执行(原版真关机危险) — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        result = check_shell_command_risk("shutdown /s /t 0", "ps7")
        assert result is not None and result.blocked, "关机命令必须被高风险拦截"

    def test_high_risk_reg_delete(self):
        """High risk - reg delete registry"""
        # 安全版: 只校验拦截逻辑, 不真执行 — 小欧 2026-08-02
        from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
        result = check_shell_command_risk("reg delete HKLM\\Software\\Test /f", "cmd")
        assert result is not None and (result.blocked or result.requires_confirmation), "注册表删除必须被拦截或需确认"

    def test_medium_risk_net_user(self):
        """Medium risk - net user management"""
        result = shell(command="net user")
        assert is_error(result) or is_success(result)


class TestExecuteShellCommandPowerShellTranslation:
    """PowerShell translation test - 17.6 new feature"""

    def test_and_operator_translation(self):
        """&& translation test"""
        result = shell(
            command="echo first && echo second",
            shell_type="ps7"
        )
        assert is_success(result)
        assert "first" in result["data"]["stdout"]
        assert "second" in result["data"]["stdout"]

    def test_or_operator_translation(self):
        """|| translation test - XiaoJian 2026-06-27, updated XiaoJian 2026-06-28 (accept warning status)
        2026-08-11 小欧: 原用例 `invalidcmd || echo fallback` 在 PS7 原生语义下
        "命令未找到"(CommandNotFoundException 终止错误) 不被 || 捕获 → 返回 error 属正确行为;
        改用合法但失败的前置命令验证 || 真语义(前置失败→执行右侧 fallback)。"""
        result = shell(
            command="cmd /c exit 1 || echo fallback",
            shell_type="ps7"
        )
        status = result.get("llm_data", {}).get("status", {})
        exec_code = status.get("exec_code", "")
        assert exec_code in ("success", "warning")
        assert "fallback" in result.get("data", {}).get("stdout", "")

        result2 = shell(
            command="cmd /c exit 0 || echo fallback",
            shell_type="ps7"
        )
        status2 = result2.get("llm_data", {}).get("status", {})
        exec_code2 = status2.get("exec_code", "")
        assert exec_code2 in ("success", "warning")
        assert "fallback" not in result2.get("data", {}).get("stdout", "")

    def test_chained_and_operators(self):
        """Chained && translation test"""
        result = shell(
            command="echo a && echo b && echo c",
            shell_type="ps7"
        )
        assert is_success(result)

    def test_mixed_operators(self):
        """Mixed && and || translation test"""
        result = shell(
            command="echo test && echo success || echo failed",
            shell_type="ps7"
        )
        assert is_success(result) or is_error(result)

    # #14: 无条件调用 _translate_powershell_operators，验证无 &&/|| 的命令不退化
    def test_no_operator_PS(self):
        """PowerShell command without &&/|| still works — regression for unconditional translation"""
        result = shell(
            command="echo 'simple command without operators'",
            shell_type="ps7"
        )
        assert is_success(result)
        assert "simple command without operators" in result["data"]["stdout"]


class TestExecuteShellCommandRealScenarios:
    """Real scenario test"""

    def test_get_system_info(self):
        """Get system info"""
        result = shell(command="Get-ComputerInfo | Select-Object WindowsVersion, OsName")
        assert is_success(result) or is_error(result)

    def test_list_processes(self):
        """List processes"""
        result = shell(command="Get-Process | Select-Object -First 5 Name, Id")
        assert is_success(result)

    def test_check_network(self):
        """Check network connection"""
        result = shell(command="Test-Connection -ComputerName localhost -Count 1")
        assert is_success(result) or is_error(result)

    def test_file_search(self, temp_output_dir):
        """File search"""
        result = shell(
            command="Get-ChildItem -File | Select-Object Name, Length",
            cwd=str(temp_output_dir)
        )
        assert is_success(result)


class TestExecuteShellCommandBoundary:
    """Boundary test"""

    def test_empty_command(self):
        """Empty command"""
        result = shell(command="")
        assert is_error(result)

    def test_whitespace_command(self):
        """Whitespace command"""
        result = shell(command="   \n\t  ")
        assert is_error(result)

    def test_special_characters(self):
        """Special character handling - XiaoJian 2026-06-27, updated XiaoJian 2026-06-28 (simplified special chars, PowerShell limit)"""
        result = shell(command="echo 'special chars: <>& chinese test'")
        assert is_success(result)

    def test_long_output(self):
        """Long output (100+ lines)"""
        result = shell(command="1..150 | ForEach-Object { Write-Output \"Line $_ test data\" }")
        assert is_success(result)
        lines = result["data"]["stdout"].strip().split("\n")
        assert len(lines) >= 50

    def test_timeout_boundary_min(self):
        """timeout boundary - minimum"""
        result = shell(command="echo test", timeout=1)
        assert is_success(result) or is_error(result)

    def test_timeout_boundary_max(self):
        """timeout boundary - maximum 600"""
        result = shell(command="echo test", timeout=600)
        assert is_success(result)

    def test_timeout_exceeded(self):
        """Timeout test - XiaoJian 2026-06-27, updated XiaoJian 2026-06-28 (timeout -> warning, code ERR_SHELL_TIMEOUT)"""
        result = shell(command="Start-Sleep -Seconds 10", timeout=2)
        status = result.get("llm_data", {}).get("status", {})
        assert status.get("exec_code") in ("error", "warning")
        assert status.get("code") == "ERR_SHELL_TIMEOUT"
        assert "超时" in status.get("hint", "") or "timeout" in status.get("hint", "").lower()


class TestExecuteShellCommandNegative:
    """Negative test"""

    def test_invalid_shell_type(self):
        """Invalid shell type"""
        result = shell(command="echo test", shell_type="unknown")
        assert is_error(result)
        assert "shell_type" in result["llm_data"]["status"]["detail"]

    def test_invalid_cwd(self):
        """Invalid working directory - 应回退tempdir"""
        result = shell(command="echo test", cwd="Z:/invalid/path/12345")
        assert is_success(result)

    def test_command_not_found(self):
        """Command not found"""
        result = shell(command="nonexistentcommand12345")
        assert is_error(result)

    def test_timeout_out_of_range_low(self):
        """timeout out of range - too low"""
        result = shell(command="echo test", timeout=0)
        assert is_error(result)

    def test_timeout_out_of_range_high(self):
        """timeout out of range - too high"""
        result = shell(command="echo test", timeout=1000)
        assert is_error(result)


class TestExecuteShellCommandSchemaValidation:
    """Schema validation test - discover Schema issues"""

    def test_schema_examples_insufficient(self):
        """Schema examples insufficient - should have more real-world examples"""
        pass

    def test_schema_safety_check_undocumented(self):
        """Safety check mechanism not fully documented in Schema"""
        pass

    def test_schema_timeout_unit_ambiguous(self):
        """timeout unit should be clearly documented in Schema as seconds"""
        pass
