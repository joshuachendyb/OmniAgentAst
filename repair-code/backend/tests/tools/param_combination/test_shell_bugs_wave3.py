# -*- coding: utf-8 -*-
"""
Shell工具 Bug暴露测试 第3波 — 小欧 2026-06-24 — v2: PersistentShell版

目标: 深挖shell/which/code在PersistentShell引擎下的隐蔽Bug
"""
import time
import sys
from typing import Any, Dict

import pytest

from app.tools.fundamental.execute_shell_command import shell
from app.tools.shell.find_command import which
from app.tools.tool_response import is_success, is_error
from app.tools.tool_fc_helper import _decode_bytes_safe



# ═══════════════════════════════════════════════════════════════
# Bug#60: which 空格/特殊字符 ═════════════════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug60_FindCommandEdgeCases:
    """Bug#60: which的空格和特殊字符"""

    def test_bug60_non_existent_cmd(self):
        """不存在的命令应返回 available=False (找不到时为 warning)"""
        r = which("this_command_does_not_exist_42xyz")
        status = (r.get("llm_data", {}) or {}).get("status", {}) or {}
        assert status.get("exec_code") in ("success", "warning"), \
            f"不存在的命令应 success/warning: {status.get('exec_code')}"
        assert r["llm_data"]["metrics"]["available"]["value"] is False, \
            f"Bug: 不存在命令标记为 available=True"

    def test_bug60_all_paths_non_existent(self):
        """all_paths=True时不存在的命令应返回 warning (无路径)"""
        r = which("this_command_does_not_exist_42xyz", all_paths=True)
        status = (r.get("llm_data", {}) or {}).get("status", {}) or {}
        assert status.get("exec_code") in ("success", "warning"), \
            f"all_paths不存在的命令应 success/warning: {status.get('exec_code')}"

    def test_bug60_command_with_spaces(self):
        """含空格的命令名(如"Windows PowerShell")不应崩溃"""
        r = which("Windows PowerShell", all_paths=False)
        assert r is not None, "Bug: 空格命令名返回None"

    def test_bug60_unicode_command(self):
        """Unicode命令名不应崩溃"""
        r = which("测试命令", all_paths=False)
        assert r is not None, "Bug: Unicode命令名返回None"


# ═══════════════════════════════════════════════════════════════
# Bug#61: _build_shell_result timed_out但success=True ═══════
# ═══════════════════════════════════════════════════════════════

class TestBug61_TimedOutResultFields:
    """Bug#61: 超时结果的字段完整性"""

    def test_bug61_timeout_result_has_err_code(self):
        r = shell(
            "powershell Start-Sleep -Seconds 30", timeout=1)
        assert r["llm_data"]["status"]["exec_code"] in ("error", "warning"), f"超时未报错/警告 {r}"
        status = (r.get("llm_data", {}) or {}).get("status", {}) or {}
        assert status.get("code") == "ERR_SHELL_TIMEOUT", \
            f"Bug: 超时结果code='{status.get('code')}', 应为'ERR_SHELL_TIMEOUT'"
        assert "timeout" in status.get("hint", "").lower(), \
            f"Bug: 超时结果hint未提示包含timeout: '{status.get('hint')}'"


# ═══════════════════════════════════════════════════════════════
# Bug#62: shell 二进制输出含null字节 ═════════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug62_NullByteInOutput:
    """Bug#62: 二进制输出不应导致解码崩溃"""

    def test_bug62_binary_output_no_crash(self):
        r = shell(
            "powershell Write-Host ([char]0)Hello([char]0)World",
            shell_type="ps7")
        assert r is not None, "Bug: 含null字节输出导致返回None"



# ═══════════════════════════════════════════════════════════════
# Bug#65: which all_paths=True 对不存在命令的结果 ═════════════
# ═══════════════════════════════════════════════════════════════

class TestBug65_FindCommandAllPathsStructure:
    """Bug#65: which all_paths=True返回结构一致性"""

    def test_bug65_all_paths_structure_consistent(self):
        """存在命令应返回 paths 列表; 不存在命令应返回 warning (无可执行路径)"""
        r_exist = which("python", all_paths=True)
        r_noexist = which("xyz_nonexistent_cmd_999", all_paths=True)
        assert is_success(r_exist), "python查找失败"
        d_exist = r_exist.get("data", {}) or {}
        assert "paths" in d_exist and isinstance(d_exist["paths"], list) and len(d_exist["paths"]) > 0
        status_noexist = (r_noexist.get("llm_data", {}) or {}).get("status", {}) or {}
        assert status_noexist.get("exec_code") in ("success", "warning"), \
            f"不存在命令应 success/warning: {status_noexist.get('exec_code')}"



# ═══════════════════════════════════════════════════════════════
# Bug#67: Safety检查器对command中包含eval字符串的误报 ═══════
# ═══════════════════════════════════════════════════════════════

class TestBug67_SafetyFalsePositive:
    """Bug#67: 安全检查对command中含'eval'等子串的误报"""

    def test_bug67_eval_in_string_not_blocked(self):
        """command参数值本身含'eval('不应被拦截"""
        r = shell(
            'echo "This string contains eval( but is harmless"',
            shell_type="cmd")
        assert is_success(r), \
            f"Bug: 含'eval('字符串的命令被误拦截: {r}"

    def test_bug67_open_in_string_not_blocked(self):
        """command中open(出现在字符串内容内不应被拦截"""
        r = shell(
            'echo "open( is just text here"', shell_type="cmd")
        assert is_success(r), \
            f"Bug: 含'open('字符串的命令被误拦截: {r}"


# ═══════════════════════════════════════════════════════════════
# Bug#70: _decode_bytes_safe 混合编码bytes ════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug70_MixedEncodingBytes:
    """Bug#70: 混合编码字节解码时的行为"""

    def test_bug70_mixed_encoding_no_crash(self):
        """混合编码字节不应崩溃"""
        gbk_b = "测试".encode("gbk")
        emoji_b = "🎉".encode("utf-8")
        mixed = gbk_b + b" " + emoji_b
        result = _decode_bytes_safe(mixed)
        assert result is not None, "Bug: 混合编码解码返回None"
        assert len(result) > 0, "Bug: 混合编码解码为空"


# ═══════════════════════════════════════════════════════════════
# Bug#73: shell cwd为None时的行为 ═════════════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug73_CwdNoneBehavior:
    """Bug#73: cwd=None时使用当前目录"""

    def test_bug73_cwd_none_uses_cwd(self):
        import os
        cwd_before = os.getcwd()
        r = shell("cd", shell_type="cmd", cwd=None)
        assert is_success(r), f"Bug: cwd=None执行失败: {r}"


# ═══════════════════════════════════════════════════════════════
# Bug#74: shell timeout=1 (最小有效值) ═══════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug74_Timeout1:
    """Bug#74: timeout=1ms(边界最小值)"""

    def test_bug74_timeout_1ms_for_fast_cmd(self):
        """timeout=1ms留给非常快的命令"""
        r = shell("echo FastCmd", timeout=1)
        if is_error(r):
            status = (r.get("llm_data", {}) or {}).get("status", {}) or {}
            assert "timeout" in status.get("hint", "").lower(), \
                f"Bug: 1ms超时hint缺timeout提示: {status.get('hint')}"
        elif is_success(r):
            pass



# ═══════════════════════════════════════════════════════════════
# Bug#79: which 多重调用(非干扰) ═════════════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug79_FindCommandMultipleCalls:
    """Bug#79: which多次调用不干扰"""

    def test_bug79_sequential_calls_independent(self):
        results = []
        for cmd in ["python", "pip", "git", "node", "npm"]:
            r = which(cmd)
            results.append(r)
            assert is_success(r), f"查找'{cmd}'失败: {r}"
        for i, r in enumerate(results):
            assert r.get("data") is not None, \
                f"Bug: 第{i}次调用data=None"




# ═══════════════════════════════════════════════════════════════
# Bug#84: shell 超长command行 ═════════════════════════════════
# ═══════════════════════════════════════════════════════════════

class TestBug84_VeryLongCommand:
    """Bug#84: 超长命令(>8000字符)截断"""

    def test_bug84_long_command_cmd(self):
        cmd = "echo " + "A" * 8000
        r = shell(cmd, shell_type="cmd")
        assert is_success(r), f"Bug: 超长命令失败: {r}"
        data = r.get("data", {}) or {}
        stdout = data.get("stdout", "")
        assert "A" in stdout, f"Bug: 超长命令输出丢失"
