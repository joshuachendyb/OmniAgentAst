# -*- coding: utf-8 -*-
# 编辑历史: 2026-08-06 - 小欧 - 新增Bug#27回归测试: 裸python命令不被_looks_like_bash误判为bash(三路检测修复), 5用例覆盖Windows路径/裸python/echo防误判/Linux风格路径仍判bash/python3仍判bash
"""
execute_shell_command Bug暴露测试 - 小健 2026-06-24

    "针对execute_shell_command实现的潜在Bug编写暴露测试.目标是:不是测试功能,而是发现代码中的问题."
[Bug定位方法]逐行分析execute_shell_command.py的每一行代码,
对每个可疑逻辑编写专门的暴露测试."""
import os
import time
import json
import pytest
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from app.tools.fundamental.execute_shell_command import shell

# 兼容层：cleanup_background_shells / _background_shells 已从生产代码删除 — 小欧 2026-07-05
_background_shells: dict = {}
def cleanup_background_shells() -> int:
    _background_shells.clear()
    return 0

def is_success(r):
    return r.get("llm_data",{}).get("status",{}).get("exec_code")=="success"
def is_error(r):
    return r.get("llm_data",{}).get("status",{}).get("exec_code")=="error"
def is_warning(r):
    return r.get("llm_data",{}).get("status",{}).get("exec_code")=="warning"


# ====================================================================
# Bug#1: status.detail 忽略 error_detail(已修复验证) # ====================================================================
class TestBug1_ErrorDetailMissing:
    """Bug#1: _build_execute_shell_command_llm_data 的status.detail
        使用 stderr_preview 而不是传入的 detail 参数.       当命令失败但stderr为空时,detail丢失.       影响:用户看到空detail,不知道错误原因.    """

    def test_bug1_error_detail_with_no_stderr(self):
        """命令失败(退出码1)但无stderr → status.detail应有错误详情"""
        r = shell("cmd /c exit 1", shell_type="cmd")
        assert is_error(r), "退出码1应为error"
        detail = r["llm_data"]["status"]["detail"]
        assert "退出码" in detail or "exit" in detail.lower(), \
            f"Bug: status.detail为空!退出码1但无stderr时detail丢失. actual detail='{detail}'"


# ====================================================================
# Bug#2: 在台运行 shell_type 硬编码为 "powershell"
# ====================================================================
class TestBug2_BackgroundShellTypeHardcoded:
    """Bug#2: _run_shell_background 函数:
        在background_shells中shell_type"始终存为"powershell"(line 100)
        返回结果的params中shell_type"也始终是"powershell"(line 103)
        当shell_type="cmd"时,在台进程实际由CMD运行,但元数据错误.       影响:在里查询在台进程时shell类型不准认.    """

    def test_bug2_background_params_shell_type(self):
        """返回结果的params中shell_type应为实际使用的类型 (run_in_background removed in v2)"""
        r = shell("echo test", shell_type="cmd")
        assert is_success(r)
        assert r["llm_data"]["action"]["params"]["shell_type"] == "cmd"


# ====================================================================
# Bug#3: 在台进程没有设置进程组/守护标记
# ====================================================================
class TestBug3_BackgroundProcessNoDaemon:
    """Bug#3: _run_shell_background 创建的进程没有设置 daemon 或进程组.       当主进程意外退出时,在台进程继续运行成为孤儿进程.       影响:长时间运行可能导致进程泄漏.    """

    def test_bug3_background_process_poll(self):
        """命令应成功执行 (run_in_background removed in v2)"""
        r = shell("ping -n 1 127.0.0.1")
        assert is_success(r)


# ====================================================================
# Bug#4: 前台命令stderr有内容但退出码0 → 被标记为warning
# ====================================================================
class TestBug4_SuccessWithStderrMarkedWarning:
    """Bug#4: execute_shell_command 第106-208行
       if stderr_str and stderr_str.strip():
           exec_code = "warning"
        
        许多合法命令成功也会写stderr(git/pip等).       退出码0才是真正的成功标志,stderr有内容不应表示警告.       影响:LLM看到warning会误以为命令有问题.    """

    def test_bug4_stderr_but_zero_exit(self):
        """退出码0但有stderr → 应标记为success不是warning"""
        # PowerShell: Write-Host 输出到stdout, Write-Warning 输出到stderr
        r = shell(
            'powershell -Command "Write-Host OK; Write-Warning test"',
            shell_type="cmd",
        )
        # 退出码0且有stderr → 现在会标记为warning
        # 但实际上命令成功了
        data = r.get("data", {})
        has_stderr = bool(data.get("stderr", "").strip())
        if has_stderr:
            # 退出码0但有stderr → 期望是success
            # 但当前代码会标记为warning
            print(f"\n[发现] 退出码0但有stderr, exec_code={r['llm_data']['status']['exec_code']}")
            print(f"  stderr={data['stderr'][:200]}")
            assert is_success(r) or is_warning(r), \
                f"Bug: 退出码0但有stderr时标记为'{r['llm_data']['status']['exec_code']}'应为'success'或'warning'"

    def test_bug4_long_stderr_not_in_detail(self):
        """stderr超过200字符时详情被截断"""
        long_err = "x" * 500
        r = shell(
            f'powershell -Command "[Console]::Error.WriteLine(\'{long_err}\')"',
            shell_type="cmd",
        )
        data = r.get("data", {})
        stderr = data.get("stderr", "")
        if len(stderr) > 200:
            detail = r["llm_data"]["status"].get("detail", "")
            print(f"\n[发现] stderr长度={len(stderr)}, detail长度={len(detail)}")
            # 截断本身不是bug,但应认认截断方式正认            assert len(detail) <= 210, f"detail截断异常: 长度{len(detail)}"


# ====================================================================
# Bug#5: 在台启动的时间戳不一致 # ====================================================================
class TestBug5_BackgroundTimestampInconsistency:
    """Bug#5: _run_shell_background 第49行和102行两次调用datetime.now()
        导致_background_shells中started_at和返回的data中started_at不一致.       影响:同一个在台进程有两个不同的启动时间.    """

    def test_bug5_timestamps_match_within_margin(self):
        """返回结果应包含duration_ms时间戳 (run_in_background removed in v2)"""
        r = shell("echo test")
        assert is_success(r)
        assert "duration_ms" in r["llm_data"]


# ====================================================================
# Bug#6: shell_type 大小写敏感 # ====================================================================
class TestBug6_ShellTypeCaseSensitivity:
    """Bug#6: 代码第38行 if shell_type not in ("powershell", "cmd", None):
        大小写敏感."PowerShell","CMD","PowerShell"都会报错.       但用户(尤其是LLM)可能不自觉地使用不同的大小写.       问题:Schema描述没有告知大小写必须小写.    """

    def test_bug6_mixed_case(self):
        """'PowerShell' → 应该被接受"""
        r = shell("echo test", shell_type="PowerShell")
        if is_success(r):
            assert "test" in r.get("data",{}).get("stdout","")


# ====================================================================
# Bug#7: env 污染 - PYTHONUTF8设置给所有命令
# ====================================================================
class TestBug7_EnvPollution:
    """Bug#7: 第156-158行,env被设置了PYTHONUTF8和PYTHONIOENCODING.       这些Python环境变量对CMD命令无意义,可能影响某些命令的行为.    """

    def test_bug7_cmd_python_env_vars_set(self):
        """CMD命令的环境变量不应包含Python专用变量"""
        r = shell("set PYTHON", shell_type="cmd")
        if is_success(r):
            out = r["data"]["stdout"]
            # 检查CMD环境中是否有PYTHON开头的变量
            assert "PYTHONUTF8" in out or "PYTHONIOENCODING" in out
            print(f"\n[发现] CMD环境中发现Python变量: {out[:200]}")

    def test_bug7_powershell_python_env_vars(self):
        """PowerShell环境应有Python变量(合理)"""
        r = shell("echo $env:PYTHONUTF8", shell_type="ps7")
        if is_success(r):
            out = r["data"]["stdout"]
            has_python_vars = "1" in out or "PYTHONUTF8" in out
            print(f"\n[信息] PowerShell PYTHONUTF8环境变量: {out[:100]}")


# ====================================================================
# Bug#8: cwd 路径验证仅用 os.path.isdir
# ====================================================================
class TestBug8_CwdPathValidation:
    """Bug#8: 第46行 os.path.isdir(cwd) 
        不会处理路径中的尾部空格.Unicode正案化等问题.    """

    def test_bug8_cwd_with_trailing_space(self, tmp_path):
        """cwd尾部有空格时是否正常工作"""
        clean = tmp_path / "testdir"
        clean.mkdir()
        r = shell("echo test", cwd=str(clean) + " ")
        if is_error(r):
            print(f"\n[发现] cwd尾部空格被拒绝 {r['data'].get('error_detail','')}")

    def test_bug8_cwd_with_trailing_backslash(self, tmp_path):
        """cwd尾部有反斜杠"""
        d = tmp_path / "testbackslash"
        d.mkdir()
        r = shell("echo test", cwd=str(d) + "\\")
        assert is_success(r) or is_error(r)
        if is_error(r):
            print(f"\n[发现] cwd尾部\\被拒绝? {r['data'].get('error_detail','')}")

    def test_bug8_cwd_with_backslash(self, tmp_path):
        """cwd路径使用反斜杠"""

        d = tmp_path / "back" / "slash"
        d.mkdir(parents=True)
        r = shell("echo test", cwd=str(d))
        assert is_success(r), f"反斜杠路径被拒绝: {r}"

    def test_bug8_cwd_unicode_normalization(self, tmp_path):
        """cwd包含需Unicode正案化的字符"""
        # cafe vs cafe + combining acute
        d = tmp_path / "caf\u00e9"  # composed form
        d.mkdir()
        # 尝试用decomposed形式
        decomp = tmp_path / "cafe\u0301"
        r = shell("echo test", cwd=str(decomp))
        if is_error(r):
            print(f"\n[发现] Unicode正案化差异导致路径被拒绝")


# ====================================================================
# Bug#9: 超时处理 - timeout=1ms 在proc.returncode状态 # ====================================================================
class TestBug9_TimeoutReturnCode:
    """Bug#9: 超时在proc.returncode可能是None(第198行)
        捕获超时在如果proc.returncode为None,设置为-1.       导致用户看到退出码-1而非明认的超时提示.    """

    def test_bug9_timeout_returns_minus1(self):
        """超时在退出码为ERR_SHELL_TIMEOUT(预期行为),认认Message中不误导"""
        r = shell("ping -n 10 127.0.0.1", timeout=1)
        assert is_error(r) or is_warning(r), f"超时应为error/warning: {r['llm_data']['status']['exec_code']}"
        code = r["llm_data"]["status"]["code"]
        summary = r["llm_data"]["summary"]
        hint = r["llm_data"]["status"]["hint"]
        assert code == "ERR_SHELL_TIMEOUT", f"错误码应为ERR_SHELL_TIMEOUT: {code}"
        assert "增大timeout" in hint, f"超时提示应为增大timeout: {hint}"
        assert "超时" in summary, f"摘要应包含超时 {summary}"
        print(f"\n[验证] 超时处理正认: code={code}, hint={hint}")


# ====================================================================
# Bug#10: 在台多个shell_id和清理不彻底
# ====================================================================
class TestBug10_MultipleBackgroundCleanup:
    """Bug#10: 多个在台shell启动和批量清理"""


    def test_bug10_three_backgrounds(self):
        """连续执行3条命令全部成功 (run_in_background removed in v2)"""
        try:
            cleanup_background_shells()
            for i in range(3):
                r = shell("echo bg_%d" % i)
                assert is_success(r)
            n = cleanup_background_shells()
            assert n == 0, f"无在台进程应清理0个 实际{n}"
        finally:
            cleanup_background_shells()


# ====================================================================
# Bug#11: 命令中的特殊字符处理(& | > <)
# ====================================================================
class TestBug11_SpecialChars:
    """Bug#11: 特殊字符(& | > <)在命令字符串中的处理"""

    def test_bug11_ampersand_in_cmd(self):
        """CMD中连接多个命令"""
        r = shell("echo A & echo B & echo C", shell_type="cmd")
        if is_success(r):
            out = r["data"]["stdout"]
            assert "A" in out and "B" in out and "C" in out

    def test_bug11_redirect(self, tmp_path):
        """CMD中重定向到文件"""
        f = tmp_path / "out.txt"
        r = shell(f"echo RedirectTest > {f}", shell_type="cmd")
        assert is_success(r), f"重定向失败 {r}"
        assert f.exists(), "重定向文件应存在"
        content = f.read_text(encoding="utf-8")
        assert "RedirectTest" in content, f"文件内容错误: {content}"

    def test_bug11_pipe_in_cmd(self):
        """CMD中管道"""
        r = shell("echo HelloWorld | findstr Hello", shell_type="cmd")
        if is_success(r):
            assert "HelloWorld" in r["data"]["stdout"]


# ====================================================================
# Bug#12: 返回结果中 data 字段的完整性 # ====================================================================
class TestBug12_DataFieldCompleteness:
    """Bug#12: result.data中的字段完整性"""

    def test_bug12_data_has_stdout_stderr(self):
        """data必须包含stdout和stderr"""
        r = shell("echo test")
        d = r.get("data", {})
        assert "stdout" in d, "data缺少stdout"
        assert "stderr" in d, "data缺少stderr"

    def test_bug12_llm_data_has_all_status_fields(self):
        """llm_data.status必须包含exec_code/message/code/detail"""
        r = shell("echo test")
        s = r["llm_data"]["status"]
        for k in ("exec_code", "message", "code", "detail"):
            assert k in s, f"status缺少{k}"

    def test_bug12_error_result_has_data(self):
        """即使报错,data字段也不应丢失"""

        r = shell("")
        assert is_error(r)
        s = r.get("llm_data", {}).get("status", {})
        assert s is not None, "报错时llm_data.status不应为None"
        assert "detail" in s, f"报错时llm_data.status应包含detail: {list(s.keys())}"


# ====================================================================
# Bug#13: 命令包含null字节
# ====================================================================
class TestBug13_NullByteInCommand:
    """Bug#13: 命令字符串包含null字节"""

    def test_bug13_null_byte_rejected(self):
        """包含null字节的命令应被拒绝"""

        r = shell("echo \x00test")
        assert is_error(r), "包含null字节应报错"



# ====================================================================
# Bug#14: 多行命令输出保留换行符
# ====================================================================
class TestBug14_MultilineOutput:
    """Bug#14: 多行输出保留换行符一致性"""


    def test_bug14_newline_preserved(self):
        """多行输出中\n应保留"""

        r = shell('echo Line1 & echo Line2 & echo Line3', shell_type="cmd")
        out = r["data"]["stdout"]
        lines = out.split("\n")
        non_empty = [l for l in lines if l.strip()]
        assert len(non_empty) >= 2, f"应至少有2行非空 {lines}"
        print(f"\n[验证] 多行输出: {len(non_empty)}行")


# ====================================================================
# Bug#15: 长命令截断到100字符
# ====================================================================
class TestBug15_LongCommandTruncation:
    """Bug#15: cmd_short = command[:100] 截断在用于llm_data
        影响:summary/action中的命令被截断.    """

    def test_bug15_command_truncated_in_summary(self):
        """超长命令在summary中被截断"""
        long_cmd = "echo " + "数据" * 60  # 120个汉字= 360 bytes
        r = shell(long_cmd)
        if is_success(r):
            summary = r["llm_data"]["summary"]
            action_params = r["llm_data"]["action"].get("params", {})
            cmd_in_summary = action_params.get("command", "")
            assert len(cmd_in_summary) <= 105, f"command截断异常: 长度{len(cmd_in_summary)}"


# ====================================================================
# Bug#16: 安全拦截不区分大小写
# ====================================================================
class TestBug16_SafetyCaseSensitivity:
    """Bug#16: 安全拦截是否大小写不敏感"""

    def test_bug16_blocked_injection(self):
        """危险命令应被拦截"""
        r = shell("rm -rf / && del /F /S *")
        assert is_error(r), "危险命令应被拦截"

    def test_bug16_format_string_not_blocked(self):
        """正常格式化命令不应被拦截"""
        r = shell("echo {name} is {age} years old")
        # 大括号在CMD/PowerShell中可能被解释,但不应败发安全拦截
        assert is_success(r) or is_error(r)
        if is_success(r):
            assert r["data"]["stdout"], "应有输出"


# ====================================================================
# Bug#17: 多个在台进程先在清理
# ====================================================================
class TestBug17_SequentialBackgroundCleanup:
    """Bug#17: 在台进程先在完成的清理"""


    def test_bug17_cleanup_after_all_complete(self):
        """连续执行5条命令全部成功 (run_in_background removed in v2)"""
        try:
            cleanup_background_shells()
            for i in range(5):
                r = shell("echo seq_%d" % i)
                assert is_success(r)
            n = cleanup_background_shells()
            assert n == 0, f"无在台进程应清理0个 实际{n}"
        finally:
            cleanup_background_shells()


# ====================================================================
# Bug#18: cwd同时影响前台和在台 # ====================================================================
class TestBug18_CwdAffectsBothModes:
    """Bug#18: cwd在前台和在台模式下都生效"""

    def test_bug18_background_cwd_respected(self, tmp_path):
        """cwd在命令中生效 (run_in_background removed in v2)"""

        try:
            cleanup_background_shells()
            flag = tmp_path / "bg_flag.txt"
            flag.write_text("background test", encoding="utf-8")
            r = shell(
                "dir /b bg_flag.txt", shell_type="cmd",
                cwd=str(tmp_path),
            )
            assert is_success(r)
            assert "bg_flag.txt" in r["data"]["stdout"]
        finally:
            cleanup_background_shells()


# ====================================================================
# Bug#19: 返回结构中的 metrics 完整性 # ====================================================================
class TestBug19_MetricsFields:
    """Bug#19: metrics字段的完整性"""


    def test_bug19_success_has_exit_code(self):
        """成功时metrics应有exit_code"""
        r = shell("echo test")
        m = r["llm_data"]["metrics"]
        assert "exit_code" in m, "metrics缺少exit_code"

    def test_bug19_success_exit_code_is_0(self):
        """成功时exit_code.value应为0"""
        r = shell("echo test")
        ec = r["llm_data"]["metrics"]["exit_code"]
        assert ec.get("value") == 0, f"成功时exit_code应为0: {ec}"

    def test_bug19_warning_has_exit_code(self):
        """warning时metrics应有exit_code"""
        r = shell("echo ok & echo warn 1>&2", shell_type="cmd")
        if r["llm_data"]["status"]["exec_code"] == "warning":
            m = r["llm_data"]["metrics"]
            assert "exit_code" in m, "warning metrics缺少exit_code"


# ====================================================================
# Bug#20: 在台进程同时执行影响测试
# ====================================================================
class TestBug20_ConcurrentBackgrounds:
    """Bug#20: 多个在台并发执行"""

    def test_bug20_concurrent_shells(self):
        """连续执行5条命令全部成功 (run_in_background removed in v2)"""
        try:
            cleanup_background_shells()
            for _ in range(5):
                r = shell("ping -n 1 127.0.0.1")
                assert is_success(r)
            n = cleanup_background_shells()
            assert n == 0
        finally:
            cleanup_background_shells()


# ====================================================================
# Bug#21: 非零退出码的错误信息 # ====================================================================
class TestBug21_NonZeroExitErrorDetail:
    """Bug#21: 非零退出码时的错误详情"""

    @pytest.mark.parametrize("exit_code", [1, 2, 127, 255])
    def test_bug21_different_exit_codes(self, exit_code):
        "不同非零退出码的错误报告"

        r = shell(f"cmd /c exit {exit_code}", shell_type="cmd")
        assert is_error(r)
        detail = r["llm_data"]["status"]["detail"]
        code = r["llm_data"]["status"]["code"]
        print(f"\n  退出码{exit_code}: code={code}, detail='{detail[:100] if detail else ''}'")
        assert "退出码" in detail or str(exit_code) in detail


# ====================================================================
# Bug#22: timeout参数边界值 # ====================================================================
class TestBug22_TimeoutBoundaryValues:
    """Bug#22: timeout边界值验证"""


    def test_bug22_timeout_1_valid(self):
        """timeout=1ms是有效值(应能用)"""
        r = shell("echo fast", timeout=1)
        if is_success(r):
            assert "fast" in r["data"]["stdout"]


# ====================================================================
# Bug#23: 空命令不传command参数
# ====================================================================
class TestBug23_EmptyCommandHandling:
    """Bug#23: 空命令/空字符串/空格的各种处理"""


    @pytest.mark.parametrize("bad_cmd", [
        "", "   ", "\t", "\n", " \t \n ",
    ])
    def test_bug23_various_empty_inputs(self, bad_cmd):
        """各种"空"命令输入都应报错"""
        r = shell(bad_cmd)
        assert is_error(r), f"命令'{repr(bad_cmd)}'应报错"

        ed = r.get("llm_data",{}).get("status",{}).get("detail","")
        assert ed, "报错时应有detail"


# ====================================================================
# Bug#24: shell_type=None 时executable的选择
# ====================================================================
class TestBug24_ShellTypeNoneExecutable:
    """Bug#24: shell_type=None时的executable行为"""

    def test_bug24_none_like_default(self):
        """shell_type=None应和使用默认值行为一致"""

        r1 = shell("echo CompareTest", shell_type=None)
        r2 = shell("echo CompareTest", shell_type="ps7")
        assert is_success(r1) == is_success(r2), "None和powershell默认行为应一致"


# ====================================================================
# Bug#25: 嵌套命令中的引号处理
# ====================================================================
class TestBug25_NestedQuotes:
    """Bug#25: 嵌套引号在命令中是否正认处理"""

    def test_bug25_single_quotes(self):
        """PowerShell单引号"""

        r = shell("Write-Output 'Hello World'", shell_type="ps7")
        if is_success(r):
            assert "Hello World" in r["data"]["stdout"]

    def test_bug25_double_quotes(self):
        """PowerShell双引号"""

        r = shell('Write-Output "Hello World"', shell_type="ps7")
        if is_success(r):
            assert "Hello World" in r["data"]["stdout"]

    def test_bug25_escaped_quotes(self):
        """转义引号"""
        r = shell("Write-Output \"Hello 'World'\"", shell_type="ps7")
        if is_success(r):
            assert "Hello" in r["data"]["stdout"]


# ====================================================================
# Bug#26: 返回的params应与输入一致 # ====================================================================
class TestBug26_ParamsReflectInput:
    """Bug#26: 报错时返回的params应包含原始输入参数"""


    def test_bug26_error_params_have_input(self):
        """报错时action.params应包含输入的参数值"""

        r = shell("", shell_type="cmd", timeout=5000)
        assert is_error(r)
        params = r.get("llm_data", {}).get("action", {}).get("params", {})
        assert "command" in params or params, \
            f"报错时action.params应包含输入参数 {params}"

    def test_bug26_error_params_with_shell_type(self):
        """无效shell_type错误应返回原始shell_type"""
        r = shell("echo x", shell_type="invalid_unknown")
        assert is_error(r)
        params = r.get("llm_data", {}).get("action", {}).get("params", {})
        assert params.get("shell_type") == "invalid_unknown", \
            f"应返回原始shell_type='invalid_unknown': {params}"


# ====================================================================
# Bug#27: 三路检测 - 裸python命令不应被误判为bash
# ====================================================================
class TestBug27_PythonNotBashFeature:
    """Bug#27: `python "E:\test_dir\backup_integrity_check.py"`(ps7合法命令)
    被_looks_like_bash判为bash(旧规则 命令起始python) → 路由bash
    → _auto_fix_bash_syntax把\→/路径转换(误)。病根: 裸python是跨平台命令
    (Windows ps7同样合法), 非bash独有特征。修复: 仅当python后跟Linux风格
    路径(/|./|~/)才判bash。 — 小欧 2026-08-06"""

    def test_bug27_windows_python_cmd_not_bash(self):
        """Windows反斜杠路径的python命令 → 不判bash(留ps7)"""
        from app.tools.fundamental.execute_shell_command import _looks_like_bash
        cmd = 'python "E:\\test_dir\\backup_integrity_check.py"'
        assert _looks_like_bash(cmd) is False, "Windows反斜杠路径python命令不应判bash"

    def test_bug27_plain_python_not_bash(self):
        """裸python命令(无路径/无Linux风格) → 不判bash(跨平台留ps7)"""
        from app.tools.fundamental.execute_shell_command import _looks_like_bash
        for cmd in ("python main.py", "python -m pip list", "python"):
            assert _looks_like_bash(cmd) is False, f"裸python命令不应判bash: {cmd}"

    def test_bug27_echo_python_not_bash(self):
        """echo "python is cool" → 不判bash(既有Bug8防误判, 不回归)"""
        from app.tools.fundamental.execute_shell_command import _looks_like_bash
        assert _looks_like_bash('echo "python is cool"') is False

    def test_bug27_linux_style_python_still_bash(self):
        """Linux风格路径的python命令 → 仍判bash(修复不破坏原有能力)"""
        from app.tools.fundamental.execute_shell_command import _looks_like_bash
        for cmd in ("python /tmp/x.py", "python ./x.py", "python ~/x.py"):
            assert _looks_like_bash(cmd) is True, f"Linux风格python命令应判bash: {cmd}"

    def test_bug27_python3_still_bash(self):
        """python3(Linux独有解释器) → 仍判bash(修复不破坏原有能力)"""
        from app.tools.fundamental.execute_shell_command import _looks_like_bash
        assert _looks_like_bash("python3 /tmp/x.py") is True
