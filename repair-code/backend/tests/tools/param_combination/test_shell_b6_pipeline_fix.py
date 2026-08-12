# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-07 - 小欧 - B6(G2普遍性根治)回归测试: ps_cmd管道层根治后全场景验证(别名fl/ft/fw/错误分流/嵌套/大输出/中文/native stderr/双引擎/进程stderr零残留), 覆盖文档8.9.5回归计划
# 2026-08-07 - 小欧 - B6.1回归测试: 初版31用例(全部ERROR→fixture签名修正→28过3败), 3败挖出B6结构性缺陷
#        BUG#1(分号复合命令rc漏报)/BUG#2(PS5 native stderr误报); 探测挖出BUG#3(LASTEXITCODE残留污染)/
#        BUG#4(throw终止性错误假超时); 定稿B6.1结构修复后31用例全绿; 新增第12节TestB61_Regression/
#        TestB61_PS5_Regression 共10用例固化四缺陷回归保护
"""
test_shell_b6_pipeline_fix — B6 管道层根治回归测试  — 小欧 2026-08-07

背景: 2026-08-07 G2普遍性根治(B6)实施于 shell_engine._exec_locked 的 ps_cmd:
  旧结构: & { cmd } 2>&1 | ForEach-Object { 错误→err文件; 成功→out文件(直接落盘) }
          → 成功分支 Out-File 渲染 FormatEntryData 触发 out-lineoutput → 进程stderr残留 → C12误报
  新结构: & { cmd } 2>&1 | ForEach-Object { 错误→[void]$errs.Add($_); 成功→$_ } |
          Out-String -Width 4096 | Out-File out + 错误最后单独 Out-File err

验证要点(对应文档8.9.5回归计划):
  1) 别名盲区根治: fl/ft/fw 别名 → 进程stderr零残留、out完整、err空、rc=0
  2) 完整命令名: Format-List/Table/Wide → 零残留
  3) 错误分流语义保留: Get-Item Nonexistent → 错误完整进err、rc=1、out干净
  4) 正常命令保真: Get-ChildItem | Select -First 3 → out完整、err空、rc=0
  5) cwd正确更新: cd后 (Get-Location).Path 落盘验证
  6) 中文命令: 输出编码正常、无乱码
  7) native stderr: cmd /c "..." 1>&2 → 错误进入err、out仅stdout
  8) 管道嵌套/子shell: (Get-Service)|fl / cmd;fl / %{ } 子shell → 零残留
  9) 大输出: Get-Service | fl * (~200KB) → out完整、无截断
  10) 双引擎(PS5/PS7) 各跑以上场景
"""
import os
import glob
import tempfile
from pathlib import Path

import pytest

from app.tools.fundamental.execute_shell_command import shell
from app.tools.fundamental.shell_engine import PersistentShell, shell_pool


def is_success(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "success"


def is_error(r):
    return r.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


def _assert_no_c12_residual(engine):
    """验证引擎实例关闭后进程stderr文件无C12残留(out-lineoutput) — 小欧 2026-08-07"""
    if engine._stderr_path and os.path.exists(engine._stderr_path):
        content = Path(engine._stderr_path).read_text(encoding="utf-8", errors="replace")
        assert "out-lineoutput" not in content, f"C12残留检出: {content[:500]}"
        assert "FormatEntryData" not in content, f"C12残留检出: {content[:500]}"


@pytest.fixture(scope="class")
def ps7_engine(request):
    """真实PS7持久引擎实例(通过池获取, 每类一个) — 小欧 2026-08-07"""
    engine = shell_pool.acquire("b6-test-ps7", "ps7", workdir=os.getcwd(), env=None)
    request.cls.engine = engine
    yield engine
    try:
        shell_pool.release(engine)
    except Exception:
        pass


@pytest.fixture(scope="class")
def ps5_engine(request):
    """真实PS5持久引擎实例(通过池获取, 每类一个) — 小欧 2026-08-07"""
    engine = shell_pool.acquire("b6-test-ps5", "ps5", workdir=os.getcwd(), env=None)
    request.cls.engine5 = engine
    yield engine
    try:
        shell_pool.release(engine)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# 1. 别名盲区根治 (R1 枚举保护的软肋, B6 必须覆盖)
# ═══════════════════════════════════════════════════════════════

class TestB6_AliasBlindspot:
    """B6: 别名 fl/ft/fw 必须零残留(这是R1枚举式保护做不到的)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    @pytest.mark.parametrize("cmd", [
        "Get-Service w32time | fl *",
        "Get-Process -Name pwsh | ft Name,Id -AutoSize",
        "Get-Service | fw Name",
    ])
    def test_alias_zero_residual(self, cmd):
        """别名命令 → PROCESS_STDERR零残留、rc=0"""
        r = self.engine.exec(cmd, timeout=30)
        assert r["exit_code"] == 0, f"rc={r['exit_code']} stderr={r['stderr']}"
        _assert_no_c12_residual(self.engine)
        assert "out-lineoutput" not in r["stderr"], f"stderr泄漏: {r['stderr']}"

    def test_alias_output_complete(self):
        """别名命令输出完整(非空白截断)"""
        r = self.engine.exec("Get-Service | ft Name,Status -AutoSize", timeout=30)
        assert r["exit_code"] == 0
        assert len(r["stdout"]) > 100, f"Format输出不应为空白截断: len={len(r['stdout'])}"
        _assert_no_c12_residual(self.engine)


# ═══════════════════════════════════════════════════════════════
# 2. 完整命令名 (Format-Table/List/Wide 原本 R1 覆盖范围)
# ═══════════════════════════════════════════════════════════════

class TestB6_FullFormatNames:
    """B6: 完整命令名回归(原R1保护范围不得退化)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    @pytest.mark.parametrize("cmd", [
        "Get-Service w32time | Format-List *",
        "Get-Process -Name pwsh | Format-Table -AutoSize",
        "Get-Process | Format-Wide Name",
    ])
    def test_full_name_zero_residual(self, cmd):
        r = self.engine.exec(cmd, timeout=30)
        assert r["exit_code"] == 0, f"rc={r['exit_code']} stderr={r['stderr']}"
        _assert_no_c12_residual(self.engine)
        assert "out-lineoutput" not in r["stderr"]


# ═══════════════════════════════════════════════════════════════
# 3. 错误分流语义保留 (B6 相对旧结构/方向A的核心价值)
# ═══════════════════════════════════════════════════════════════

class TestB6_ErrorSeparation:
    """B6: 错误必须完整进err、out干净、rc正确(分流语义零退化)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_error_goes_to_err(self):
        """Get-Item Nonexistent → 错误进err、rc=1、out仅换行"""
        r = self.engine.exec("Get-Item Nonexistent", timeout=30)
        assert r["exit_code"] == 1, f"rc应为1: {r}"
        assert r["stderr"].strip(), "错误必须进err文件"
        assert "Nonexistent" in r["stderr"] or "NotFound" in r["stderr"] \
            or "不存在" in r["stderr"], f"err内容异常: {r['stderr']}"
        assert "out-lineoutput" not in r["stderr"]
        _assert_no_c12_residual(self.engine)

    def test_error_after_success_pipeline(self):
        """错误发生在管道中段 → 错误分流进err、成功输出保留"""
        r = self.engine.exec("Get-Service NOSUCHSVC; Get-Service w32time | fl *", timeout=30)
        assert r["exit_code"] == 1
        assert r["stderr"].strip(), "NOSUCHSVC错误应进err"
        assert "w32time" in r["stdout"].lower() or "Windows Time" in r["stdout"], \
            f"成功部分输出应在out: {r['stdout'][:200]}"


# ═══════════════════════════════════════════════════════════════
# 4. 正常命令保真 + cwd 更新
# ═══════════════════════════════════════════════════════════════

class TestB6_NormalCommand:
    """B6: 普通命令行为不得退化"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_normal_select(self):
        r = self.engine.exec("Get-ChildItem | Select -First 3", timeout=30)
        assert r["exit_code"] == 0
        assert r["stdout"].strip(), "正常命令应有输出"
        assert not r["stderr"].strip(), "正常命令err应为空"

    def test_cwd_update(self, tmp_path):
        """cd后(Get-Location).Path落盘 → 引擎cwd正确更新"""
        r = self.engine.exec(f'Set-Location "{tmp_path}"; (Get-Location).Path', timeout=30)
        assert r["exit_code"] == 0, f"cwd测试失败: {r}"
        assert str(tmp_path).lower() in self.engine._cwd.lower(), \
            f"引擎cwd未更新: engine={self.engine._cwd} expect={tmp_path}"
        # 恢复正常
        self.engine.exec("Set-Location $env:TEMP", timeout=30)

    def test_echo_basic(self):
        """Write-Output 基本命令"""
        r = self.engine.exec("Write-Output hello-b6", timeout=30)
        assert r["exit_code"] == 0
        assert "hello-b6" in r["stdout"], f"输出异常: {r['stdout']}"


# ═══════════════════════════════════════════════════════════════
# 5. 中文命令编码
# ═══════════════════════════════════════════════════════════════

class TestB6_ChineseEncoding:
    """B6: 中文命令/输出编码正常、无乱码"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_chinese_output(self):
        r = self.engine.exec("Write-Output '中文测试B6'", timeout=30)
        assert r["exit_code"] == 0
        assert "中文测试B6" in r["stdout"], f"中文乱码: {r['stdout']!r}"
        assert not r["stderr"].strip()

    def test_chinese_format_list(self):
        """中文列名 Format-List 输出正常"""
        r = self.engine.exec("Get-Service w32time | Format-List Name,DisplayName", timeout=30)
        assert r["exit_code"] == 0
        assert "Name" in r["stdout"], f"输出异常: {r['stdout'][:200]}"
        assert not r["stderr"].strip(), f"err非空: {r['stderr']}"


# ═══════════════════════════════════════════════════════════════
# 6. native stderr (外部命令 stderr → err文件)
# ═══════════════════════════════════════════════════════════════

class TestB6_NativeStderr:
    """B6: 外部native命令stderr必须进err文件"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_cmd_stderr_to_err(self):
        """cmd /c 输出到stderr → 错误进err文件、out干净"""
        r = self.engine.exec('cmd /c "echo native-err 1>&2"', timeout=30)
        assert r["exit_code"] == 0, f"cmd /c 回显stderr rc应为0: {r}"
        assert "native-err" in r["stderr"], f"native stderr应进err: {r['stderr']}"
        assert "native-err" not in r["stdout"], "stderr不应混入stdout"
        _assert_no_c12_residual(self.engine)


# ═══════════════════════════════════════════════════════════════
# 7. 管道嵌套 / 子shell
# ═══════════════════════════════════════════════════════════════

class TestB6_NestedPipeline:
    """B6: 管道嵌套/子shell场景零残留"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    @pytest.mark.parametrize("cmd", [
        "(Get-Service) | fl *",
        "Get-Service; Get-Service | fl *",
        "Get-Service | % { $_.Name } | fl Name",
    ])
    def test_nested_zero_residual(self, cmd):
        r = self.engine.exec(cmd, timeout=30)
        assert r["exit_code"] == 0, f"cmd={cmd} rc={r['exit_code']} stderr={r['stderr']}"
        assert "out-lineoutput" not in r["stderr"]
        _assert_no_c12_residual(self.engine)

    def test_subshell_output_complete(self):
        r = self.engine.exec("(Get-Service | Select -First 5) | ft Name,Status -AutoSize", timeout=30)
        assert r["exit_code"] == 0
        assert len(r["stdout"]) > 50, "子shell Format输出不应空白"


# ═══════════════════════════════════════════════════════════════
# 8. 大输出 (Get-Service | fl * ~200KB, 防截断)
# ═══════════════════════════════════════════════════════════════

class TestB6_LargeOutput:
    """B6: 大输出完整、无截断、零残留"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_large_output_complete(self):
        r = self.engine.exec("Get-Service | fl *", timeout=60)
        assert r["exit_code"] == 0, f"大输出失败: {r['stderr'][:200]}"
        assert len(r["stdout"]) > 50000, f"大输出不应被截断: len={len(r['stdout'])}"
        assert not r["stderr"].strip(), f"大输出err应空: {r['stderr'][:200]}"
        _assert_no_c12_residual(self.engine)


# ═══════════════════════════════════════════════════════════════
# 9. 双引擎 (PS5) 全场景
# ═══════════════════════════════════════════════════════════════

class TestB6_PS5_DualEngine:
    """B6: PS5 引擎全场景(编码/BOM/格式排版差异兼容)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps5_engine):
        pass

    def test_ps5_alias_zero_residual(self):
        r = self.engine5.exec("Get-Service w32time | fl *", timeout=30)
        assert r["exit_code"] == 0, f"PS5 rc={r['exit_code']} stderr={r['stderr']}"
        assert "out-lineoutput" not in r["stderr"]
        _assert_no_c12_residual(self.engine5)

    def test_ps5_full_name(self):
        r = self.engine5.exec("Get-Service w32time | Format-List *", timeout=30)
        assert r["exit_code"] == 0
        assert "out-lineoutput" not in r["stderr"]
        _assert_no_c12_residual(self.engine5)

    def test_ps5_error_to_err(self):
        """PS5错误分流: BOM处理 + 错误进err"""
        r = self.engine5.exec("Get-Item Nonexistent", timeout=30)
        assert r["exit_code"] == 1
        assert r["stderr"].strip(), "PS5错误应进err"
        assert "out-lineoutput" not in r["stderr"]
        _assert_no_c12_residual(self.engine5)

    def test_ps5_native_stderr(self):
        r = self.engine5.exec('cmd /c "echo ps5-native-err 1>&2"', timeout=30)
        assert r["exit_code"] == 0
        assert "ps5-native-err" in r["stderr"], f"PS5 native stderr应进err: {r['stderr']}"

    def test_ps5_chinese(self):
        r = self.engine5.exec("Write-Output '中文PS5测试'", timeout=30)
        assert r["exit_code"] == 0
        assert "中文PS5测试" in r["stdout"], f"PS5中文乱码: {r['stdout']!r}"


# ═══════════════════════════════════════════════════════════════
# 10. shell() 业务入口全链路(execute_shell_command → R1移除后 → 引擎B6)
# ═══════════════════════════════════════════════════════════════

class TestB6_ShellEntryPoint:
    """B6: shell()业务入口回归(命令名/别名/错误/中文全链路)"""

    def test_shell_format_list(self):
        r = shell("Get-Service w32time | Format-List *", shell_type="ps7")
        assert is_success(r), f"shell Format-List失败: {r.get('data',{}).get('stderr','')[:200]}"
        assert "out-lineoutput" not in r["data"].get("stderr", "")

    def test_shell_alias(self):
        """别名 fl → 业务入口零残留(R1移除后由B6管道层兜底)"""
        r = shell("Get-Service w32time | fl *", shell_type="ps7")
        assert is_success(r), f"shell别名失败: {r}"
        assert "out-lineoutput" not in r["data"].get("stderr", "")

    def test_shell_error(self):
        """业务入口错误分流: rc=1、错误进stderr、exec_code=error"""
        r = shell("Get-Item Nonexistent", shell_type="ps7")
        assert is_error(r), f"错误命令应为error: {r['llm_data']['status']['exec_code']}"
        assert r["llm_data"]["status"]["exec_code"] == "error"
        assert r["data"]["stderr"], "错误应进data.stderr"

    def test_shell_success_stderr_empty(self):
        """成功命令 stderr 应为空 → exec_code=success"""
        r = shell("Get-Service w32time | Format-List *", shell_type="ps7")
        assert is_success(r)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert not r["data"].get("stderr", "").strip(), "成功命令stderr应为空"

    def test_shell_chinese(self):
        r = shell("Write-Output '业务入口中文'", shell_type="ps7")
        assert is_success(r)
        assert "业务入口中文" in r["data"].get("stdout", ""), f"中文输出异常: {r}"


# ═══════════════════════════════════════════════════════════════
# 11. 资源回收: 引擎关闭后临时文件零残留(防泄漏)
# ═══════════════════════════════════════════════════════════════

class TestB6_TempFileCleanup:
    """B6: 引擎生命周期后临时文件无泄漏(含C12残留文件)"""

    def test_no_stale_temp_files(self):
        """关闭后无本次调用产生的临时文件残留"""
        tmpdir = tempfile.gettempdir()
        before = set(glob.glob(os.path.join(tmpdir, "tmp*.ps1")) +
                     glob.glob(os.path.join(tmpdir, "tmp*.out")) +
                     glob.glob(os.path.join(tmpdir, "tmp*.err")) +
                     glob.glob(os.path.join(tmpdir, "tmp*.cwd")))
        engine = PersistentShell(workdir=os.getcwd(), shell_type="ps7")
        engine._ensure_alive(env=None)
        engine.exec("Get-Service | fl *", timeout=30)
        engine.exec("Get-Item Nonexistent", timeout=30)
        engine.close()
        after = set(glob.glob(os.path.join(tmpdir, "tmp*.ps1")) +
                    glob.glob(os.path.join(tmpdir, "tmp*.out")) +
                    glob.glob(os.path.join(tmpdir, "tmp*.err")) +
                    glob.glob(os.path.join(tmpdir, "tmp*.cwd")))
        leaked = after - before
        assert not leaked, f"临时文件泄漏: {leaked}"


# ═══════════════════════════════════════════════════════════════
# 12. B6.1 四缺陷回归(BUG#1-4, 由B6回归测试+探测挖出, 三堂会审定稿)
# ═══════════════════════════════════════════════════════════════

class TestB61_Regression:
    """B6.1: BUG#1-4 修复回归(PS7/PS5双引擎)"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps7_engine):
        pass

    def test_bug1_semicolon_error_rc(self):
        """BUG#1: `;`复合命令前段出错 → rc必须=1(非0漏报)、错误进err、成功输出保留"""
        r = self.engine.exec("Get-Service NOSUCHSVC; Get-Service w32time | fl *", timeout=30)
        assert r["exit_code"] == 1, f"BUG#1: rc应为1实际{r['exit_code']}: {r}"
        assert r["stderr"].strip(), f"BUG#1: 错误应进err: {r['stderr']}"
        assert "w32time" in r["stdout"].lower() or "Windows Time" in r["stdout"], \
            f"BUG#1: 成功部分输出应保留: {r['stdout'][:200]}"
        _assert_no_c12_residual(self.engine)

    def test_bug1_semicolon_three_cmds(self):
        """BUG#1延伸: 中段错误+前/后成功 → rc=1、输出完整"""
        r = self.engine.exec("Write-Output head; Get-Item NOSUCHFILE; Write-Output tail", timeout=30)
        assert r["exit_code"] == 1, f"rc应为1: {r}"
        assert r["stdout"].strip(), "成功部分输出应在out"

    def test_bug2_native_stderr_rc_zero(self):
        """BUG#2: native写stderr(实际成功) → rc=0(非误报)、stderr进err文件"""
        r = self.engine.exec('cmd /c "echo native-err 1>&2"', timeout=30)
        assert r["exit_code"] == 0, f"BUG#2: native stderr rc应为0实际{r['exit_code']}: {r}"
        assert "native-err" in r["stderr"], f"BUG#2: native stderr应进err: {r['stderr']}"

    def test_bug3_last_exit_code_residual(self):
        """BUG#3: native exit3后再跑cmdlet错误 → rc=1(非残留3)"""
        r1 = self.engine.exec('cmd /c "exit 3"', timeout=30)
        assert r1["exit_code"] == 3
        r2 = self.engine.exec("Get-Item Nonexistent", timeout=30)
        assert r2["exit_code"] == 1, f"BUG#3: 残留污染rc应1实际{r2['exit_code']}: {r2}"
        r3 = self.engine.exec("Write-Output clean", timeout=30)
        assert r3["exit_code"] == 0, f"BUG#3: 正常命令rc应0实际{r3['exit_code']}: {r3}"

    def test_bug4_throw_terminating(self):
        """BUG#4: throw终止性错误 → rc=1(非rc=-1)、错误文本进err、不触发超时杀进程"""
        r = self.engine.exec('Write-Output before; throw "boom"; Write-Output after', timeout=30)
        assert r["exit_code"] == 1, f"BUG#4: throw rc应1实际{r['exit_code']}: {r}"
        assert "boom" in r["stderr"], f"BUG#4: throw文本应进err: {r['stderr']}"
        assert "before" in r["stdout"], f"BUG#4: throw前输出应保留: {r['stdout'][:200]}"
        assert "after" not in r["stdout"], "throw后语句不应执行"
        assert not r.get("timed_out"), "BUG#4: 不应假超时"

    def test_bug4_throw_shell_entry(self):
        """BUG#4经业务入口: shell()错误命令 → exec_code=error(非假超时)"""
        r = shell('throw "boom-b61"', shell_type="ps7")
        assert is_error(r), f"BUG#4入口: throw应为error: {r['llm_data']['status']['exec_code']}"
        assert "boom-b61" in r["data"].get("stderr", ""), f"throw文本应进stderr: {r}"


class TestB61_PS5_Regression:
    """B6.1: PS5引擎 BUG#1-4 双引擎一致性"""

    @pytest.fixture(autouse=True)
    def _setup(self, ps5_engine):
        pass

    def test_ps5_bug1_semicolon(self):
        r = self.engine5.exec("Get-Service NOSUCHSVC; Get-Service w32time | fl *", timeout=30)
        assert r["exit_code"] == 1, f"PS5 BUG#1: rc应1实际{r['exit_code']}: {r}"
        assert r["stderr"].strip(), "PS5错误应进err"
        _assert_no_c12_residual(self.engine5)

    def test_ps5_bug2_native_stderr(self):
        r = self.engine5.exec('cmd /c "echo ps5-native-err 1>&2"', timeout=30)
        assert r["exit_code"] == 0, f"PS5 BUG#2: rc应0实际{r['exit_code']}: {r}"
        assert "ps5-native-err" in r["stderr"], f"PS5 native stderr应进err: {r['stderr']}"

    def test_ps5_bug3_last_exit_residual(self):
        self.engine5.exec('cmd /c "exit 7"', timeout=30)
        r = self.engine5.exec("Get-Item Nonexistent", timeout=30)
        assert r["exit_code"] == 1, f"PS5 BUG#3: rc应1实际{r['exit_code']}: {r}"

    def test_ps5_bug4_throw(self):
        r = self.engine5.exec('Write-Output before; throw "ps5boom"', timeout=30)
        assert r["exit_code"] == 1, f"PS5 BUG#4: rc应1实际{r['exit_code']}: {r}"
        assert "ps5boom" in r["stderr"], f"PS5 throw文本应进err: {r['stderr']}"
        assert not r.get("timed_out"), "PS5 throw不应假超时"
