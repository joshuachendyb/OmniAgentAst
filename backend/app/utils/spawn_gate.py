# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 全局进程/线程创建闸门(有界等待+快速失败+计数), 消除 Windows loader lock 互锁
"""spawn_gate — 进程创建 × 线程创建 互斥闸门 — 小欧 2026-11-04

【问题】Windows 上 `CreateProcessW` 调用期持 loader lock 且不释放 GIL; `Thread.start()`
内部 `self._started.wait()` 无超时, 新线程 bootstrap 同样要 loader lock → 二者并发即永久
互锁, 线程报废, 槽位烧光, 全站僵死。
实证: backend/logs/pyspy/hang_20261104_0115_final_nonblocking.txt
  MainThread   : start(threading.py) → wait(threading.py)   ← Thread.start 永不返回
  loop-watchdog: __init__(subprocess.py)                    ← CreateProcess 卡住

【做法】`subprocess.Popen.__init__` 与 `threading.Thread.start` 共用一把 RLock(同线程可
重入)。覆盖面无遗漏: 全库进程创建入口只有 Popen(app/ 无 os.system/os.spawn/os.popen/ctypes 直调)。

【关键: 有界 + 快速失败】绝不无限等待 —— 无限等待就是僵死, 只是换了个位置。
  等锁超 `ACQUIRE_TIMEOUT` ⇒ 抛 `SpawnGateBusy`: 工具返回错误, 进程照样活着, 日志/计数器留痕。
  这是"出事也不僵死"的唯一实现方式: 宁可让一条命令失败, 也不让线程永久卡住。

【为什么在启动期安装】线程池已在导入期建满, 闸门于 startup 安装后运行期不应再有建线程动作; 闸门是兜底网,
让将来任何漏网的 Thread.start 变成"有界失败 + 可见", 而不是"偶发僵死 + 无现场"。
"""
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from app.logger import logger

__all__ = ["SpawnGateBusy", "install_spawn_gate", "mark_runtime_started", "snapshot"]

ACQUIRE_TIMEOUT = 20.0      # 等锁上限(秒): CreateProcessW 被杀软扫描时可到秒级, 20s 仍属异常
SLOW_WARN = 1.0             # 建进程/等锁超过该值(秒)即告警: 说明 loader lock 窗口被拉长

_GATE = threading.RLock()
_install_lock = threading.Lock()
_installed = False
_runtime_started = False

_stats: Dict[str, Any] = {
    "popen_calls": 0,           # 累计 CreateProcess 次数
    "thread_start_calls": 0,    # 累计 Thread.start 次数
    "runtime_thread_starts": 0, # 启动完成之后的 Thread.start 次数 —— 必须为 0, 否则暴露漏网点
    "gate_timeouts": 0,         # 等锁超上限次数(每次都是一次"本会僵死"的现场)
    "wait_max_ms": 0.0,         # 等锁最长耗时
    "popen_max_ms": 0.0,        # CreateProcess 持锁最长耗时(≈ loader lock 窗口)
}


class SpawnGateBusy(RuntimeError):
    """闸门被占用超上限: 拒绝在 loader lock 上无限等待 — 2026-11-04 小欧"""


def _record(key: str, value: float) -> None:
    if value > _stats[key]:
        _stats[key] = value


def _acquire(what: str, ident: str) -> float:
    """有界获取闸门; 超限抛 SpawnGateBusy(绝不放行, 也绝不无限等)。返回等待秒数。"""
    t0 = time.monotonic()
    if not _GATE.acquire(timeout=ACQUIRE_TIMEOUT):
        _stats["gate_timeouts"] += 1
        logger.error(
            f"[进程闸门] {what} 等锁超过 {ACQUIRE_TIMEOUT:.0f}s → 快速失败(拒绝无限等待 {ident})")
        raise SpawnGateBusy(f"{what} 等锁超 {ACQUIRE_TIMEOUT:.0f}s: {ident}")
    waited = time.monotonic() - t0
    _record("wait_max_ms", waited * 1000)
    if waited >= SLOW_WARN:
        logger.warning(f"[进程闸门] {what} 等锁 {waited:.1f}s 才拿到 {ident}")
    return waited


def install_spawn_gate() -> None:
    """安装闸门(幂等) — 2026-11-04 小欧"""
    global _installed
    with _install_lock:
        if _installed:
            return
        _installed = True

    orig_popen_init = subprocess.Popen.__init__
    orig_thread_start = threading.Thread.start

    def popen_init(self, *args, **kwargs):
        argv: Optional[Any] = args[0] if args else kwargs.get("args")
        _acquire("CreateProcess", repr(argv))
        _stats["popen_calls"] += 1
        t0 = time.monotonic()
        try:
            return orig_popen_init(self, *args, **kwargs)
        finally:
            held = time.monotonic() - t0
            _record("popen_max_ms", held * 1000)
            _GATE.release()
            if held >= SLOW_WARN:
                logger.warning(f"[进程闸门] CreateProcess 持锁 {held:.1f}s(杀软扫描/loader lock 长窗口) {argv!r}")

    def thread_start(self):
        if _runtime_started:
            _stats["runtime_thread_starts"] += 1
        _stats["thread_start_calls"] += 1
        _acquire("Thread.start", self.name)
        try:
            return orig_thread_start(self)
        finally:
            _GATE.release()

    subprocess.Popen.__init__ = popen_init
    threading.Thread.start = thread_start
    logger.info("[进程闸门] 已安装: CreateProcess × Thread.start 互斥(有界等待, 超限快速失败)")


def mark_runtime_started() -> None:
    """标记"启动期结束": 此后每次 Thread.start 都计入 runtime_thread_starts — 2026-11-04 小欧"""
    global _runtime_started
    _runtime_started = True


def snapshot() -> Dict[str, Any]:
    """闸门运行指标(供 /health 暴露) — 2026-11-04 小欧"""
    return {
        **_stats,
        "wait_max_ms": round(_stats["wait_max_ms"], 1),
        "popen_max_ms": round(_stats["popen_max_ms"], 1),
        "threads": threading.active_count(),
    }
