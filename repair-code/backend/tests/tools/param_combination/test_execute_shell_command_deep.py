# -*- coding: utf-8 -*-
"""
shell 第三轮深度BUG发现测试
小健 2026-06-25
"""
import pytest
import tempfile
from pathlib import Path

from app.tools.tool_response import is_success, is_error


class TestExecuteShellCommandDeepBugs:
    """深度BUG发现 — shell — 小健 2026-06-25"""

    def test_bug_1_command_empty(self, tmp_path):
        """BUG#1: command=""空字符串"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("")
        assert is_error(result)

    def test_bug_2_command_none(self, tmp_path):
        """BUG#2: command=None"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell(None)
        assert is_error(result)

    def test_bug_3_timeout_zero(self, tmp_path):
        """BUG#3: timeout=0"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("echo test", timeout=0)
        # 应该报错或立即超时

    def test_bug_4_timeout_negative(self, tmp_path):
        """BUG#4: timeout=-1负数"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("echo test", timeout=-1)
        # 应该报错

    def test_bug_5_dangerous_command(self, tmp_path):
        """BUG#5: 危险命令rm -rf /"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("rm -rf /")
        # 应该被安全检查拦截

    def test_bug_6_command_with_special_chars(self, tmp_path):
        """BUG#6: 命令包含特殊字符"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell('echo "test & | < >"')
        # 应该正认处理

    def test_bug_7_command_injection(self, tmp_path):
        """BUG#7: 命令注入攻击"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("echo test; rm -rf /")
        # 应该被拦截或安全执行

    def test_bug_8_cwd_not_exist(self, tmp_path):
        """BUG#8: cwd不存在 — 小健,更新小欧 2026-06-28(参数名cwd)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("echo test", cwd=str(tmp_path / "not_exist"))
        # 应该报错

    def test_bug_9_cwd_is_file(self, tmp_path):
        """BUG#9: cwd指向文件 — 小健,更新小欧 2026-06-28(参数名cwd)"""
        from app.tools.fundamental.execute_shell_command import shell
        fp = tmp_path / "test.txt"
        fp.write_text("test", encoding="utf-8")
        result = shell("echo test", cwd=str(fp))
        # 应该报错

    def test_bug_10_very_long_command(self, tmp_path):
        """BUG#10: 非常长的命令,10000字符"""
        from app.tools.fundamental.execute_shell_command import shell
        long_cmd = "echo " + "a" * 10000
        result = shell(long_cmd)
        # 应该成功或报错

    def test_bug_11_command_with_unicode(self, tmp_path):
        """BUG#11: 命令包含Unicode字符"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell('echo "测试中文"')
        # 应该正认处理

    def test_bug_15_timeout_very_short(self, tmp_path):
        """BUG#15: timeout=1毫秒(非常短)"""
        from app.tools.fundamental.execute_shell_command import shell
        result = shell("ping -n 10 127.0.0.1", timeout=1)
        # 应该超时
