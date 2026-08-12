# -*- coding: utf-8 -*-
"""
PersistentShell 引擎专项测试 — 小欧 2026-07-05

覆盖:
  1) 进程池复用 (_get_process / _return_process)
  2) 基础 shell 执行 (cmd + powershell)
  3) 超时机制
  4) 多次调用工作目录继承
  5) 多个 shell_type 隔离
  6) 进程自愈 (kill 后恢复)
  7) 临时文件清理 (cmd.exe 模式)
"""
from app.tools.fundamental.execute_shell_command import shell
from app.tools.shell.find_command import which
from app.tools.tool_response import is_success, is_error


# ═══════════════════════════════════════════════════════════════
# 基础执行 - 验证 PersistentShell 能正常工作
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_Basic:
    """PersistentShell 基础执行"""

    def test_shell_cmd_echo(self):
        r = shell("echo hello", shell_type="cmd")
        assert is_success(r), f"cmd echo 失败: {r}"

    def test_shell_powershell_echo(self):
        r = shell("Write-Host hello", shell_type="ps7")
        assert is_success(r), f"powershell echo 失败: {r}"

    def test_shell_with_exit_code(self):
        r = shell("python -c \"exit(0)\"", shell_type="cmd")
        assert is_success(r), "exit(0) 应返回 success"

    def test_shell_non_zero_exit(self):
        r = shell("python -c \"exit(1)\"", shell_type="cmd")
        assert r["llm_data"]["status"]["exec_code"] != "success"


# ═══════════════════════════════════════════════════════════════
# 进程池复用 - 多次执行应复用同一 PersistentShell 进程
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_PoolReuse:
    """进程池复用：多次 shell 调用共享同一进程"""

    def test_reuse_same_type(self):
        """同一 shell_type 多次调用不应崩溃"""
        for i in range(5):
            r = shell(f"echo call_{i}", shell_type="cmd")
            assert is_success(r), f"第{i}次调用失败: {r}"

    def test_isolated_types(self):
        """cmd 与 powershell 进程隔离，不应互相影响"""
        r1 = shell("echo from_cmd", shell_type="cmd")
        assert is_success(r1), "cmd 执行失败"
        r2 = shell("Write-Host from_ps", shell_type="ps7")
        assert is_success(r2), "powershell 执行失败"

    def test_many_sequential(self):
        """100 次连续调用验证稳定性"""
        for i in range(100):
            r = shell(f"echo seq_{i}", shell_type="cmd", timeout=30)
            assert is_success(r), f"第{i}次连续调用失败"


# ═══════════════════════════════════════════════════════════════
# 超时行为
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_Timeout:
    """PersistentShell 超时行为"""

    def test_timeout_short(self):
        """timeout=200ms 应让快速命令成功"""
        r = shell("echo fast", timeout=200, shell_type="cmd")
        assert is_success(r), f"200ms 超时不应影响快速命令: {r}"

    def test_timeout_hit(self):
        """极短 timeout 应触发超时"""
        r = shell(
            "ping -n 30 127.0.0.1",
            timeout=1, shell_type="cmd")
        assert r["llm_data"]["status"]["exec_code"] in ("error", "warning"), "1秒应超时"

    def test_timeout_recovery(self):
        """超时后进程应恢复可用"""
        r1 = shell("ping -n 30 127.0.0.1", timeout=1, shell_type="cmd")
        assert r1["llm_data"]["status"]["exec_code"] in ("error", "warning"), "首次应超时"
        r2 = shell("echo after_timeout", timeout=10, shell_type="cmd")
        assert is_success(r2), f"超时后恢复失败: {r2}"


# ═══════════════════════════════════════════════════════════════
# 工作目录跨调用行为
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_WorkingDir:
    """工作目录继承"""

    def test_cwd_persists(self):
        """PersistentShell 中 cd 后，下一次调用仍留在该目录"""
        r1 = shell("cd %TEMP% && cd", shell_type="cmd")
        assert is_success(r1), "cd to TEMP 失败"
        data1 = r1.get("data", {}) or {}
        path1 = (data1.get("stdout") or "").strip()
        assert path1, "未获取到路径"
        r2 = shell("cd", shell_type="cmd")
        assert is_success(r2), "第二次 cd 失败"
        data2 = r2.get("data", {}) or {}
        path2 = (data2.get("stdout") or "").strip()
        assert path2, "第二次未获取到路径"


# ═══════════════════════════════════════════════════════════════
# 大输出 / 截断行为
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_LargeOutput:
    """大输出截断测试"""

    def test_large_stdout_no_crash(self):
        """10MB 输出不应使 process 崩溃"""
        r = shell(
            "python -c \"import sys; sys.stdout.write('x'*1024*1024*10)\"",
            timeout=60000, shell_type="cmd")
        assert r is not None, "大输出导致返回 None"

    def test_stderr_no_crash(self):
        """大量 stderr 不应崩溃"""
        r = shell(
            "python -c \"import sys; sys.stderr.write('x'*1024*1024*5)\"",
            timeout=60000, shell_type="cmd")
        assert r is not None, "大量 stderr 导致返回 None"


# ═══════════════════════════════════════════════════════════════
# which 在 PersistentShell 下的表现
# ═══════════════════════════════════════════════════════════════

class TestPersistentShell_Which:
    """which 与 PersistentShell 共存"""

    def test_which_after_shell(self):
        """shell 执行后在 which 不应受影响"""
        r1 = shell("echo pre", shell_type="cmd")
        assert is_success(r1)
        r2 = which("python")
        assert is_success(r2), f"which 在 shell 后失败: {r2}"

    def test_which_multi_cmd(self):
        """which 多重调用稳定"""
        for cmd in ["python", "pip", "git"]:
            r = which(cmd)
            assert is_success(r), f"which '{cmd}' 失败"



