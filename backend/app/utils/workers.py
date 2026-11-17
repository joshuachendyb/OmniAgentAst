# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 统一常驻线程池(WorkerPool/ThreadLeasePool), 取代 serial_worker.py 与两处私有池实现
# 2026-11-05 - 小欧 - 修复 submit/lease 丢 ContextVar: 常驻线程不继承调用方上下文, 改为提交时绑定 copy_context, 与 asyncio.to_thread 同语义
# 2026-11-15 - 小欧 - 新增 WorkerSlots/SlotLease: 有界并发闸门显式记账"在途"与"随线程永久损耗",
#   取代 BoundedSemaphore 在不可中断原生调用卡死时永久占用且无法区分持有者的问题; 凭证一次性, 迟到回调幂等
# 2026-11-15 - 小欧 - 修复槽位容量永久泄漏: 超时 mark_lost 后线程迟到归还时回收已记损耗(原 _active 单标志
#   使迟到回调空操作, 瞬时超时反复发生会把 available 永久侵蚀到 0); SlotLease 状态机 held/released/lost
#   与计数在同一把 cond 锁内原子推进, 消除 mark_lost(事件循环线程)与 release(worker 线程)并发双扣
"""workers — 常驻线程池(运行期零 Thread.start) — 小欧 2026-11-04

【为什么要有这个模块】Windows 上 `Thread.start()` 内部 `self._started.wait()` 无超时, 新线程
bootstrap 要拿 loader lock; 而 `CreateProcessW` 调用期持 loader lock 且不释放 GIL → 二者并发
即永久互锁, 线程报废(实证 logs/pyspy/hang_20261104_0115_final_nonblocking.txt)。
⇒ 凡是"偶发但致命"的阻塞动作, 线程必须在启动期建好, 运行期只入队。

【两类语义, 不合并】
  WorkerPool      : 任务一次性返回 → submit() 得 Future, 有界等待用 fut.result(timeout)。
                    超时抛 TimeoutError, 任务仍在池内继续跑(放弃等待 ≠ 中断任务)。
  ThreadLeasePool : 任务长期服务某个持有者(如 shell 实例的 stdin 写线程) → lease() 租一个
                    worker, 任务返回即归还; 任务卡死则该槽位永久损失, lease 有界失败。
两者都只是 `queue.put` + 常驻线程, 不引入额外抽象(YAGNI)。
"""
import concurrent.futures
import contextvars
import functools
import queue
import threading
from typing import Any, Callable, Optional

from app.logger import logger

__all__ = ["WorkerPool", "SlotLease", "WorkerSlots", "ThreadLeasePool"]


class WorkerPool:
    """固定 N 个常驻 daemon 线程: submit 只入队, 运行期零 Thread.start — 2026-11-04 小欧

    为什么不用 ThreadPoolExecutor: worker 懒创建, 且 submit 会在调用线程里 Thread.start()
    (concurrent/futures/thread.py _adjust_thread_count) —— 调用方常在事件循环线程, 一旦
    线程创建停顿, 事件循环当场僵死(2026-11-04 事故形态)。本类构造期一次建满。
    """

    def __init__(self, n: int, name: str):
        self.size = n
        self._q: "queue.Queue" = queue.Queue()
        for i in range(n):
            threading.Thread(target=self._run, name=f"{name}-{i}", daemon=True).start()

    def _run(self) -> None:
        while True:
            fn, fut = self._q.get()
            # 排队期已被取消的任务直接丢弃; RUNNING 后 cancel() 无效, 结果照常回填
            if not fut.set_running_or_notify_cancel():
                continue
            try:
                fut.set_result(fn())
            except BaseException as e:      # noqa: BLE001 - 必须回填, 否则等待方永久悬挂
                fut.set_exception(e)

    def submit(self, fn: Callable[[], Any]) -> "concurrent.futures.Future":
        fut: "concurrent.futures.Future" = concurrent.futures.Future()
        # 2026-11-05 小欧 - 常驻线程不继承 ContextVar(task_id/session_id/hooks): 提交时绑定调用方上下文, 否则齐丢
        self._q.put((functools.partial(contextvars.copy_context().run, fn), fut))
        return fut


class SlotLease:
    """一次槽位占用的凭证(一次性) — 2026-11-15 小欧

    为什么需要凭证: 只用计数器无法区分"哪个请求持有哪一格"。一旦某请求被判损耗,
    它迟到的 done_callback 若仍执行 release(), 会把**别人**正在用的槽位减掉,
    造成容量虚增(比原信号量泄漏更危险)。凭证状态机 held/released/lost 保证每次
    持有只结算一次; 且迟到归还(超时后才真正返回)会回收先前记的永久损耗,
    避免瞬时超时反复发生把 available 永久侵蚀到 0。状态与计数同锁内原子推进。
    """

    _HELD, _RELEASED, _LOST = "held", "released", "lost"

    __slots__ = ("_slots", "_state")

    def __init__(self, slots: "WorkerSlots") -> None:
        self._slots = slots
        self._state = self._HELD

    def release(self) -> None:
        self._slots._settle(self, lost=False)

    def mark_lost(self) -> None:
        self._slots._settle(self, lost=True)


class WorkerSlots:
    """有界并发闸门: 区分"在途"与"随线程永久损耗" — 2026-11-15 小欧

    BoundedSemaphore 只能表达占用/空闲; 执行体卡死在不可中断的原生调用里时, 线程永久报废,
    其 done_callback 永不触发, 信号量却永久占用 —— 计数与真实可用线程从此错位(exp1 实测)。
    本类把损耗显式记账: mark_lost() 把一次持有转为永久损耗, 可用量随之下调,
    失败信息能说出真实原因, 不再表现成"莫名其妙拿不到 worker"。
    """

    def __init__(self, size: int):
        self.size = size
        self._cond = threading.Condition()
        self._in_use = 0
        self._lost = 0

    def acquire(self) -> Optional[SlotLease]:
        """非阻塞占位; 满则返回 None(排队由调用方在 event loop 里做, 不阻塞线程)。"""
        with self._cond:
            if self._in_use + self._lost >= self.size:
                return None
            self._in_use += 1
            return SlotLease(self)

    def _settle(self, lease: "SlotLease", *, lost: bool) -> None:
        """原子结算一次持有 — 2026-11-15 小欧
        held  -> released : 正常归还, 在途 -1
        held  -> lost     : 超时未归还, 在途 -1 且损耗 +1(容量随之下调)
        lost  -> released : 迟到归还(线程实际已返回), 回收先前记的损耗, 容量回归
        状态与计数同锁内推进, mark_lost(事件循环线程)与 release(worker 线程)并发亦不双扣。
        """
        with self._cond:
            state = lease._state
            if state == SlotLease._HELD:
                self._in_use -= 1
                if lost:
                    lease._state = SlotLease._LOST
                    self._lost += 1
                else:
                    lease._state = SlotLease._RELEASED
            elif state == SlotLease._LOST and not lost:
                lease._state = SlotLease._RELEASED
                self._lost -= 1
            # 其余情况(已 released / 已 lost 再次 lost): 幂等忽略

    @property
    def lost(self) -> int:
        with self._cond:
            return self._lost

    @property
    def available(self) -> int:
        with self._cond:
            return max(0, self.size - self._in_use - self._lost)


class ThreadLeasePool:
    """N 个常驻 daemon 线程, 按租约长期服务某个持有者 — 2026-11-04 小欧

    租约归还 = 任务函数正常返回; 任务卡住 ⇒ 该槽位永久损失(不掩盖), lease 有界失败后
    由调用方决定兜底或降级, 绝不无限等待。
    """

    def __init__(self, n: int, name: str):
        self.size = n
        self._jobs: "queue.Queue" = queue.Queue()
        self._idle = threading.Semaphore(0)
        for i in range(n):
            threading.Thread(target=self._run, name=f"{name}-{i}", daemon=True).start()

    def _run(self) -> None:
        self._idle.release()                    # 就绪, 可接租约
        while True:
            fn = self._jobs.get()
            try:
                fn()
            except BaseException as e:          # noqa: BLE001 - worker 不能因单个租约异常而退出
                logger.error(f"[线程池] 租约任务异常(worker 继续服务): {e!r}")
            finally:
                self._idle.release()

    def lease(self, fn: Callable[[], None], timeout: float) -> bool:
        """租一个空闲 worker 执行 fn; 池满/全卡住 → 超时返回 False。"""
        if not self._idle.acquire(timeout=timeout):
            return False
        # 2026-11-05 小欧 - 同 submit: 租约任务也在常驻线程里跑, 必须显式携带调用方 context
        self._jobs.put(functools.partial(contextvars.copy_context().run, fn))
        return True
