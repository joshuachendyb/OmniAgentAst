# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: 临时输出文件读取保护线改引用 tool_constants.SHELL_OUTPUT_FILE_MAX_BYTES(原 _MAX_OUTPUT_SZ=10MB), 功能零退化
# 2026-07-18 - 小沈 - 修复多行命令(如 python -c "..." 含换行)经 -Command - 从stdin喂入导致PowerShell解析器卡死等待输入(见 logs 2026-07-18 21:34-21:44 step=15 跑满600s超时): 改为写入.ps1文件 + 向持久pwsh喂一句【单行】dot-source投递, 多行内容留在文件内不再经stdin流, 死锁消除; 功能零退化
# 2026-07-20 - 小欧 - 门限治理(章6.4/3.5): SHELL_OUTPUT_FILE_MAX_BYTES 改名 SHELL_OUTLIMIT_RAW_BYTES(私有内部常量加 INER_ 前缀); 删除 shell_engine.py 本地重复定义, 统一引用 tool_constants 单源
# 2026-07-23 - 小欧 - 北京老陈驱动: safe_read_file 去掉 10MB head+tail 限制, 改为纯读; 删 SHELL_OUTLIMIT_RAW_BYTES import (仅保留 50K/20K tool 输出截断, 不需要磁盘读限制+字符截断两层)
# 2026-07-26 - 小沈 - 超时统一: 127行timeout=30→DEFAULT_TIMEOUT_SEC, 276行timeout=5→SUBPROCESS_TIMEOUT_SHORT, 286行timeout=5→SUBPROCESS_TIMEOUT_SHORT
# 2026-07-27 - 小欧 - 安全: exec()/_ensure_alive()/_start()加env参数, PS进程不再直接copy os.environ, 由调用方传_sanitize_env()过滤API key
# 2026-07-28 - 小欧 - 欧阳BUG-01+BUG-12修复: _class_lock Lock→RLock防死锁; _poll_for_file delay 5ms/×1.5/0.1→100ms/×2/1.0减少系统调用
# 2026-07-28 - 小欧 - 新增 _preprocess_command 命令预处理: PS5.1 将 && 降级为 ;(顺序执行), Windows 将 python3 降级为 python
# 2026-07-28 - 小欧 - 修复Bug-2+Bug-3: python3替换改用regex单词边界(避免误伤路径/版本号/包名); &&替换改用引号感知状态机(仅替换引号外的&&, 避免误伤字符串字面量)
# 2026-07-28 - 小欧 - 删除死代码 _replace_ampersand（&&/|| 翻译已由 execute_shell_command._translate_powershell_operators 完成）
#         _replace_python3_safe 新增引号感知替换, 避免python3误改字符串字面量
#         close()/_close() 加锁约束注释, 明确调用方锁约定
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; __init__+get_instance+_start按shell_type(ps7/ps5)选pwsh.exe/powershell.exe
# 2026-07-28 - 小欧 - 删死字段 _is_pwsh7: _start中赋值后全局无读取(旧读者 _preprocess_command 的 && 分支已删)
# 2026-07-30 - 小沈 - 去单例+ShellPoolManager分池重构: 删get_instance/_instances/_class_lock/cleanup_all_persistent_shells/_IDLE_TIMEOUT; close()改self._lock.acquire(timeout=5); 尾部新增ShellPoolManager类+shell_pool单例+atexit; _close()docstring更新timeout场景
# 2026-07-30 - 小沈 - BugFix轮: acquire() 两段式(持锁检查→解锁启动→持锁入池)解决子进程启动阻塞全池; 复用空闲实例时加alive检查; release() close()移出锁; cleanup_by_task 增加临时实例清理(self._temp_instances); 删__init__中self._key死代码
# 2026-07-30 - 小沈 - 清理: 更新PersistentShell类docstring(删"实例池+空闲清理"); 删self._last_used死字段(只写不读)
# 2026-07-30 - 小沈 - 空闲超时兜底: ShellPoolManager 新增 idle_timeout=300s + _last_used 追踪; acquire()复用前检查超时则close不放回; release()/cleanup*同步清理_last_used
# 2026-07-30 - 小沈 - except:pass补日志: _kill_tree/_close/cleanup_by_task/cleanup_all四处catch改为logger.debug记录
# 2026-07-31 - 小欧 - Shell池进程保护: ShellPoolManager新增get_all_pids()返回所有活跃PID集合,供安全检查拦截Stop-Process/taskkill/kill保护自身进程; get_all_pids()加debug日志
# 2026-08-06 - 小欧 - 按设计文档12章实施H1-H10: ①新增探活常量+_probe()响应性探活; ②_start() stderr落日志+就绪握手; ③_close()显式关stderr句柄+残留读取+清理临时文件; ④ShellPoolManager新增_sem并发限流+_slot_held槽位记录; ⑤acquire()重构(Phase0限流/Phase1持锁找空闲/Phase2解锁探活/Phase3有界重试); ⑥release()/cleanup_by_task归还前查_slot_held防计数虚高; ⑦删除死代码shell/shell_engine.py
# 2026-08-06 - 小欧 - v2.7 BugFix: acquire()复用路径漏注册_inst_map(release()会pop, 复用后release拿key=None提前return → 信号量槽位泄漏, 并发下所有acquire等满ACQUIRE_WAIT_TIMEOUT); 由test_shell_pool_manager并发用例暴露(100.89s→41.21s); 复用路径补 self._inst_map[id(inst)] = key
"""
PersistentShell — 持久 PowerShell 进程引擎(ps7/ps5) — 小欧 2026-07-05

【编码链路】PS分支编码修复 (2026-07-07 小欧):
  ┌─ [入] stdin.write(cmd.encode(locale.getpreferredencoding()))
  │    PS5.1 `-Command -` stdin 用系统OEM编码(中文Windows=cp936/GBK)读取
  │    UTF-8写入时中文字节被GBK错误解码 → 必须用locale编码写入
  │    非locale可编码字符用errors='replace'回退
  │
  ├─ [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
  │    PYTHONIOENCODING: print()输出中文不抛UnicodeEncodeError
  │    PYTHONUTF8=1: open()默认用UTF-8,避免gbk误读UTF-8代码文件
  │
  ├─ [出] > 替换为 Out-File -Encoding utf8
  │    PS5.1默认>写UTF-16LE导致中文乱码 → 统一UTF-8
  │
  └─ [读] safe_read_file + .lstrip('\ufeff')
       PS5.1 Out-File写BOM头 → 去掉ZWNBSP
       (out/err/code/cwd 全部处理)

  全景图见 execute_shell_command.py 头部注释

【架构层级】引擎层 (raw dict only，不碰 build3/llm_data)
   铁规1: 本文件只返回 raw dict，严禁调用 build_success/build_error/build_warning
   铁规2: 计时(duration_ms) 不在本文件，在 shell() 主函数

【设计原则】
  SRP: 只做进程管理 + 命令执行，tempfile/安全读取提取为独立函数
  DRY: _ERROR_NO_SHELL/_ERROR_TIMEOUT 错误常量统一
  KISS: exec() -> _ensure_alive() -> _exec() 直线调用
  YAGNI: 无 daemon 线程空闲检查，exec 时懒检测
"""

import atexit
import contextlib
import locale
import os
import re as re_mod
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.logger import logger
from app.tools.tool_constants import DEFAULT_TIMEOUT_SEC, SHELL_POOL_IDLE_TIMEOUT, SUBPROCESS_TIMEOUT_SHORT


# ═══════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════

_ERROR_NO_SHELL = {"stdout": "", "stderr": "PowerShell不可用", "exit_code": -1}
_ERROR_TIMEOUT  = {"stdout": "", "stderr": "timeout", "exit_code": -1, "timed_out": True}
_EXIT_PROCESS_DIED = -2          # 进程死亡 sentinel，外部重试用
_PROBE_TIMEOUT = 3               # 响应性探活超时(秒)：半死进程3秒内无回执即判死 — 小欧 2026-08-06
_PROBE_CMD = "Write-Output __OMNI_PROBE__"   # 探活命令：轻量、无副作用、输出唯一标记 — 小欧 2026-08-06
ACQUIRE_WAIT_TIMEOUT = 10        # acquire 并发限流等待超时(秒)：超时兜底创建，避免限流变成新卡死 — 小欧 2026-08-06

# ═══════════════════════════════════════════════════════
#  _TempFiles — 临时文件 contextmanager
# ═══════════════════════════════════════════════════════

@contextlib.contextmanager
def _TempFiles():
    """安全创建 5 个临时文件并自动清理 — out/err/code/cwd/ps1"""
    paths = {}
    try:
        # ps1: 2026-07-18 小沈 新增, 存多行命令脚本(避免直接经stdin喂入导致PS卡死)
        for name in ("out", "err", "code", "cwd", "ps1"):
            f = tempfile.NamedTemporaryFile(delete=False, suffix=f".{name}",
                                             mode="w", encoding="utf-8")
            f.close()
            paths[name] = f.name
        yield type("Paths", (), paths)()
    finally:
        for p in paths.values():
            try:
                os.unlink(p)
            except OSError:
                pass


def safe_read_file(path: str) -> str:
    """读取文件内容(utf-8), OSError返回空串 — 小欧 2026-07-23"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# ═══════════════════════════════════════════════════════
#  _poll_for_file — 指数退避轮询
# ═══════════════════════════════════════════════════════

def _poll_for_file(path: str, timeout: int) -> bool:
    """轮询直到文件非空或超时 — 指数退避 100ms→1s"""
    deadline = time.time() + timeout
    delay = 0.1
    while time.time() < deadline:
        try:
            if os.path.getsize(path) > 0:
                return True
        except OSError:
            pass
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 1.0)
    return False


# ═══════════════════════════════════════════════════════
#  _replace_python3_safe — 引号感知 python3→python 替换
# ═══════════════════════════════════════════════════════

def _replace_python3_safe(command: str) -> tuple[str, int]:
    """引号感知的 python3→python 替换(仅替换引号外的python3) — 小欧 2026-07-28

     返回 (替换后命令, 替换次数) 方便调用方日志记录。"""
    result = []
    in_single = False
    in_double = False
    count = 0
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
            result.append(c)
            i += 1
        elif c == '"' and not in_single:
            in_double = not in_double
            result.append(c)
            i += 1
        elif not in_single and not in_double:
            # 引号外: 匹配 python3 (word boundary 语义)
            if (i == 0 or command[i - 1] in ' \t;|&') and \
               i + 7 <= n and command[i:i + 7] == 'python3' and \
               (i + 7 >= n or command[i + 7] in ' \t;|&'):
                result.append('python')
                i += 7
                count += 1
                continue
            result.append(c)
            i += 1
        else:
            result.append(c)
            i += 1
    return ''.join(result), count


# ═══════════════════════════════════════════════════════
#  PersistentShell — 核心类
# ═══════════════════════════════════════════════════════

class PersistentShell:
    """持久 PowerShell 进程(ps7/ps5) — 自动重启(exec内2次retry+_ensure_alive)

    用法:
        engine = shell_pool.acquire("task_id", "ps7", workdir="C:/work")
        result = engine.exec("Get-ChildItem", timeout=DEFAULT_TIMEOUT_SEC)
        shell_pool.release(engine)
        # result = {"stdout": ..., "stderr": ..., "exit_code": 0}
    """

    def __init__(self, workdir: str, shell_type: str = "ps7"):
        if shell_type not in ("ps7", "ps5"):
            raise ValueError(f"PersistentShell 仅支持 ps7/ps5, 收到: {shell_type}")
        self._proc: Optional[subprocess.Popen] = None
        self._alive = False
        self._lock = threading.Lock()
        self._cwd = workdir or os.getcwd()
        self._shell_type = shell_type
        self._stderr_path: Optional[str] = None   # stderr 日志文件路径(半死可观测) — 小欧 2026-08-06

    # ── 公共方法 ────────────────────────────────

    def exec(self, command: str, timeout: int = 60, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        with self._lock:
            for attempt in range(2):
                if not self._ensure_alive(env):
                    if attempt == 0:
                        self._close()
                        continue
                    return dict(_ERROR_NO_SHELL)
                result = self._exec(command, timeout)
                if result.get("exit_code") != _EXIT_PROCESS_DIED:
                    return result
                self._close()
            return dict(_ERROR_NO_SHELL)

    def close(self):
        """关闭实例并终止进程。先尝试获取 self._lock（最多等5秒），超时也 force-kill。"""
        locked = self._lock.acquire(timeout=5)
        try:
            self._close()
        finally:
            if locked:
                self._lock.release()

    @property
    def current_dir(self) -> str:
        return self._cwd

    # ── 进程生命周期 ────────────────────────────

    def _ensure_alive(self, env: Optional[Dict[str, str]] = None) -> bool:
        if self._alive and self._proc and self._proc.poll() is None:
            return True
        return self._start(env)

    def _probe(self, env: Optional[Dict[str, str]] = None) -> bool:
        """响应性探活(纯探测, 不重建)：进程死或半死返回 False, 由调用方决定重建。
        复用 _exec 机制(DRY)：半死时 _exec 内部 _poll_for_file 超时 → 自动 _kill_tree+_close。
        返回 True=健康可复用; False=进程不可用(可能已被 _exec 销毁)。 — 小欧 2026-08-06"""
        if self._proc is None or self._proc.poll() is not None:
            return False                      # 进程已死/未启动 → 不可复用
        result = self._exec(_PROBE_CMD, timeout=_PROBE_TIMEOUT)   # 复用现有执行机制
        if result.get("timed_out"):
            logger.warning(f"[PersistentShell] 探活失败(半死)→已销毁 (pid={self._proc.pid})")
            self._close()                     # 半死销毁(重建由调用方负责)
            return False
        return "__OMNI_PROBE__" in result.get("stdout", "")

    def _start(self, env: Optional[Dict[str, str]] = None) -> bool:
        self._close()
        if self._shell_type == "ps7":
            pwsh = shutil.which("pwsh.exe")
        else:  # "ps5"
            pwsh = shutil.which("powershell.exe")
        if not pwsh:
            logger.error(f"[PersistentShell] {self._shell_type}(pwsh.exe/powershell.exe) 未找到")
            return False
        try:
            # 设PYTHONIOENCODING保证子Python进程输出中文时不抛UnicodeEncodeError — 小欧 2026-07-07
            # PYTHONUTF8=1让open()默认用UTF-8而非gbk,避免读UTF-8代码文件乱码 — 小欧 2026-07-07
            base_env = env if env is not None else os.environ
            child_env = {**base_env, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            # ① stderr: DEVNULL → 日志文件(可观测半死原因) — 治#2 小欧 2026-08-06
            fd, self._stderr_path = tempfile.mkstemp(suffix=".err", prefix="ps_", text=True)
            os.close(fd)
            self._proc = subprocess.Popen(
                [pwsh, "-NoProfile", "-Command", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=open(self._stderr_path, "w", encoding="utf-8", errors="replace"),
                cwd=self._cwd, env=child_env,
            )
            for _ in range(40):
                if self._proc.poll() is None:
                    break
                time.sleep(0.025)
            else:
                self._alive = False
                logger.error("[PersistentShell] 进程启动后立即退出")
                return False
            self._alive = True
            # ② 就绪握手：启动后立即纯探测一次，未就绪则销毁(调用方重建) — 治#3 小欧 2026-08-06
            if not self._probe(env):
                logger.error("[PersistentShell] 就绪握手失败，进程未就绪")
                self._close()
                return False
            logger.info(f"[PersistentShell] 进程就绪 (pid={self._proc.pid}, stderr={self._stderr_path}, cwd={self._cwd}, shell_type={self._shell_type})")
            return True
        except Exception as e:
            logger.error(f"[PersistentShell] 启动失败: {e}")
            self._alive = False
            return False

    # ── 命令预处理 ──────────────────────────────

    def _preprocess_command(self, command: str) -> str:
        """预处理命令, 修复常见跨平台/跨PS版本不兼容 — 小欧 2026-07-28
        注: PS5 的 &&/|| 翻译已在 execute_shell_command._translate_powershell_operators 完成, 此处不再重复 — 小欧 2026-07-28"""
        if sys.platform == "win32":
            new_cmd, count = _replace_python3_safe(command)
            if count:
                logger.debug(f"[PersistentShell] python3 → python (x{count})")
            command = new_cmd
        return command

    # ── 命令执行 ────────────────────────────────

    def _exec(self, command: str, timeout: int) -> Dict[str, Any]:
        command = self._preprocess_command(command)
        with _TempFiles() as paths:
            # 用Out-File -Encoding utf8取代>避免PS5.1写UTF-16LE导致中文乱码 — 小欧 2026-07-07
            # 设置$OutputEncoding为UTF8避免PS5.1用GBK解读子进程UTF-8输出导致乱码 — 小欧 2026-07-07
            # $OutputEncoding+Out-File -Width 4096解决PS5.1 Format-Table因控制台宽度不足(默认80列)输出空白 — 小欧 2026-07-08
            ps_cmd = (
                f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; $global:rc=0; & {{ {command}; if (-not $?) {{ $global:rc = if ($LASTEXITCODE) {{ $LASTEXITCODE }} else {{ 1 }} }} }} 2>&1 | '
                f'ForEach-Object {{ if ($_ -is [System.Management.Automation.ErrorRecord]) {{ $_ | Out-File -FilePath "{paths.err}" -Encoding utf8 -Width 4096 -Append }} else {{ $_ | Out-File -FilePath "{paths.out}" -Encoding utf8 -Width 4096 -Append }} }}; '
                f'$global:rc | Out-File -FilePath "{paths.code}" -Encoding utf8; '
                f'(Get-Location).Path | Out-File -FilePath "{paths.cwd}" -Encoding utf8'
            )
            try:
                # 修复(小沈 2026-07-18): 多行命令(如 python -c "..." 含换行)直接经 -Command - 从stdin喂入时,
                # PowerShell解析器会卡死等待输入, 导致命令跑满timeout(见 logs 2026-07-18 step=15 跑满600s)。
                # 改为: 将ps_cmd(含多行内容)以UTF-8-BOM写入.ps1文件, 再向持久pwsh喂一句【单行】dot-source
                # (& { . "path.ps1" }), 多行内容留在文件内不再经stdin流 → 死锁消除。单行命令亦正常。
                with open(paths.ps1, "w", encoding="utf-8-sig") as _ps1:
                    _ps1.write(ps_cmd)
                feed = f'& {{ . "{paths.ps1}" }}\n'
                self._proc.stdin.write(feed.encode(locale.getpreferredencoding(), errors="replace"))
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError):
                return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}

            if not _poll_for_file(paths.code, timeout):
                self._kill_tree()
                self._close()
                return dict(_ERROR_TIMEOUT)

            # .lstrip('\ufeff') 去掉PS5.1 Out-File -Encoding utf8写的BOM — 小欧 2026-07-07
            stdout = safe_read_file(paths.out).lstrip('\ufeff')
            stderr = safe_read_file(paths.err).lstrip('\ufeff')
            code_raw = safe_read_file(paths.code).strip().lstrip('\ufeff')
            cwd_raw = safe_read_file(paths.cwd).strip().lstrip('\ufeff')
            if cwd_raw:
                self._cwd = cwd_raw
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": int(code_raw) if code_raw else 0,
            }

    # ── 清理 ────────────────────────────────────

    def _kill_tree(self):
        if self._proc and self._proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(self._proc.pid)],
                    capture_output=True, timeout=SUBPROCESS_TIMEOUT_SHORT,
                )
            except Exception as e:
                logger.debug(f"taskkill失败(pid={self._proc.pid}): {e}")

    def _close(self):
        """内部关闭, 不持锁。调用方尽量持有 self._lock（close()超时5s未获取到锁也会force-kill）。"""
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
            except Exception as e:
                logger.debug(f"关闭进程失败(pid={self._proc.pid}): {e}")
            # v2.7 修复(问题3): 显式关闭 stderr 句柄(在置 None 前), 防半死场景 wait 超时后句柄残留→unlink 失败 — 小欧 2026-08-06
            try:
                if self._proc.stderr is not None:
                    self._proc.stderr.close()
            except Exception:
                pass
            self._proc = None
            self._alive = False
        # 半死可观测：close 前读取 stderr 残留并记录，随后清理临时文件 — 小欧 2026-08-06
        if self._stderr_path:
            tail = safe_read_file(self._stderr_path).strip()
            if tail:
                logger.warning(f"[PersistentShell] 关闭时 stderr 残留: {tail[:200]}")
            try:
                os.unlink(self._stderr_path)
            except OSError:
                pass
            self._stderr_path = None


# ═══════════════════════════════════════════════════════
#  ShellPoolManager — 按 (task_id, shell_type) 分池
# ═══════════════════════════════════════════════════════

class ShellPoolManager:
    """Shell实例池管理器 — 按 (task_id, shell_type) 分池，任务隔离 + 同类型并行"""

    def __init__(self, max_per_type: int = 3, idle_timeout: Optional[int] = SHELL_POOL_IDLE_TIMEOUT):
        self._pool: Dict[tuple, List[PersistentShell]] = defaultdict(list)
        self._busy: Dict[tuple, set] = defaultdict(set)
        self._inst_map: Dict[int, tuple] = {}
        self._temp_instances: Dict[str, List[PersistentShell]] = defaultdict(list)
        self._lock = threading.Lock()
        self._max_per_type = max_per_type
        self._sem: Dict[tuple, threading.BoundedSemaphore] = defaultdict(lambda: threading.BoundedSemaphore(self._max_per_type))
        self._slot_held: Dict[int, bool] = {}   # id(inst)→是否持有信号量槽位(超时放行的实例不持有, 防计数虚高) — 小欧 2026-08-06
        # 空闲超时兜底: 实例放回池后超过 idle_timeout 秒无人 acquire 则 close（防孤魂野鬼）
        self._idle_timeout = idle_timeout
        self._last_used: Dict[int, float] = {}  # id(inst) → release 时间戳

    def _pool_key(self, task_id: str, shell_type: str) -> tuple:
        return (task_id, shell_type)

    def _make_shell(self, shell_type: str, workdir: str = None) -> PersistentShell:
        """创建 PersistentShell 实例（解锁执行，不持池锁）"""
        return PersistentShell(workdir, shell_type)

    def acquire(self, task_id: str, shell_type: str, workdir: str = None) -> PersistentShell:
        """获取一个空闲 PersistentShell 实例（按 task_id + shell_type 分池）
        并发限流+探活移出锁:
          Phase0: 信号量限流(同key并发≤max_per_type, 治#5)
          Phase1(持锁): 仅找空闲实例+空闲超时兜底, 零耗时(治#6)
          Phase2(解锁): 复用→_probe()探活; 新建→_start()启动
          Phase3: 探活/启动失败→剔除销毁→有界重试
        """  # 小欧 2026-08-06
        key = self._pool_key(task_id, shell_type)
        sem = self._sem[key]
        acquired = sem.acquire(timeout=ACQUIRE_WAIT_TIMEOUT)   # Phase0: 超时也继续(兜底创建) — 治#5; v2.7 记录是否实际占用槽位
        max_attempts = self._max_per_type + 2   # 有界重试: 防 pwsh 不可用时无限循环 — 小欧 2026-08-06
        try:
            for _ in range(max_attempts):
                # ── Phase1(持锁): 仅找空闲实例+空闲超时兜底, 零耗时(治#6) ──
                with self._lock:
                    pool = self._pool[key]
                    busy = self._busy[key]
                    inst = None
                    for it in list(pool):
                        if id(it) not in busy:
                            if self._idle_timeout is not None:
                                last = self._last_used.get(id(it), 0)
                                if time.time() - last > self._idle_timeout:
                                    pool.remove(it)
                                    self._inst_map.pop(id(it), None)
                                    self._last_used.pop(id(it), None)
                                    it.close()
                                    continue
                            busy.add(id(it))
                            inst = it
                            break
                    if inst is None:
                        inst = self._make_shell(shell_type, workdir)
                        if len(pool) < self._max_per_type:
                            pool.append(inst)
                            busy.add(id(inst))
                            self._inst_map[id(inst)] = key
                            self._last_used[id(inst)] = time.time()
                            fresh = True
                        else:
                            # 已达上限 → 临时实例（不入池, 用完close）
                            self._inst_map[id(inst)] = key
                            self._temp_instances[task_id or ""].append(inst)
                            fresh = True
                    else:
                        # v2.7 BugFix(小欧 2026-08-06): 复用路径必须重新注册 _inst_map。
                        # release() 会 pop(id)，若复用后不重注册，下一次 release 拿到 key=None
                        # 提前返回 → 信号量永不归还 → 槽位泄漏(并发下所有 acquire 等满10s)。
                        self._inst_map[id(inst)] = key
                        fresh = False
                # ── Phase2(解锁): 新建→_start; 复用→_probe ──
                ok = inst._start() if fresh else inst._probe()
                if ok:
                    self._slot_held[id(inst)] = acquired   # 记录槽位持有状态, 供 release/cleanup 判断(v2.7) — 小欧 2026-08-06
                    return inst
                # ── Phase3: 失败→销毁剔除→有界重试 ──
                with self._lock:
                    pool = self._pool[key]
                    busy = self._busy[key]
                    if inst in pool:
                        pool.remove(inst)
                    busy.discard(id(inst))
                    self._inst_map.pop(id(inst), None)
                    self._last_used.pop(id(inst), None)
                inst.close()
            raise RuntimeError(
                f"[ShellPool] 连续 {max_attempts} 次获取 Shell 失败 (shell_type={shell_type}, task_id={task_id})"
            )
        except Exception:
            if acquired:   # v2.7: 仅实际占用槽位时归还, 防超时未占用却虚高计数 — 小欧 2026-08-06
                with contextlib.suppress(Exception):   # 异常路径归还槽位, 防泄漏
                    sem.release()
            raise

    def release(self, inst: PersistentShell):
        """释放实例回池"""
        key = self._inst_map.pop(id(inst), None)
        if key is None:
            return
        sem = self._sem.get(key)
        held = self._slot_held.pop(id(inst), False)   # v2.7: 是否实际持有槽位(正常必有记录; 默认False防超归崩溃) — 小欧 2026-08-06
        should_close = False
        with self._lock:
            busy_set = self._busy.get(key)
            if busy_set is None:
                should_close = True
            else:
                busy_set.discard(id(inst))
                pool = self._pool.get(key, [])
                if inst not in pool:
                    # 从 temp_instances 移除（可能存在于多个 task_id 列表，逐个尝试）
                    for tid_list in self._temp_instances.values():
                        try:
                            tid_list.remove(inst)
                        except ValueError:
                            continue
                    should_close = True
                else:
                    # 池实例放回: 记录时间戳供空闲超时兜底
                    self._last_used[id(inst)] = time.time()
        # Bug#3 修复: close() 在锁外执行，不阻塞全池操作
        if should_close:
            inst.close()
        if held and sem is not None:
            sem.release()   # 并发槽位归还（治#5）; v2.7 held 防未占用虚高 — 小欧 2026-08-06

    def cleanup_by_task(self, task_id: str):
        """关闭某个任务的所有实例 — 任务结束时调用"""
        count = 0
        close_list = []
        with self._lock:
            # ── 池中实例 ──
            keys_to_remove = [k for k in self._pool if k[0] == task_id]
            for key in keys_to_remove:
                for inst in self._pool[key]:
                    self._slot_held.pop(id(inst), None)   # v2.7 清理槽位记录(池实例不归还, 仅清残留防 id 重用误判) — 小欧 2026-08-06
                    self._inst_map.pop(id(inst), None)
                    self._last_used.pop(id(inst), None)
                    close_list.append(inst)
                del self._pool[key]
                self._busy.pop(key, None)
            # ── 临时实例（Bug#4 修复: 之前漏清理）──
            task_key = task_id or ""
            temp_list = self._temp_instances.pop(task_key, [])
            for inst in temp_list:
                sem = self._sem.get(self._inst_map.get(id(inst)))
                held = self._slot_held.pop(id(inst), False)   # v2.7: 仅实际持槽位才归还 — 小欧 2026-08-06
                if held and sem:
                    sem.release()   # 仅归还未release且实际持槽位的临时实例, 防槽位泄漏 — 小欧 2026-08-06
                self._inst_map.pop(id(inst), None)
                self._last_used.pop(id(inst), None)
                close_list.append(inst)
                count += 1
        # 锁外 close，不阻塞全池
        for inst in close_list:
            try:
                inst.close()
                count += 1
            except Exception as e:
                logger.debug(f"关闭Shell实例失败: {e}")
        return count

    def cleanup_all(self) -> int:
        """关闭所有池中实例 — 给 atexit 安全网用"""
        close_list = []
        with self._lock:
            for key, lst in list(self._pool.items()):
                for inst in lst:
                    self._inst_map.pop(id(inst), None)
                    close_list.append(inst)
            # 剩余临时实例
            for tid_list in self._temp_instances.values():
                for inst in tid_list:
                    self._inst_map.pop(id(inst), None)
                    close_list.append(inst)
            self._pool.clear()
            self._busy.clear()
            self._inst_map.clear()
            self._slot_held.clear()   # v2.7 清理槽位记录(atexit 兜底) — 小欧 2026-08-06
            self._temp_instances.clear()
            self._last_used.clear()
        for inst in close_list:
            try:
                inst.close()
            except Exception as e:
                logger.debug(f"atexit清理Shell实例失败: {e}")
        return len(close_list)

    def get_all_pids(self) -> set:
        """返回所有活跃shell实例的PID集合(供安全检查保护自身进程) — 小欧 2026-07-31"""
        pids = set()
        with self._lock:
            for key, pool in self._pool.items():
                for inst in pool:
                    if inst._proc and inst._proc.poll() is None:
                        pids.add(inst._proc.pid)
            for tid_list in self._temp_instances.values():
                for inst in tid_list:
                    if inst._proc and inst._proc.poll() is None:
                        pids.add(inst._proc.pid)
        if pids:
            logger.debug(f"[ShellPool] get_all_pids: {len(pids)} 个活跃PID: {pids}")
        return pids


shell_pool = ShellPoolManager(max_per_type=3)


atexit.register(shell_pool.cleanup_all)
