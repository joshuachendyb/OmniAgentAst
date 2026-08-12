# -*- coding: utf-8 -*-
"""
Shell工具 Bug暴露测试 第2波 — 小欧 2026-06-24

目标: 验证shell/which/code工具在PersistentShell引擎下的正确性
"""
import os
import re
import sys
import time
from typing import Any, Dict

import pytest

from app.tools.fundamental.execute_shell_command import shell
from app.tools.shell.find_command import which
from app.tools.tool_response import is_success, is_error
from app.tools.tool_fc_helper import _decode_bytes_safe


# ══════════════════════════════════════════════════════════════════════════════
# Bug#12: _decode_bytes_safe 编码优先级问题
# ══════════════════════════════════════════════════════════════════════════════

class TestBug12_DecodeEncodingPriority:
    """Bug#12: _decode_bytes_safe 先试系统编码(GBK/cp936)再试utf-8

    在中文Windows上,locale.getpreferredencoding() = 'cp936' (GBK).
    如果命令输出是纯utf-8,先用GBK解码可能产生乱码.
    验证:纯utf-8中文被gbk先行解码时产生乱码
    """

    def test_bug12_utf8_decoded_as_gbk_mangled(self):
        utf8_b = "你好".encode("utf-8")
        import locale
        pref = locale.getpreferredencoding().lower()
        if "936" not in pref and "gbk" not in pref and "cp936" not in pref:
            pytest.skip(f"系统编码不是cp936: {pref}")
        result = _decode_bytes_safe(utf8_b)
        assert result == "你好", \
            f"utf-8中文应优先utf-8正确解码, 实际'{result}'"

    def test_bug12_emoji_utf8_not_gbk(self):
        """emoji等非GBK字符被cp936解码不会产生乱码(因为会失败fallback到utf-8)"""
        emoji_b = "🐛".encode("utf-8")
        result = _decode_bytes_safe(emoji_b)
        assert result == "🐛", f"Bug: emoji解码为'{result}',应为'🐛'"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#15: _build_shell_result 非0退出不返回err_code
# ══════════════════════════════════════════════════════════════════════════════

class TestBug15_NonZeroExitMissingErrCode:
    """Bug#15: _build_shell_result returncode非0时不返回err_code字段"""

    def test_bug15_nonzero_exit_has_err_code(self):
        r = shell("exit 1", shell_type="cmd")
        assert is_error(r), f"退出码1应报错 {r}"
        code = r.get("llm_data", {}).get("status", {}).get("code", "")
        assert code, f"Bug: 退出码1时无err_code"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#27: which split('\n')在Windows上留尾巴\r
# ══════════════════════════════════════════════════════════════════════════════

class TestBug27_FindCommandTrailingCR:
    """Bug#27: which使用split('\\n')在Windows上留尾巴\\r"""

    def test_bug27_no_trailing_cr(self):
        r = which("python", all_paths=True)
        if is_success(r):
            data = r.get("data", {}) or {}
            paths = data.get("paths", [])
            for p in paths:
                assert not p.endswith("\r"), \
                    f"Bug: 路径'{p}'末尾有回车符"



# ══════════════════════════════════════════════════════════════════════════════
# Bug#36: 超时在进程残留
# ══════════════════════════════════════════════════════════════════════════════

class TestBug36_TimeoutProcessLeak:
    """Bug#36: 超时kill在子进程可能残留"""

    def test_bug36_timeout_returns_error(self):
        r = shell(
            "powershell Start-Sleep -Seconds 30", timeout=1)
        assert r["llm_data"]["status"]["exec_code"] in ("error", "warning"), f"1秒超时应报错/警告 {r}"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#43: which 空白字符串
# ══════════════════════════════════════════════════════════════════════════════

class TestBug43_FindCommandEmptyString:
    """Bug#43: which 空白字符串不报错"""

    def test_bug43_whitespace_rejected(self):
        r = which("   ", all_paths=False)
        assert is_error(r), "Bug: 空白字符串未报错"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#49: shell_type=None行为
# ══════════════════════════════════════════════════════════════════════════════

class TestBug49_ShellTypeNone:
    """Bug#49: shell_type=None应等同于默认值powershell"""

    def test_bug49_none_works(self):
        r = shell("echo NoneShellTest", shell_type=None)
        assert is_success(r), "Bug: shell_type=None执行失败"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#53: timeout无效值校验
# ══════════════════════════════════════════════════════════════════════════════

class TestBug53_TimeoutBoundaries:
    """Bug#53: timeout=0,负值,>600000应被拦截"""

    @pytest.mark.parametrize("bad", [0, -1, -100, 600001])
    def test_bug53_bad_timeout_rejected(self, bad):
        r = shell("echo test", timeout=bad)
        assert is_error(r), f"Bug: timeout={bad}应被拒绝"


# ══════════════════════════════════════════════════════════════════════════════
# Bug#55: shell shell_type="cmd"时PYTHONIOENCODING污染
# ══════════════════════════════════════════════════════════════════════════════

class TestBug55_CmdPythonEnvVars:
    """Bug#55: cmd子进程环境中PYTHONIOENCODING和PYTHONUTF8被设置?"""

    def test_bug55_cmd_sees_python_env(self):
        r = shell("set PYTHON", shell_type="cmd")
        assert is_success(r), f"执行失败: {r}"
        stdout = (r.get("data", {}) or {}).get("stdout", "")
        assert "PYTHONUTF8" in stdout, "PYTHONUTF8在cmd环境中不可见"
        assert "PYTHONIOENCODING" in stdout, "PYTHONIOENCODING在cmd环境中不可见"
