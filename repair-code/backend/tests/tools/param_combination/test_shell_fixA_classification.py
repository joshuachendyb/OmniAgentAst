# -*- coding: utf-8 -*-
# 编辑历史: 2026-08-08 - 小欧 - 新增修正A回归测试: error分支双字段判别法(真实错误信号→error/良性警告+stdout产出→warning/无产出→保守error),
#   覆盖150案例回归(131/17/2)中的三类判别 + _contains_real_error/_has_output 纯函数 + 词边界防误伤
# 编辑历史: 2026-08-11 - 小欧 - test_benign_warning_with_output_warning: 输出改纯ASCII(done), 避免cmd中文echo在GBK代码页解码乱码
#   (完整套件中detail显示'ͳ����'乱码致assert '统计完成' in detail失败, 编码往返脆弱; 测试语义不变仍验证stdout有产出→warning降级)
"""
execute_shell_command 修正A回归测试 - 小欧 2026-08-08

背景: task007 问题1-病因D 良性stderr误判为error(实证150个ERR_SHELL_EXEC中17个任务成功却误报error)。
修正: error分支(returncode≠0)改为双字段三分支判别:
  ① stderr/stdout 含真实错误信号(_REAL_ERROR_MARKERS词边界) → error
  ② 无真实错误信号 且 stdout有产出(_has_output) → warning(降级)
  ③ 无产出 → error(保守防掩盖)
本测试验证该判别的正确性与边界, 防止后续改动退化。
"""
import pytest
from typing import Dict, Any

from app.tools.fundamental.execute_shell_command import (
    shell, _contains_real_error, _has_output, _REAL_ERROR_MARKERS,
)


def is_error(r: Dict[str, Any]) -> bool:
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

def is_warning(r: Dict[str, Any]) -> bool:
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"

def is_success(r: Dict[str, Any]) -> bool:
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


class TestContainsRealError:
    """_contains_real_error 纯函数: 真实错误信号识别 + 词边界防误伤"""

    def test_python_exception_true(self):
        assert _contains_real_error("Traceback (most recent call last):\n  File x.py") is True

    def test_syntax_error_true(self):
        assert _contains_real_error("  File <string>, line 1\nSyntaxError: invalid syntax") is True

    def test_cmd_not_found_true(self):
        assert _contains_real_error("/usr/bin/bash: line 1: Select-Object: command not found") is True

    def test_windows_error_code_true(self):
        assert _contains_real_error("ERROR: Cannot find registry key 0x80070426") is True

    def test_chinese_failure_true(self):
        assert _contains_real_error("读取失败: 文件不存在") is True

    def test_benign_warning_false(self):
        # 良性提示必须不判为真实错误
        assert _contains_real_error("UserWarning: torch.quantize_per_tensor is deprecated") is False
        assert _contains_real_error("Using CPU") is False
        assert _contains_real_error("FutureWarning: pandas behavior change") is False

    def test_no_error_word_boundary_false(self):
        # 词边界: "no error"/"error-free" 不得误伤
        assert _contains_real_error("check complete, no error found") is False

    def test_empty_or_none_false(self):
        assert _contains_real_error("") is False
        assert _contains_real_error(None) is False


class TestHasOutput:
    """_has_output 纯函数: stdout 产出判定(strip 非空, 规避短产出误判)"""

    def test_short_output_true(self):
        # 实证边界: "PDF报告已生成" 10字符 < 旧长度阈值20, 必须判有产出
        assert _has_output("PDF报告已生成") is True

    def test_report_output_true(self):
        assert _has_output("4份报告已生成: txt/yaml/json/html") is True

    def test_whitespace_only_false(self):
        assert _has_output("  \n  ") is False

    def test_empty_false(self):
        assert _has_output("") is False


class TestErrorBranchClassification:
    """error 分支(returncode≠0)双字段三分支判别: 对应150案例回归(131 error/17 warning/2 保守error)"""

    @pytest.mark.skipif(not __import__("sys").platform == "win32", reason="Windows only")
    def test_real_error_kept_error(self):
        """① stderr 含真实错误(Traceback) → 必须 error, 不得被降级"""
        r = shell("python -c \"raise ValueError('boom')\"", shell_type="cmd")
        assert is_error(r), f"真实Traceback必须判error, actual={r.get('llm_data',{}).get('status')}"

    @pytest.mark.skipif(not __import__("sys").platform == "win32", reason="Windows only")
    def test_benign_warning_with_output_warning(self):
        """② 无真实错误信号 + stdout 有产出 → 降级 warning(实证17例: 任务成功误报被纠正)"""
        # 输出用纯ASCII(done), 避免中文echo在GBK代码页往返乱码 — 小欧 2026-08-11
        r = shell('echo done & exit /b 1', shell_type="cmd")
        assert is_warning(r), f"良性输出+有产出应降warning, actual={r.get('llm_data',{}).get('status')}"
        assert "done" in r.get("llm_data", {}).get("status", {}).get("detail", ""), \
            "warning detail 应保留实际产出"

    @pytest.mark.skipif(not __import__("sys").platform == "win32", reason="Windows only")
    def test_no_output_conservative_error(self):
        """③ 无真实错误信号 + stdout/stderr 均无产出 → 保守 error 防掩盖"""
        r = shell('exit /b 1', shell_type="cmd")
        assert is_error(r), "无产出+非零退出应保守保留error, actual=" + str(r.get('llm_data', {}).get('status'))


class TestRealErrorMarkersCoverage:
    """_REAL_ERROR_MARKERS 白名单覆盖常用真实错误(回归193/131错误集合的判别保真)"""

    @pytest.mark.parametrize("text", [
        "ModuleNotFoundError: No module named 'yaml'",
        "ImportError: cannot import name 'foo'",
        "FileNotFoundError: [Errno 2] No such file",
        "PermissionError: [Errno 13] Permission denied",
        "UnicodeEncodeError: 'gbk' codec can't encode",
        "AttributeError: 'NoneType' object has no attribute 'x'",
        "KeyError: 'missing_key'",
        "TypeError: unsupported operand type(s)",
        "OSError: [WinError 2] 系统找不到指定的文件",
        "bash: line 1: ls: command not found",
        "'grep' 不是内部或外部命令",
        "fatal: not a git repository",
        "ParserError: Missing closing brace",
        "unexpected EOF while looking for matching",
        "Argument list too long",
    ])
    def test_real_error_detected(self, text):
        assert _contains_real_error(text) is True, f"应识别真实错误: {text}"

    @pytest.mark.parametrize("text", [
        "DeprecationWarning: legacy behavior",
        "UserWarning: ignore",
        "Note: this is informational",
        "Info: connected",
        "Non-authoritative answer: 10.0.0.1",
        "torch.set_num_threads(1)",
        "w_ih = torch.quantize_per_tensor(",
    ])
    def test_benign_not_detected(self, text):
        assert _contains_real_error(text) is False, f"不应误判为真实错误: {text}"
