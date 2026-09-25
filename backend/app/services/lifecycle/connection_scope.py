# -*- coding: utf-8 -*-
"""
connection_scope — 共享连接池唯一所有者(一代配置 = 一个 scope)

[70] ConnectionScope连接池统一所有者实施方案 — 小欧 2026-09-25
职责(SRP): 池由它建(ensure_pool), 计数由它发(acquire_lease), 换代由它退休(release_owner),
停机由它等(drain); 不做业务查询(决议留 resolver), 不做归还中介(快照 close 直线 release)。
生命周期模型见 [70] 2.3: 无状态机, 纯引用计数——owner 归还后零穿越只可能在退休后,
close_on_zero 天然实现"活动任务撑池不关、任务全结束后最后一个 release 归零 aclose"。
"""

import asyncio
import time
from typing import Optional

from app.logger import logger
from app.llm import BaseAIService, SharedClientLease

# 换代归还的 owner 释放协程强引用表: asyncio 仅持 Task 弱引用, GC 回收会取消协程致 ref 悬挂,
# 强引用持有, done 时 discard 防泄漏(与 orchestrator._background_tasks 同精神) — 小欧 2026-09-25
_pending_release_tasks: set = set()


class ConnectionScope:
    """共享 httpx 连接池唯一所有者 — 一代配置(单例+池)的生命周期锚 — [70] 小欧 2026-09-25"""

    def __init__(self, ai_service: BaseAIService) -> None:
        """持本代单例(池未建); owner lease 于 ensure_pool 建立(计数起点=1) — 小欧 2026-09-25"""
        self.ai_service = ai_service
        self._owner_lease: Optional[SharedClientLease] = None
        self._owner_released = False

    def ensure_pool(self) -> None:
        """建池 + 所有权移交(幂等): 首次经 ai_service.ensure_client_pool() 建 LLMClient 池并
        relinquish_ownership(保留使用引用不关池), SharedClientLease(client) 计数起点=1 — [70] 2.4 小欧 2026-09-25"""
        if self._owner_lease is not None:
            return
        client = self.ai_service.ensure_client_pool()
        self._owner_lease = SharedClientLease(client)

    def acquire_lease(self) -> SharedClientLease:
        """任务/快照借用本代池(ref+1)。已退休/未初始化抛 RuntimeError(防新任务混入旧代);
        池已归零(_closing)由素材 SharedClientLease.acquire 自身拦截(双重防线) — [70] 2.3 小欧 2026-09-25"""
        if self._owner_lease is None:
            raise RuntimeError("ConnectionScope 未初始化(池未建), 禁止借用")
        if self._owner_released:
            raise RuntimeError("ConnectionScope 已退休(换代/停机), 禁止新任务混入旧代")
        return self._owner_lease.acquire()

    def release_owner(self) -> None:
        """换代/停机归还 owner 引用(幂等, ref-1; 归零由素材 close_on_zero 自动 aclose)。
        调度参照 close_instance_sync 双分支: 运行中事件循环 create_task(强引用防 GC 取消),
        无运行循环 asyncio.run 同步完成 — [70] 2.2; reset() 新语义即此调用 — 小欧 2026-09-25"""
        if self._owner_released or self._owner_lease is None:
            return
        self._owner_released = True
        coro = self._owner_lease.release()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None:
            task = loop.create_task(coro)
            _pending_release_tasks.add(task)
            task.add_done_callback(_pending_release_tasks.discard)
        else:
            asyncio.run(coro)

    async def drain(self, timeout: float = 30.0) -> None:
        """停机收口: 等本代池 lease 全部归零关闭(0.1s 轮询, 超时记 warning 放行不阻塞退出)。
        归零关闭由 release 触发, 本函数只等 — [70] 2.3 小欧 2026-09-25"""
        deadline = time.monotonic() + timeout
        while self.ref_count > 0:
            if time.monotonic() >= deadline:
                logger.warning(
                    f"[ConnectionScope] drain 超时{timeout}s 放行: 剩余 ref={self.ref_count}(活动任务未结束)")
                return
            await asyncio.sleep(0.1)
        # 归零与 aclose 之间存在微窗口(最后一个 release 协程在途), 短歇让关闭收尾 — 小欧 2026-09-25
        await asyncio.sleep(0.05)

    @property
    def ref_count(self) -> int:
        """池引用计数(owner 未归还时含 1) — 可观测/测试断言 — [70] 2.4 小欧 2026-09-25"""
        if self._owner_lease is None:
            return 0
        return self._owner_lease.ref_count

    @property
    def is_released(self) -> bool:
        """退休态(owner 已归还) — 替代四态状态机的直接观测 — [70] 2.3 小欧 2026-09-25"""
        return self._owner_released
