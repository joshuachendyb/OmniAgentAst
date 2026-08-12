# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-28 - 小欧 - 新增 shell 引擎/工具函数质量测试, 覆盖_replace_python3_safe/_close_if_blocks/_cmd_powershell_mismatch_hint/_translate_powershell_operators
# 2026-07-28 - 小欧 - 删除已废弃的 _replace_ampersand 测试（功能被 _translate_powershell_operators 覆盖），充实 _translate_powershell_operators 测试案例

"""
shell 引擎/工具函数质量测试 — 小欧 2026-07-28

测试项:
  1. _replace_python3_safe     — python3→python, 引号感知
  2. _close_if_blocks          — if块闭合补全, 深度计数+引号感知
  3. _cmd_powershell_mismatch_hint — CMD/PS混用检测, 中英文匹配
  4. _translate_powershell_operators — PS &&/|| 完整翻译(含注释/子表达式)
"""

import pytest

from app.tools.fundamental.shell_engine import (
    _replace_python3_safe,
)
from app.tools.fundamental.execute_shell_command import (
    _close_if_blocks,
    _shell_mismatch_hint,
    _translate_powershell_operators,
)

# ═══════════════════════════════════════════════════════
# 1  _replace_python3_safe 测试
# ═══════════════════════════════════════════════════════

class TestReplacePython3Safe:
    """_replace_python3_safe: python3→python 引号感知替换"""

    def test_basic_replacement(self):
        """BUG-16: 正常python3应替换为python"""
        cmd, count = _replace_python3_safe("python3 --version")
        assert cmd == "python --version"
        assert count == 1

    def test_inside_double_quotes(self):
        """BUG-17: 双引号内python3不应替换"""
        cmd, count = _replace_python3_safe('echo "use python3"')
        assert count == 0
        assert cmd == 'echo "use python3"'

    def test_inside_single_quotes(self):
        """BUG-18: 单引号内python3不应替换"""
        cmd, count = _replace_python3_safe("echo 'use python3'")
        assert count == 0
        assert cmd == "echo 'use python3'"

    def test_python3_at_end(self):
        """BUG-19: python3在行尾"""
        cmd, count = _replace_python3_safe("run python3")
        assert cmd == "run python"
        assert count == 1

    def test_word_boundary_no_match(self):
        """BUG-20: python3not不应匹配(无尾部边界)"""
        cmd, count = _replace_python3_safe("python3not")
        assert count == 0
        assert cmd == "python3not"

    def test_no_preceding_boundary(self):
        """BUG-21: apython3不应匹配(无前部边界)"""
        cmd, count = _replace_python3_safe("apython3")
        assert count == 0
        assert cmd == "apython3"

    def test_multiple_occurrences(self):
        """BUG-22: 多个python3全部替换"""
        cmd, count = _replace_python3_safe("python3 a && python3 b")
        assert count == 2
        assert cmd == "python a && python b"

    def test_python3_with_semicolon(self):
        """BUG-23: python3后跟分号"""
        cmd, count = _replace_python3_safe("python3;echo done")
        assert count == 1
        assert cmd == "python;echo done"

    def test_mixed_quotes_and_python3(self):
        """BUG-24: 引号内外混合, 只替换引号外的"""
        cmd, count = _replace_python3_safe('echo "python3" && python3')
        assert count == 1
        assert cmd == 'echo "python3" && python'

    def test_empty_string(self):
        """BUG-25: 空字符串"""
        cmd, count = _replace_python3_safe("")
        assert count == 0
        assert cmd == ""


# ═══════════════════════════════════════════════════════
# 2  _close_if_blocks 测试
# ═══════════════════════════════════════════════════════

class TestCloseIfBlocks:
    """_close_if_blocks: if块闭合补全, 深度计数+引号感知"""

    def _build(self, *segments):
        """Helper: 拼出含marker的模拟翻译串"""
        return "".join(segments)

    def test_needs_close(self):
        """BUG-26: 块缺少闭合时补}"""
        s = '; if ($__ok) {  echo hello'
        result = _close_if_blocks(s)
        assert result == '; if ($__ok) {  echo hello }'

    def test_already_closed(self):
        """BUG-27: 块已有闭合时不重复补"""
        s = '; if ($__ok) {  echo hello }'
        result = _close_if_blocks(s)
        assert result == s

    def test_string_brace_not_mistaken(self):
        """BUG-28: 字符串内}不误判为块闭合(原简单存在性检查的bug)"""
        s = '; if ($__ok) {  echo "}" }'
        # 第一个}在字符串内, 第二个}才是块闭合, 已有闭合
        result = _close_if_blocks(s)
        assert result == s

    def test_string_brace_not_mistaken_needs_close(self):
        """BUG-29: 字符串内有}但块缺少闭合, 仍需补"""
        s = '; if ($__ok) {  echo "}"'
        result = _close_if_blocks(s)
        assert result == '; if ($__ok) {  echo "}" }'

    def test_nested_blocks(self):
        """BUG-30: 嵌套块深度计数正确, 各marker独立闭合"""
        s = '; if ($__ok) {  a ; if ($__ok) {  b }'
        result = _close_if_blocks(s)
        # 外层覆盖到内层marker前, 外层缺}补在a后面
        assert result == '; if ($__ok) {  a  }; if ($__ok) {  b }'

    def test_not_marker(self):
        """BUG-31: 不含marker时不变"""
        s = "echo hello"
        assert _close_if_blocks(s) == s

    def test_multiple_if_blocks(self):
        """BUG-32: 多个if块各自补全"""
        s = 'cmd1 ; if ($__ok) {  a ; if ($__ok) {  b }'
        result = _close_if_blocks(s)
        # 外层仅覆盖到内层marker, 补}在a后; 内层已有}不重复补
        assert result == 'cmd1 ; if ($__ok) {  a  }; if ($__ok) {  b }'

    def test_if_not_marker(self):
        """BUG-33: if (-not $__ok) 块处理"""
        s = '; if (-not $__ok) {  echo fail'
        result = _close_if_blocks(s)
        assert result == '; if (-not $__ok) {  echo fail }'

    def test_string_with_brace_and_marker(self):
        """BUG-34: 真实场景 — 翻译后字符串内}不干扰闭合判断"""
        s = '$__ok=$true; echo "}" ; $__ok=$?; if ($__ok) {  echo hello'
        result = _close_if_blocks(s)
        assert '} ; $__ok=$?' in result or result.count('}') == 2
        assert result.endswith('hello }')


# ═══════════════════════════════════════════════════════
# 3  _shell_mismatch_hint 测试
# ═══════════════════════════════════════════════════════

class TestShellMismatchHint:
    """_shell_mismatch_hint: shell语法混用检测, 中英文匹配+4种shell类型"""

    def test_chinese_error(self):
        """中文错误提示应匹配"""
        stderr = "'Select-Object' 不是内部或外部命令，也不是可运行的程序"
        result = _shell_mismatch_hint("cmd", stderr)
        assert "PowerShell" in result

    def test_chinese_error2(self):
        """中文错误变体"""
        stderr = "'Select-Object' 不是可运行的程序"
        result = _shell_mismatch_hint("cmd", stderr)
        assert "PowerShell" in result

    def test_english_not_recognized(self):
        """英文 not recognized 应匹配"""
        stderr = "'Select-Object' is not recognized as an internal command"
        result = _shell_mismatch_hint("cmd", stderr)
        assert "PowerShell" in result

    def test_english_not_an_internal(self):
        """英文 not an internal 应匹配"""
        stderr = "'Select-Object' is not an internal command"
        result = _shell_mismatch_hint("cmd", stderr)
        assert "PowerShell" in result

    def test_not_cmd_shell_type(self):
        """非cmd shell_type返回针对性的CMD语法提示"""
        result = _shell_mismatch_hint("ps7", "不是内部或外部命令")
        assert "CMD" in result

    def test_ps5_shell_type(self):
        """ps5 shell_type也返回CMD语法提示"""
        result = _shell_mismatch_hint("ps5", "'Select-Object' is not recognized")
        assert "CMD" in result

    def test_bash_shell_type(self):
        """bash shell_type返回Windows语法提示"""
        result = _shell_mismatch_hint("bash", "不是内部或外部命令")
        assert "Windows" in result or "cmd" in result

    def test_irrelevant_stderr(self):
        """不相关stderr返回空"""
        result = _shell_mismatch_hint("cmd", "File not found")
        assert result == ""


# ═══════════════════════════════════════════════════════
# 4  _translate_powershell_operators 测试（简测+回归）
# ═══════════════════════════════════════════════════════

class TestTranslatePowerShellOperators:
    """_translate_powershell_operators: PS &&/|| 完整翻译"""

    def test_basic_and_and(self):
        """基本&&应翻译为if($__ok)块"""
        result = _translate_powershell_operators("cmd1 && cmd2")
        assert "if ($__ok)" in result
        assert "cmd2" in result

    def test_basic_or(self):
        """基本||翻译"""
        result = _translate_powershell_operators("cmd1 || cmd2")
        assert "if (-not $__ok)" in result

    def test_and_and_inside_double_quotes(self):
        """双引号内&&不应翻译"""
        result = _translate_powershell_operators('echo "a && b"')
        assert 'a && b' in result
        assert "if ($__ok)" not in result

    def test_and_and_inside_single_quotes(self):
        """单引号内&&不应翻译"""
        result = _translate_powershell_operators("echo 'a && b'")
        assert 'a && b' in result
        assert "if ($__ok)" not in result

    def test_comment_and_and(self):
        """#注释内&&不触发翻译"""
        result = _translate_powershell_operators("echo hello # comment && still comment")
        assert "# comment" in result

    def test_subexpression_depth(self):
        """$()子表达式不影响引号状态"""
        result = _translate_powershell_operators('echo "$(Get-Date)" && echo done')
        assert "if ($__ok)" in result

    def test_multiple_and_and(self):
        """多个&&全部翻译"""
        result = _translate_powershell_operators("a && b && c")
        assert result.count("if ($__ok)") == 2

    def test_and_and_at_start(self):
        """&&在行首"""
        result = _translate_powershell_operators("&& cmd")
        assert "if ($__ok)" in result

    def test_and_and_at_end(self):
        """&&在行尾"""
        result = _translate_powershell_operators("cmd &&")
        assert "if ($__ok)" in result

    def test_empty_string(self):
        """空字符串不变"""
        assert _translate_powershell_operators("") == ""

    def test_no_operator(self):
        """无&&||时不变"""
        cmd = "echo hello"
        assert _translate_powershell_operators(cmd) == cmd

    def test_backtick_inside_quotes(self):
        """反引号转义引号不误切"""
        result = _translate_powershell_operators("echo 'it`'s fine' && echo ok")
        assert "if ($__ok)" in result
        assert "echo ok" in result

    def test_subexpression_inside_and_and(self):
        """$()嵌套在&&翻译中不影响"""
        result = _translate_powershell_operators("a && echo $(Get-Date)")
        assert "if ($__ok)" in result
        assert "echo $(Get-Date)" in result
