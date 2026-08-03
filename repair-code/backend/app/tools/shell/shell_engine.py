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
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.tool_constants import DEFAULT_TIMEOUT_SEC, SUBPROCESS_TIMEOUT_SHORT


# ═══════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════

_ERROR_NO_SHELL = {"stdout": "", "stderr": "PowerShell不可用", "exit_code": -1}
_ERROR_TIMEOUT  = {"stdout": "", "stderr": "timeout", "exit_code": -1, "timed_out": True}
_EXIT_PROCESS_DIED = -2          # 进程死亡 sentinel，外部重试用
_IDLE_TIMEOUT   = 1800           # 30 分钟空闲自动清理

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
    """持久 PowerShell 进程(ps7/ps5) — 实例池 + 自动重启 + 空闲清理

    用法:
        engine = PersistentShell.get_instance("C:/work", "ps7")
        result = engine.exec("Get-ChildItem", timeout=DEFAULT_TIMEOUT_SEC)
        # result = {"stdout": ..., "stderr": ..., "exit_code": 0}
    """

    _instances: Dict[str, 'PersistentShell'] = {}
    _class_lock = threading.RLock()

    def __init__(self, workdir: str, shell_type: str = "ps7"):
        if shell_type not in ("ps7", "ps5"):
            raise ValueError(f"PersistentShell 仅支持 ps7/ps5, 收到: {shell_type}")
        self._key = workdir or os.getcwd()
        self._proc: Optional[subprocess.Popen] = None
        self._alive = False
        self._last_used = time.time()
        self._lock = threading.Lock()
        self._cwd = self._key
        self._shell_type = shell_type

    # ── 实例池 ──────────────────────────────────

    @classmethod
    def get_instance(cls, workdir: str = None, shell_type: str = "ps7") -> 'PersistentShell':
        with cls._class_lock:
            workdir_actual = workdir or os.getcwd()
            key = f"{workdir_actual}|{shell_type}"
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
                inst = cls(workdir_actual, shell_type)
                cls._instances[key] = inst
            inst._last_used = time.time()
            return inst

    # ── 公共方法 ────────────────────────────────

    def exec(self, command: str, timeout: int = 60, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        self._last_used = time.time()
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
        """关闭实例并从池中移除。持有 _class_lock(RLock) 保护 _instances 并发安全。"""
        with PersistentShell._class_lock:
            PersistentShell._instances.pop(self._key, None)
            self._close()

    @property
    def current_dir(self) -> str:
        return self._cwd

    # ── 进程生命周期 ────────────────────────────

    def _ensure_alive(self, env: Optional[Dict[str, str]] = None) -> bool:
        if self._alive and self._proc and self._proc.poll() is None:
            return True
        return self._start(env)

    def _start(self, env: Optional[Dict[str, str]] = None) -> bool:
        self._close()
        if self._shell_type == "ps7":
            pwsh = shutil.which("pwsh.exe")
            self._is_pwsh7 = True
        else:  # "ps5"
            pwsh = shutil.which("powershell.exe")
            self._is_pwsh7 = False
        if not pwsh:
            logger.error(f"[PersistentShell] {self._shell_type}(pwsh.exe/powershell.exe) 未找到")
            return False
        try:
            # 设PYTHONIOENCODING保证子Python进程输出中文时不抛UnicodeEncodeError — 小欧 2026-07-07
            # PYTHONUTF8=1让open()默认用UTF-8而非gbk,避免读UTF-8代码文件乱码 — 小欧 2026-07-07
            base_env = env if env is not None else os.environ
            child_env = {**base_env, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            self._proc = subprocess.Popen(
                [pwsh, "-NoProfile", "-Command", "-"],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, cwd=self._cwd, env=child_env,
            )
            for _ in range(40):
                if self._proc.poll() is None:
                    self._alive = True
                    logger.info(f"[PersistentShell] 进程已启动 (pid={self._proc.pid}, cwd={self._cwd}, shell_type={self._shell_type})")
                    return True
                time.sleep(0.025)
            self._alive = False
            logger.error("[PersistentShell] 进程启动后立即退出")
            return False
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
            except Exception:
                pass

    def _close(self):
        """内部关闭, 不持锁。调用方必须已持有 self._lock 或 _class_lock 保证线程安全。"""
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
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
