# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 - 小欧 - 新建: 统一常驻线程池(WorkerPool/ThreadLeasePool), 取代 serial_worker.py 与两处私有池实现
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
import queue
import threading
from typing import Any, Callable

from app.logger import logger

__all__ = ["WorkerPool", "ThreadLeasePool"]


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
        self._q.put((fn, fut))
        return fut


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
        self._jobs.put(fn)
        return True
