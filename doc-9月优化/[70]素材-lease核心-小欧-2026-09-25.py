# [70] 方案素材 — lease 核心引用计数实现（原样摘出，未改动一行）
# 来源: F:\OmniAgentAs-repair\backend\app\llm\client_sdk.py 第64-146行（未提交工作树）
# 摘取时间: 2026-09-25 11:35:22
# 摘取人: 小欧
# 用途: ConnectionScope 方案吸收其引用计数语义（[69] 文档 5.4 改判 A 执行路径步骤①）
# 依赖: import inspect / import threading / typing.Any / app.logger.logger
# 说明: 摘出后工作树 client_sdk.py 已 git restore 回 HEAD（本素材是该两段代码的唯一存档，
#       连同 backup-6files未提交改动-2026-09-25.patch 全量备份互为兜底）

class _SharedClientPool:
    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
        self.client = client
        self.close_on_zero = close_on_zero
        self._ref_count = 1
        self._closing = False
        self._lock = threading.Lock()

    def acquire(self) -> "SharedClientLease":
        with self._lock:
            if self._closing:
                raise RuntimeError("共享 httpx 客户端已关闭，不能继续获取 lease")
            self._ref_count += 1
        return SharedClientLease._from_pool(self)

    def release(self) -> bool:
        with self._lock:
            if self._closing or self._ref_count <= 0:
                return False
            self._ref_count -= 1
            if self._ref_count != 0 or not self.close_on_zero:
                return False
            self._closing = True
            return True

    @property
    def ref_count(self) -> int:
        with self._lock:
            return self._ref_count

    @property
    def closing(self) -> bool:
        with self._lock:
            return self._closing

    async def close(self) -> None:
        if getattr(self.client, "is_closed", False) is True:
            return
        try:
            result = self.client.aclose()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.warning(f"[LLM] 共享 httpx 客户端关闭失败: {exc}")


class SharedClientLease:
    """共享连接池的一次引用；释放幂等，最后一个引用负责关闭。"""

    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
        self._pool = _SharedClientPool(client, close_on_zero=close_on_zero)
        self._released = False

    @classmethod
    def _from_pool(cls, pool: _SharedClientPool) -> "SharedClientLease":
        lease = cls.__new__(cls)
        lease._pool = pool
        lease._released = False
        return lease

    @property
    def client(self) -> Any:
        return self._pool.client

    @property
    def ref_count(self) -> int:
        return self._pool.ref_count

    @property
    def is_released(self) -> bool:
        return self._released

    def acquire(self) -> "SharedClientLease":
        if self._released:
            raise RuntimeError("已释放的 lease 不能继续获取引用")
        return self._pool.acquire()

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._pool.release():
            await self._pool.close()
