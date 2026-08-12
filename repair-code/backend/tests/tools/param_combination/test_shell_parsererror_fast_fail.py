# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-08 - 小欧 - B6.3 ParserError快速失败回归测试(北京老陈驱动, 三堂会审通过): 覆盖4类常见ParserError(尾逗号/
#        括号不匹配/引号未闭合/操作符错误)+语法正确多行(防B6.2语义退化)+throw(防BUG#4回归)共6个护栏用例。
#        断言核心: rc=1 + err含ParserError原文 + 耗时<5s(防假超时60s回退)。测试文件仅验证用途, 遵循铁律不commit。
"""
test_shell_parsererror_fast_fail — B6.3 ParserError快速失败回归测试  — 小欧 2026-08-08

背景: 2026-08-08 引擎修正(B6.3): command从内联改独立cmd.ps1文件, ps_cmd内dot-source该文件
  +try/catch包在dot-source外层 → 解析期错误(ParserError)由运行时catch捕获 → rc/err文件正常落盘
  → 引擎立即返回build_error, 不再空等60s假超时(问题二真病根, 见日志挖掘报告§10)。
  旧内联结构: ParserError是编译期错误, 发生在try块进入之前, catch接不住 → rc文件不写 → 假超时。

验证要点(对应文档§10.5回归护栏6用例):
  1) 尾逗号 @('x','y',) → rc=1 + err含ParserError + <5s
  2) 括号不匹配 (1+2 → 同上
  3) 引号未闭合 "unterminated string → 同上
  4) 操作符错误 1 +* 2 → 同上
  5) 语法正确多行foreach → rc=0正常(防B6.2语义退化)
  6) throw终止性错误 → rc=1 + stdout保留throw前内容(防BUG#4回归)
"""
import time

import pytest

from app.tools.fundamental.shell_engine import PersistentShell, shell_pool

# 假超时护栏: ParserError快速失败应<5s(旧结构空等60s)
_MAX_FAST_FAIL_SECONDS = 5


@pytest.fixture(scope="class")
def ps7_engine(request):
    """真实PS7持久引擎实例(通过池获取, 每类一个) — 小欧 2026-08-08"""
    engine = shell_pool.acquire("parsererror-test-ps7", "ps7", workdir=r"F:\test_dir", env=None)
    request.cls.engine = engine
    yield engine
    try:
        shell_pool.release(engine)
    except Exception:
        pass


@pytest.fixture(scope="class")
def ps5_engine(request):
    """真实PS5持久引擎实例(通过池获取, 每类一个) — 小欧 2026-08-08"""
    engine = shell_pool.acquire("parsererror-test-ps5", "ps5", workdir=r"F:\test_dir", env=None)
    request.cls.engine5 = engine
    yield engine
    try:
        shell_pool.release(engine)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# 1. ParserError 快速失败护栏(4类常见语法错误, PS7)
# ═══════════════════════════════════════════════════════════════

class TestParserError_FastFail:
    """B6.3: 4类常见ParserError → 快速失败(rc=1 + err原文 + <5s)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_trailing_comma_array(self):
        """用例1(尾逗号): @('x','y',) → rc=1 + err含ParserError + <5s"""
        start = time.time()
        r = self.engine.exec("@('x','y',)", timeout=30)
        elapsed = time.time() - start
        assert r["exit_code"] == 1, f"尾逗号rc应1实际{r['exit_code']}: {r}"
        assert "ParserError" in r["stderr"] or "Missing expression" in r["stderr"], \
            f"尾逗号错误应进err: {r['stderr']}"
        assert not r.get("timed_out"), "尾逗号不应假超时"
        assert elapsed < _MAX_FAST_FAIL_SECONDS, \
            f"尾逗号应快速失败(<{_MAX_FAST_FAIL_SECONDS}s), 实际{elapsed:.2f}s(疑似假超时回退)"

    def test_unmatched_paren(self):
        """用例2(括号不匹配): (1+2 → rc=1 + err含ParserError + <5s"""
        start = time.time()
        r = self.engine.exec("(1+2", timeout=30)
        elapsed = time.time() - start
        assert r["exit_code"] == 1, f"括号不匹配rc应1实际{r['exit_code']}: {r}"
        assert "ParserError" in r["stderr"], f"括号错误应进err: {r['stderr']}"
        assert not r.get("timed_out"), "括号不匹配不应假超时"
        assert elapsed < _MAX_FAST_FAIL_SECONDS, \
            f"括号不匹配应快速失败(<{_MAX_FAST_FAIL_SECONDS}s), 实际{elapsed:.2f}s"

    def test_unterminated_string(self):
        """用例3(引号未闭合): "unterminated string → rc=1 + err含ParserError + <5s"""
        start = time.time()
        r = self.engine.exec('"unterminated string', timeout=30)
        elapsed = time.time() - start
        assert r["exit_code"] == 1, f"引号未闭合rc应1实际{r['exit_code']}: {r}"
        assert "ParserError" in r["stderr"], f"引号未闭合错误应进err: {r['stderr']}"
        assert not r.get("timed_out"), "引号未闭合不应假超时"
        assert elapsed < _MAX_FAST_FAIL_SECONDS, \
            f"引号未闭合应快速失败(<{_MAX_FAST_FAIL_SECONDS}s), 实际{elapsed:.2f}s"

    def test_bad_operator(self):
        """用例4(操作符错误): 1 +* 2 → rc=1 + err含ParserError + <5s"""
        start = time.time()
        r = self.engine.exec("1 +* 2", timeout=30)
        elapsed = time.time() - start
        assert r["exit_code"] == 1, f"操作符错误rc应1实际{r['exit_code']}: {r}"
        assert "ParserError" in r["stderr"], f"操作符错误应进err: {r['stderr']}"
        assert not r.get("timed_out"), "操作符错误不应假超时"
        assert elapsed < _MAX_FAST_FAIL_SECONDS, \
            f"操作符错误应快速失败(<{_MAX_FAST_FAIL_SECONDS}s), 实际{elapsed:.2f}s"


# ═══════════════════════════════════════════════════════════════
# 2. 语义保持护栏(防退化)
# ═══════════════════════════════════════════════════════════════

class TestParserError_Semantics:
    """B6.3: 语法正确命令与终止性错误语义不退化"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_valid_multiline_foreach(self):
        """用例5(语法正确多行foreach): → rc=0 正常(防B6.2语义退化)"""
        r = self.engine.exec(
            "$files = @('a', 'b'); foreach ($f in $files) { Write-Output \"file: $f\" }",
            timeout=30)
        assert r["exit_code"] == 0, f"正常多行命令rc应0实际{r['exit_code']}: {r}"
        assert "file: a" in r["stdout"] and "file: b" in r["stdout"], \
            f"正常多行输出应完整: {r['stdout']}"
        assert not r.get("timed_out"), "正常命令不应超时"

    def test_throw_preserves_stdout(self):
        """用例6(throw终止性错误): → rc=1 + stdout保留throw前内容(防BUG#4回归)"""
        r = self.engine.exec(
            'Write-Output before; throw "boom-parsererror"; Write-Output after', timeout=30)
        assert r["exit_code"] == 1, f"throw rc应1实际{r['exit_code']}: {r}"
        assert "boom-parsererror" in r["stderr"], f"throw文本应进err: {r['stderr']}"
        assert "before" in r["stdout"], f"throw前输出应保留: {r['stdout'][:200]}"
        assert "after" not in r["stdout"], "throw后语句不应执行"
        assert not r.get("timed_out"), "throw不应假超时"


# ═══════════════════════════════════════════════════════════════
# 3. PS5 双引擎一致性(4类ParserError快速失败)
# ═══════════════════════════════════════════════════════════════

class TestParserError_PS5_FastFail:
    """B6.3: PS5引擎 4类ParserError快速失败一致性"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps5_engine):
        pass

    @pytest.mark.parametrize("bad_cmd", [
        "@('x','y',)",
        "(1+2",
        '"unterminated string',
        "1 +* 2",
    ])
    def test_ps5_bad_cmd_fast_fail(self, bad_cmd):
        """PS5: 各类ParserError → rc=1 + err含ParserError + <5s"""
        start = time.time()
        r = self.engine5.exec(bad_cmd, timeout=30)
        elapsed = time.time() - start
        assert r["exit_code"] == 1, f"PS5 [{bad_cmd}] rc应1实际{r['exit_code']}: {r}"
        assert "ParserError" in r["stderr"], f"PS5 [{bad_cmd}] 错误应进err: {r['stderr']}"
        assert not r.get("timed_out"), f"PS5 [{bad_cmd}] 不应假超时"
        assert elapsed < _MAX_FAST_FAIL_SECONDS, \
            f"PS5 [{bad_cmd}] 应快速失败(<{_MAX_FAST_FAIL_SECONDS}s), 实际{elapsed:.2f}s"
