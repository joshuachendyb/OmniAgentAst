# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: 临时输出文件读取保护线改引用 tool_constants.SHELL_OUTPUT_FILE_MAX_BYTES(原 _MAX_OUTPUT_SZ=10MB), 功能零退化
"""
PersistentShell — 持久 PowerShell 进程引擎 — 小欧 2026-07-05

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
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.tool_constants import SHELL_OUTPUT_FILE_MAX_BYTES


# ═══════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════

_ERROR_NO_SHELL = {"stdout": "", "stderr": "PowerShell不可用", "exit_code": -1}
_ERROR_TIMEOUT  = {"stdout": "", "stderr": "timeout", "exit_code": -1, "timed_out": True}
_EXIT_PROCESS_DIED = -2          # 进程死亡 sentinel，外部重试用
_IDLE_TIMEOUT   = 1800           # 30 分钟空闲自动清理
SHELL_OUTPUT_FILE_MAX_BYTES  = 10 * 1024 * 1024  # 10MB 保护线


# ═══════════════════════════════════════════════════════
#  _TempFiles — 临时文件 contextmanager
# ═══════════════════════════════════════════════════════

@contextlib.contextmanager
def _TempFiles():
    """安全创建 4 个临时文件并自动清理 — out/err/code/cwd"""
    paths = {}
    try:
        for name in ("out", "err", "code", "cwd"):
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


# ═══════════════════════════════════════════════════════
#  safe_read_file — 安全读取 + 大文件保护
# ═══════════════════════════════════════════════════════

def safe_read_file(path: str) -> str:
    """读取文件，超 10MB 只读头尾各 5MB — 防 OOM"""
    try:
        sz = os.path.getsize(path)
        if sz == 0:
            return ""
        if sz <= SHELL_OUTPUT_FILE_MAX_BYTES:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        half = SHELL_OUTPUT_FILE_MAX_BYTES // 2
        with open(path, "rb") as f:
            head = f.read(half)
            f.seek(-half, os.SEEK_END)
            tail = f.read(half)
        return (head.decode("utf-8", errors="replace") +
                "\n...[巨大输出已截断]...\n" +
                tail.decode("utf-8", errors="replace"))
    except OSError:
        return ""


# ═══════════════════════════════════════════════════════
#  _poll_for_file — 指数退避轮询
# ═══════════════════════════════════════════════════════

def _poll_for_file(path: str, timeout: int) -> bool:
    """轮询直到文件非空或超时 — 指数退避 5ms→100ms"""
    deadline = time.time() + timeout
    delay = 0.005
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
        delay = min(delay * 1.5, 0.1)
    return False


# ═══════════════════════════════════════════════════════
#  PersistentShell — 核心类
# ═══════════════════════════════════════════════════════

class PersistentShell:
    """持久 PowerShell 进程 — 实例池 + 自动重启 + 空闲清理

    用法:
        engine = PersistentShell.get_instance("C:/work")
        result = engine.exec("Get-ChildItem", timeout=30)
        # result = {"stdout": ..., "stderr": ..., "exit_code": 0}
    """

    _instances: Dict[str, 'PersistentShell'] = {}
    _class_lock = threading.Lock()

    def __init__(self, workdir: str):
        self._key = workdir or os.getcwd()
        self._proc: Optional[subprocess.Popen] = None
        self._alive = False
        self._last_used = time.time()
        self._lock = threading.Lock()
        self._cwd = self._key

    # ── 实例池 ──────────────────────────────────

    @classmethod
    def get_instance(cls, workdir: str = None) -> 'PersistentShell':
        with cls._class_lock:
            key = workdir or os.getcwd()
            inst = cls._instances.get(key)
            if inst is None:
                now = time.time()
                expired = [k for k, v in cls._instances.items()
                           if now - v._last_used > _IDLE_TIMEOUT]
                for ek in expired:
                    try:
                        cls._instances[ek].close()
                    except Exception:
                        pass
                inst = cls(key)
                cls._instances[key] = inst
            inst._last_used = time.time()
            return inst

    # ── 公共方法 ────────────────────────────────

    def exec(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        self._last_used = time.time()
        with self._lock:
            for attempt in range(2):
                if not self._ensure_alive():
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
        with PersistentShell._class_lock:
            PersistentShell._instances.pop(self._key, None)
            self._close()

    @property
    def current_dir(self) -> str:
        return self._cwd

    # ── 进程生命周期 ────────────────────────────

    def _ensure_alive(self) -> bool:
        if self._alive and self._proc and self._proc.poll() is None:
            return True
        return self._start()

    def _start(self) -> bool:
        self._close()
        pwsh = shutil.which("pwsh.exe") or shutil.which("powershell.exe")
        if not pwsh:
            logger.error("[PersistentShell] PowerShell 未找到")
            return False
        try:
            # 设PYTHONIOENCODING保证子Python进程输出中文时不抛UnicodeEncodeError — 小欧 2026-07-07
            # PYTHONUTF8=1让open()默认用UTF-8而非gbk,避免读UTF-8代码文件乱码 — 小欧 2026-07-07
            child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            self._proc = subprocess.Popen(
                [pwsh, "-NoProfile", "-Command", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, cwd=self._cwd, env=child_env,
            )
            for _ in range(40):
                if self._proc.poll() is None:
                    self._alive = True
                    logger.info(f"[PersistentShell] 进程已启动 (pid={self._proc.pid}, cwd={self._cwd})")
                    return True
                time.sleep(0.025)
            self._alive = False
            logger.error("[PersistentShell] 进程启动后立即退出")
            return False
        except Exception as e:
            logger.error(f"[PersistentShell] 启动失败: {e}")
            self._alive = False
            return False

    # ── 命令执行 ────────────────────────────────

    def _exec(self, command: str, timeout: int) -> Dict[str, Any]:
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
                self._proc.stdin.write((ps_cmd + "\n").encode(locale.getpreferredencoding(), errors="replace"))
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
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

    def _close(self):
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None
            self._alive = False


# ═══════════════════════════════════════════════════════
#  模块级清理函数
# ═══════════════════════════════════════════════════════

def cleanup_all_persistent_shells() -> int:
    """清理所有持久 Shell 进程 — 给 atexit + main.py shutdown 用"""
    count = 0
    for inst in list(PersistentShell._instances.values()):
        try:
            inst.close()
            count += 1
        except Exception:
            pass
    return count


atexit.register(cleanup_all_persistent_shells)
