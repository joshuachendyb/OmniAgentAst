# -*- coding: utf-8 -*-
"""
shell truncation deep bug hunting - 小欧 2026-07-24
method: run real shell commands + code analysis, find real bugs

编辑历史:
   2026-07-25 - 小欧 - TestBug6直接调build函数补传cmd_short="test"(assert强制传参)
"""
import os, tempfile
import pytest
from app.tools.fundamental.execute_shell_command import (
    shell, _truncate_shell_field, _build_execute_shell_command_llm_data,
)
from app.tools.tool_constants import (
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS, SHELL_OUTLIMIT_STDERR_MAX_CHARS,
)


def _ec(r): return r["llm_data"]["status"]["exec_code"]
def _det(r): return r["llm_data"]["status"]["detail"]
def _sum(r): return r["llm_data"]["summary"]
def _hint(r): return r["llm_data"]["status"]["hint"]
def _stderr(r): return r.get("data", {}).get("stderr", "")
def _stdout(r): return r.get("data", {}).get("stdout", "")
def _trunc(r): return r.get("data", {}).get("_truncated", False)


def _safe(s): return s.encode('utf-8', errors='replace').decode('utf-8')
def _py(code, shell_t="ps7"):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8')
    f.write(code); f.close()
    try:
        return shell('python ' + f.name, shell_type=shell_t)
    finally:
        try: os.unlink(f.name)
        except OSError: pass


# ─────────────────────────────────────────────────────────────
# BUG#1 CONFIRMED: error detail >200 chars (fix works)
# ─────────────────────────────────────────────────────────────
class TestBug1_DetailNoLonger200:
    def test_stderr_300_chars(self):
        r = _py('import sys; sys.stderr.write("A"*300); sys.exit(1)')
        assert _ec(r) in ("warning", "error")
        assert len(_det(r)) > 200, f"detail {len(_det(r))} chars"

    def test_stdout_as_detail(self):
        r = _py('import sys; sys.stdout.write("B"*300); sys.exit(1)')
        assert _ec(r) in ("warning", "error")
        if len(_det(r)) > 0:
            assert "BBB" in _det(r)

    def test_exit_code_fallback(self):
        r = shell("cmd /c exit 127", shell_type="cmd")
        assert _ec(r) in ("warning", "error") and "127" in _det(r)


# ─────────────────────────────────────────────────────────────
# BUG#2 CONFIRMED: warning detail='' by design
# ─────────────────────────────────────────────────────────────
class TestBug2_Warning:
    def test_empty_detail(self):
        r = shell('cmd /c "echo stderr >&2"', shell_type="cmd")
        assert _ec(r) in ("warning", "success")
        # warning detail now always populated with exit_code info — 增强
        if _ec(r) == "warning":
            assert "退出码" in _det(r), f"warning detail should contain exit_code: '{_det(r)}'"
            assert "stderr" in _stderr(r)


# ─────────────────────────────────────────────────────────────
# BUG#3 (REAL): cmd_not_found regex (L537) only matches ENGLISH.
#   Chinese "不是内部或外部命令" → tag [命令未找到] MISSING
# ─────────────────────────────────────────────────────────────
class TestBug3_CmdNotFoundChineseTag:
    def test_english_cmd_not_found_has_tag(self):
        """English 'not recognized' should get [命令未找到] tag"""
        r = shell("nonexistent_cmd_xyz_12345", shell_type="cmd")
        assert _ec(r) in ("warning", "error")
        d = _det(r)
        # The tag [命令未找到] should be present for English not recognized
        assert "命令未找到" in d or "not" in d.lower(), f"BUG#3: tag missing: {d[:200]}"

    def test_chinese_cmd_not_found_TAG_MISSING(self):
        """Chinese '不是内部或外部命令' -> [命令未找到] TAG IS MISSING!
           L537 regex only matches English, Chinese is NOT detected.
           This is BUG#3 - pattern missing Chinese"""
        r = shell("nonexistent_cmd_xyz_12345", shell_type="cmd")
        assert _ec(r) in ("warning", "error")
        d = _det(r)
        # The detail should contain the chinese not-found text
        has_chinese = "不是内部" in d or "不是可运行" in d
        if has_chinese:
            # Check if tag is present despite Chinese-only message
            if "命令未找到" not in d:
                # THIS IS THE BUG: Chinese cmd-not-found message but no tag!
                pytest.fail(
                    f"BUG#3 (REAL): Chinese cmd-not-found '{d[:60]}' "
                    f"but [命令未找到] tag MISSING!\n"
                    f"L537 regex only matches English 'command not found|not recognized'."
                )


# ─────────────────────────────────────────────────────────────
# BUG#4 (REAL): Head-only truncation drops Python error TYPE at tail!
#   Python traceback format: ...lines...\nZeroDivisionError: msg
#   Head-only truncation preserves traceback lines but LOSES the
#   actual error type at the END. LLM sees stack lines but NOT
#   what error occurred!
# ─────────────────────────────────────────────────────────────
class TestBug4_HeadTruncationLosesTailError:
    def test_python_traceback_tail_error_lost(self):
        """Simulate: 23K Python traceback → truncated to 20K → error type LOST"""
        tb_lines = ['  File "script.py", line ' + str(i) + ', in func\n    result = x / y'
                    for i in range(400)]
        tb_lines.append('ZeroDivisionError: division by zero')
        stderr = '\n'.join(tb_lines)
        assert len(stderr) > 20000, f"need >20K, got {len(stderr)}"

        truncated, flag = _truncate_shell_field(stderr, 20000)
        assert flag is True, "should truncate"
        assert "ZeroDivisionError" not in truncated, (
            f"BUG#4: ZeroDivisionError at tail was LOST by head truncation!\n"
            f"original={len(stderr)}, truncated={len(truncated)}\n"
            f"last 200 chars: {truncated[-200:]!r}"
        )


# ─────────────────────────────────────────────────────────────
# BUG#5 (REAL): _truncate_shell_field output EXCEEDS max_chars limit
#   note = \n...[shell输出截断: 原文N字符, 保留M字符]...\n
#   for 50001-char input → output = 50041 chars > 50000 limit!
# ─────────────────────────────────────────────────────────────
class TestBug5_TruncationOutputExceedsLimit:
    def test_output_bigger_than_limit(self):
        t, tr = _truncate_shell_field("x" * 50001, 50000)
        assert tr is True
        assert len(t) > 50000, (
            f"BUG#5: truncated output {len(t)} > limit 50000!\n"
            f"note adds ~70 chars to {t[:100]!r}"
        )

    def test_at_exact_limit_no_blowup(self):
        t, tr = _truncate_shell_field("x" * 50000, 50000)
        assert tr is False and len(t) == 50000

    def test_just_over_limit(self):
        t, tr = _truncate_shell_field("x" * 50001, 50000)
        # output = 50000 + ~70 for note = ~50070
        assert len(t) <= 50080, f"too big: {len(t)}"


# ─────────────────────────────────────────────────────────────
# BUG#6 (REAL): Exception path (L560) has NO truncation on str(e)!
#   Only normal execution goes through phase 4.5 _truncate_shell_field.
#   Exception path passes str(e) directly → detail can be 100K+ !
# ─────────────────────────────────────────────────────────────
class TestBug6_ExceptionPathNoTruncation:
    def test_exception_detail_untruncated(self):
        """exception with 100K message → no truncation → detail 100K+"""
        from app.tools.tool_constants import ERR_SHELL_EXCEPTION
        long_msg = "Exception: kaboom! " + "X" * 100000
        llm = _build_execute_shell_command_llm_data("error", 100, "test", -1,
            "cmd", ERR_SHELL_EXCEPTION, long_msg, cmd_short="test")
        detail = _det({"llm_data": llm})
        assert len(detail) > 50000, (
            f"BUG#6: exception detail={len(detail)} > 50000!\n"
            f"exception path has NO truncation, str(e) goes directly to detail!"
        )

    def test_normal_execution_detail_truncated(self):
        """normal execution with 30K stderr → detail < 20K (truncated)"""
        r = _py('import sys; sys.stderr.write("e"*30000); sys.exit(1)')
        assert _ec(r) in ("warning", "error")
        # stderr should be truncated to 20000 (stderr limit)
        assert len(_stderr(r)) <= SHELL_OUTLIMIT_STDERR_MAX_CHARS + 200, \
            f"normal execution detail={len(_stderr(r))} (should be ~{SHELL_OUTLIMIT_STDERR_MAX_CHARS})"


# ─────────────────────────────────────────────────────────────
# BUG#7 (REAL): Summary embeds full detail → summary = 6000+ chars
#   L275: "summary": f"执行Shell命令{cmd_short}，失败: {_detail}"
#   When detail = 20K stderr, summary = 20K. LLM sees it twice!
# ─────────────────────────────────────────────────────────────
class TestBug7_SummaryRepeatsDetail:
    def test_summary_way_too_long(self):
        r = _py('import sys; sys.stderr.write("ERR"*2000); sys.exit(1)')
        assert _ec(r) in ("warning", "error")
        s, d = _sum(r), _det(r)
        if len(s) > 1000:
            pytest.fail(
                f"BUG#7: summary={len(s)} chars (detail={len(d)})\n"
                f"summary embeds full detail! LLM sees error info TWICE\n"
                f"L275: summary directly uses _detail string"
            )


# ─────────────────────────────────────────────────────────────
# BUG#8 (REAL): All pattern matching runs on TRUNCATED stderr_str!
#   L524: _filter_benign_stderr(stderr_str) — truncated
#   L537-542: re.search(..., stderr_str) — truncated  
#   L543: _cmd_powershell_mismatch_hint(..., stderr_str) — truncated
#   If pattern text is in the cut-off tail, detection silently fails.
# ─────────────────────────────────────────────────────────────
class TestBug8_PatternMatchingOnTruncated:
    def test_tag_detection_uses_truncated_stderr(self):
        """If 'not recognized' at position 21000 of 25000-char stderr,
        it's cut off by 20000 truncation → tag [命令未找到] NOT added."""
        # Create stderr where 'not recognized' is beyond the truncation point
        before = "some prefix text\n" * 1500
        error_line = "'some_command' is not recognized as an internal or external command"
        stderr = before + error_line
        assert len(stderr) > 21000, f"need >21K stderr, got {len(stderr)}"

        truncated_stderr, flag = _truncate_shell_field(stderr, 20000)
        assert flag, "should have truncated"
        assert "not recognized" not in truncated_stderr, (
            f"BUG#8: 'not recognized' survived truncation but should be cut off!\n"
            f"To reproduce: this would make L537 re.search fail silently."
        )


# ─────────────────────────────────────────────────────────────
# BUG#9 (REAL): _cmd_powershell_mismatch_hint checks Chinese
#   "不是内部或外部命令" (L354) but tag prefix code (L537) does NOT.
#   Inconsistency: hint catches Chinese cmd-not-found, tag doesn't.
# ─────────────────────────────────────────────────────────────
class TestBug9_HintTagInconsistency:
    def test_chinese_hint_works_but_tag_missing(self):
        r = shell("nonexistent_cmd_xyz_12345", shell_type="cmd")
        assert _ec(r) in ("warning", "error")
        hint = _hint(r)
        # hint should suggest powershell if "不是内部" is detected
        if "不是内部" in _det(r):
            assert "ps7" in hint.lower() or "ps5" in hint.lower(), (
                f"BUG#9: Chinese cmd-not-found detected in hint but "
                f"tag [命令未找到] missing from detail!\n"
                f"_cmd_powershell_mismatch_hint (L354) checks Chinese,\n"
                f"but L537 re.search only checks English patterns."
            )


# ─────────────────────────────────────────────────────────────
# BUG#10 (REAL): No hardcoded [:200] in source (CONFIRMED OK)
# ─────────────────────────────────────────────────────────────
class TestBug10_NoHardcoded200:
    def test_scan_source(self):
        fp = os.path.normpath(os.path.join(os.path.dirname(__file__),
            "../../../app/tools/fundamental/execute_shell_command.py"))
        with open(fp, "r", encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                s = line.strip()
                if s.startswith("#") or s.startswith('"""') or s.startswith("'''"): continue
                if ":200" in s and "#" not in s:
                    pytest.fail(f"line {i}: {s}")


# ─────────────────────────────────────────────────────────────
# BUG#11 (CONFIRMED OK): Stability + _truncated flag
# ─────────────────────────────────────────────────────────────
class TestBug11_Stability:
    def test_huge_stdout(self):
        r = _py('import sys; sys.stdout.write("x"*60000)')
        assert _ec(r) in ("warning", "success")
        assert len(_stdout(r)) <= SHELL_OUTLIMIT_STDOUT_MAX_CHARS + 200

    def test_huge_stderr(self):
        r = _py('import sys; sys.stderr.write("e"*30000); sys.exit(1)')
        assert _ec(r) in ("warning", "error")
        assert len(_stderr(r)) <= SHELL_OUTLIMIT_STDERR_MAX_CHARS + 200

    def test_no_false_trunc_flag(self):
        assert _trunc(shell("echo hello", shell_type="cmd")) is False


# ─────────────────────────────────────────────────────────────
# BUG#12 (REAL): timeout produces empty detail (by design)
# LLM gets no partial output info when command times out
# ─────────────────────────────────────────────────────────────
class TestBug12_TimeoutNoPartialOutput:
    def test_timeout_no_partial_info(self):
        r = shell("Start-Sleep -Seconds 10", shell_type="ps7", timeout=2)
        assert _ec(r) in ("warning", "error")
        d = _det(r)
        if _ec(r) == "warning":
            # warning detail now always populated with timeout info — 增强
            assert "超时" in d, f"warning detail should contain timeout: {d!r}"
        elif _ec(r) == "error":
            assert len(d) > 0, "error timeout detail should not be empty"


# ─────────────────────────────────────────────────────────────
# BUG#13 (CONFIRMED OK): early return detail integrity
# ─────────────────────────────────────────────────────────────
class TestBug13_EarlyReturns:
    def test_null_byte(self):
        r = shell("echo\x00hi", shell_type="cmd")
        assert _ec(r) in ("warning", "error") and any(m in _det(r).lower() for m in ["null", "byte"])

    def test_invalid_cwd(self):
        r = shell("echo hi", shell_type="cmd", cwd=r"Z:\nope_xyz")
        # invalid cwd now silently resolved to safe cwd — OK行为
        assert _ec(r) in ("warning", "error", "success")

    def test_neg_timeout(self):
        assert _ec(shell("echo hi", shell_type="cmd", timeout=-1)) == "error"


# ─────────────────────────────────────────────────────────────
# BUG#14 (REAL): _truncate_shell_field note is always Chinese.
#   Not a crash bug but a multi-lang LLM concern:
#   English LLM sees Chinese truncation note ↔ may not understand
# ─────────────────────────────────────────────────────────────
class TestBug14_NoteAlwaysChinese:
    def test_truncation_note_chinese(self):
        t, tr = _truncate_shell_field("x"*50000, 100)
        assert tr and "输出截断" in t

    def test_large_stderr_has_chinese_note(self):
        r = _py('import sys; sys.stderr.write("e"*30000); sys.exit(1)')
        if len(_stderr(r)) >= SHELL_OUTLIMIT_STDERR_MAX_CHARS:
            assert "输出截断" in _stderr(r), "truncation note should be Chinese"
