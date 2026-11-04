# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 全局进程/线程创建闸门(有界等待+快速失败+计数), 消除 Windows loader lock 互锁
# 2026-11-04 - 小欧 - 重构: RLock → 可强制回收租约 + 看门狗; 持锁方(Thread.start 的 _started.wait 无超时)
#   卡死超 HOLD_LIMIT 即强制回收并落盘全线程栈, 单线程卡死不再拖垮全站; 新增持有者诊断/运行期建线程调用栈留证
# 2026-11-04 - 小欧 - 红队 L05 修复: 全线程栈落盘改投常驻 worker(_DUMP_POOL), 原在看门狗线程内同步
#   faulthandler 写盘, 写盘期间巡检停摆(实测 12 次连发只回收 9 次) — 安全网不得阻塞在取证上
"""spawn_gate — 进程创建 × 线程创建 互斥闸门 — 小欧 2026-11-04

【问题】Windows 上 `CreateProcessW` 与新建线程的原生启动(DLL_THREAD_ATTACH/LdrpInitializeThread)
都要 loader lock; 二者并发会互锁: 新线程进不了字节码 ⇒ `Thread.start` 的 `self._started.wait()`
(无超时)永不返回 ⇒ 建进程/建线程全线饿死 ⇒ 全站僵死。

【历史事故 2026-11-04 11:28~11:31】原实现用全局 RLock 串行化两侧, 但 RLock 只有持有者能释放:
`Thread.start` 卡死时持锁永不释放, 8 条 shell-exec 堵在等锁, AnyIO 线程池被抽干, /health 也超时。
⇒ 结论: 闸门必须是"可回收租约", 不是锁。

【做法】
  1. 租约(Lease)而非 RLock: 持有者带 id 登记(线程名/ident/起始时刻/重入深度), 任何线程都可回收;
     回收后旧持有者迟到的 release 因 id 不匹配而幂等失效, 不会把计数搞坏。
  2. 看门狗每 0.5s 巡检: 持锁超 HOLD_LIMIT 秒 ⇒ 强制回收 + 落盘全线程栈 + ERROR 告警。
     牺牲的只是卡死那条线程, 其余请求立刻放行。
  3. 等锁侧仍有界(ACQUIRE_TIMEOUT), 超限抛 SpawnGateBusy: 工具返回错误, 进程照样活着。
  4. 运行期建线程留证: 记录线程名 + 4 帧调用栈(最多 5 条), 供 /health 暴露与事后定位漏网点。

【判定标准】/health.spawn.runtime_thread_starts 必须为 0; forced_reclaims 必须为 0。
非 0 即说明运行期仍有建线程/长窗口建进程, 需按日志里的调用栈清除线程源。
"""
import faulthandler
import os
import subprocess
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

from app.logger import LOG_DIR, logger
from app.utils.workers import WorkerPool  # 落盘取证常驻线程(零运行期建线程) — 2026-11-04 小欧

__all__ = ["SpawnGateBusy", "install_spawn_gate", "mark_runtime_started", "snapshot"]

ACQUIRE_TIMEOUT = 15.0      # 等锁上限(秒): 正常 CreateProcess 在 20ms 级, 15s 仍属异常
SLOW_WARN = 1.0             # 建进程/等锁超过该值(秒)即告警: 说明 loader lock 窗口被拉长
HOLD_LIMIT = 8.0            # 持锁上限(秒): 超过即由看门狗强制回收(牺牲该线程, 保住全站)
WATCHDOG_INTERVAL = 0.5     # 看门狗巡检间隔(秒)

_DUMP_DIR = LOG_DIR / "pyspy"
# 落盘取证常驻 worker(启动期建线程): 看门狗自己不得阻塞在 faulthandler 写盘上 — 2026-11-04 小欧
_DUMP_POOL = WorkerPool(1, "spawn-gate-dump")


class SpawnGateBusy(RuntimeError):
    """闸门被占用超上限: 拒绝在 loader lock 上无限等待 — 2026-11-04 小欧"""


class _Ticket:
    """租约凭据: 释放幂等(被强制回收后再 release 不会影响新持有者) — 2026-11-04 小欧"""

    __slots__ = ("_lease", "_id", "_released")

    def __init__(self, lease: "Lease", ticket_id: int) -> None:
        self._lease = lease
        self._id = ticket_id
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._lease.release(self._id)


class Lease:
    """可强制回收的互斥租约(替代 RLock) — 2026-11-04 小欧

    与 RLock 的差别只有两点: 持有者信息可读、任何线程可强制回收。
    重入语义保留(同线程再取返回同一 ticket id, 深度 +1)。
    """

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._holder: Optional[Dict[str, Any]] = None
        self._seq = 0

    def acquire(self, what: str, ident: str, timeout: float) -> _Ticket:
        me = threading.get_ident()
        deadline = time.monotonic() + timeout
        with self._cv:
            if self._holder is not None and self._holder["ident"] == me:
                self._holder["depth"] += 1
                return _Ticket(self, self._holder["id"])
            while self._holder is not None:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    raise SpawnGateBusy(
                        f"{what} 等锁超 {timeout:.0f}s: {ident}; 持有者={self._holder}")
                self._cv.wait(remain)
            self._seq += 1
            self._holder = {
                "id": self._seq,
                "what": what,
                "ident": me,
                "name": threading.current_thread().name,
                "since": time.monotonic(),
                "depth": 1,
            }
            return _Ticket(self, self._seq)

    def release(self, ticket_id: int) -> None:
        with self._cv:
            holder = self._holder
            if holder is None or holder["id"] != ticket_id:
                return          # 已被看门狗强制回收: 幂等失效
            holder["depth"] -= 1
            if holder["depth"] <= 0:
                self._holder = None
                self._cv.notify_all()

    def holder_info(self) -> Optional[Dict[str, Any]]:
        with self._cv:
            holder = self._holder
            if holder is None:
                return None
            return {
                "what": holder["what"],
                "name": holder["name"],
                "ident": holder["ident"],
                "held_s": round(time.monotonic() - holder["since"], 2),
                "depth": holder["depth"],
            }

    def reclaim_if_stuck(self, limit: float) -> Optional[Dict[str, Any]]:
        """持有超 limit 秒则强制回收; 返回被回收的持有者信息(供落盘/告警) — 2026-11-04 小欧"""
        with self._cv:
            holder = self._holder
            if holder is None:
                return None
            held = time.monotonic() - holder["since"]
            if held < limit:
                return None
            self._holder = None
            self._cv.notify_all()
            return {
                "what": holder["what"],
                "name": holder["name"],
                "ident": holder["ident"],
                "held_s": round(held, 2),
                "depth": holder["depth"],
            }


_LEASE = Lease()
_install_lock = threading.Lock()
_stop_event = threading.Event()
_installed = False
_runtime_started = False

_stats: Dict[str, Any] = {
    "popen_calls": 0,           # 累计 CreateProcess 次数
    "thread_start_calls": 0,    # 累计 Thread.start 次数
    "runtime_thread_starts": 0, # 启动完成之后的 Thread.start 次数 —— 必须为 0, 否则暴露漏网点
    "gate_timeouts": 0,         # 等锁超上限次数(每次都是一次"本会僵死"的现场)
    "forced_reclaims": 0,       # 看门狗强制回收次数 —— 必须为 0
    "wait_max_ms": 0.0,         # 等锁最长耗时
    "popen_max_ms": 0.0,        # CreateProcess 持锁最长耗时(≈ loader lock 窗口)
    "last_forced": None,        # 最近一次强制回收的持有者信息
}

_runtime_samples: List[Dict[str, str]] = []


def _record(key: str, value: float) -> None:
    if value > _stats[key]:
        _stats[key] = value


def _sample_stack(depth: int = 4) -> str:
    """取当前调用栈最近几帧(文件名:行号:函数名) — 2026-11-04 小欧"""
    frames = traceback.extract_stack(limit=depth + 2)[:-2]
    return " <- ".join(
        f"{os.path.basename(f.filename)}:{f.lineno}:{f.name}" for f in reversed(frames))


def _record_runtime_start(name: str) -> None:
    if len(_runtime_samples) >= 5:
        return
    _runtime_samples.append({"thread": name, "where": _sample_stack()})


def _dump_all_threads(info: Dict[str, Any]) -> None:
    """强制回收现场: 全线程栈落盘(logs/pyspy/), 供事后定位持锁方 — 2026-11-04 小欧"""
    try:
        _DUMP_DIR.mkdir(parents=True, exist_ok=True)
        path = _DUMP_DIR / f"spawn_gate_forced_{os.getpid()}_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(path, "a", encoding="utf-8") as fp:
            fp.write(f"[闸门强制回收] {info}\n")
            faulthandler.dump_traceback(file=fp, all_threads=True)
        logger.error(f"[进程闸门] 全线程栈已落盘: {path}")
    except Exception as e:  # 落盘失败绝不能反过来影响服务
        logger.error(f"[进程闸门] 全线程栈落盘失败: {e}")


def _watchdog_loop() -> None:
    """持锁超限即强制回收: 卡死的线程自己报废, 其余请求立刻放行 — 2026-11-04 小欧

    落盘投常驻 worker, 本线程只做"回收+告警": 否则 faulthandler 写全线程栈(慢盘可达数百 ms)
    期间巡检停摆, 红队实测 12 次连发只回收 9 次 —— 安全网不得阻塞在取证上。
    """
    while not _stop_event.wait(WATCHDOG_INTERVAL):
        info = _LEASE.reclaim_if_stuck(HOLD_LIMIT)
        if info is None:
            continue
        _stats["forced_reclaims"] += 1
        _stats["last_forced"] = info
        logger.error(
            f"[进程闸门] 强制回收: {info['what']} 被线程 {info['name']}(ident={info['ident']}) "
            f"持有 {info['held_s']}s 未释放 → 已回收, 该线程自行报废, 其余请求放行")
        _DUMP_POOL.submit(lambda i=info: _dump_all_threads(i))


def _acquire(what: str, ident: str) -> _Ticket:
    """有界获取租约; 超限抛 SpawnGateBusy(绝不放行, 也绝不无限等)。"""
    t0 = time.monotonic()
    try:
        ticket = _LEASE.acquire(what, ident, ACQUIRE_TIMEOUT)
    except SpawnGateBusy as e:
        _stats["gate_timeouts"] += 1
        logger.error(f"[进程闸门] {what} 等锁超过 {ACQUIRE_TIMEOUT:.0f}s → 快速失败({e})")
        raise
    waited = time.monotonic() - t0
    _record("wait_max_ms", waited * 1000)
    if waited >= SLOW_WARN:
        logger.warning(f"[进程闸门] {what} 等锁 {waited:.1f}s 才拿到 {ident}")
    return ticket


def install_spawn_gate() -> None:
    """安装闸门(幂等) — 2026-11-04 小欧"""
    global _installed
    with _install_lock:
        if _installed:
            return
        _installed = True
        # 先起看门狗再打补丁: 看门狗自己的 Thread.start 不经过闸门
        threading.Thread(target=_watchdog_loop, name="spawn-gate-watchdog", daemon=True).start()

    orig_popen_init = subprocess.Popen.__init__
    orig_thread_start = threading.Thread.start

    def popen_init(self, *args, **kwargs):
        argv: Optional[Any] = args[0] if args else kwargs.get("args")
        ticket = _acquire("CreateProcess", repr(argv))
        _stats["popen_calls"] += 1
        t0 = time.monotonic()
        try:
            return orig_popen_init(self, *args, **kwargs)
        finally:
            held = time.monotonic() - t0
            _record("popen_max_ms", held * 1000)
            ticket.release()
            if held >= SLOW_WARN:
                logger.warning(f"[进程闸门] CreateProcess 持锁 {held:.1f}s(杀软扫描/loader lock 长窗口) {argv!r}")

    def thread_start(self):
        if _runtime_started:
            _stats["runtime_thread_starts"] += 1
            _record_runtime_start(self.name)
        _stats["thread_start_calls"] += 1
        ticket = _acquire("Thread.start", self.name)
        try:
            return orig_thread_start(self)
        finally:
            ticket.release()

    subprocess.Popen.__init__ = popen_init
    threading.Thread.start = thread_start
    logger.info(
        f"[进程闸门] 已安装: CreateProcess × Thread.start 互斥(可回收租约, 持锁超 {HOLD_LIMIT:.0f}s 由看门狗强制回收)")


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
        "holder": _LEASE.holder_info(),
        "runtime_samples": list(_runtime_samples),
        "threads": threading.active_count(),
    }
