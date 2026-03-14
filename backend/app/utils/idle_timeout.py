"""
空闲超时异步迭代器 - 通用的实时超时检测机制

设计原理：
1. 包装任何异步迭代器
2. 实时检测空闲超时（从上次收到内容开始计时）
3. 与业务逻辑完全解耦
4. 可复用于任何异步迭代场景

使用方法：
    async def my_async_iterator():
        yield "chunk1"
        await asyncio.sleep(40)  # 超过30秒
        yield "chunk2"  # 不会执行，会抛出 IdleTimeoutError
    
    wrapper = IdleTimeoutIterator(my_async_iterator(), timeout_seconds=30)
    async for item in wrapper:
        print(item)  # 只会打印 "chunk1"，然后抛出 IdleTimeoutError
"""

import asyncio
import time
import logging
from typing import AsyncIterator, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IdleTimeoutError(Exception):
    """空闲超时异常"""
    def __init__(self, message: str = "空闲超时：超过指定时间未收到内容", timeout_seconds: float = 30):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"{message}（超时阈值{timeout_seconds}秒）")


class IdleTimeoutIterator(Generic[T]):
    """带空闲超时检测的异步迭代器包装器
    
    功能：
    1. 包装任何异步迭代器
    2. 从上次收到内容开始计时
    3. 超过指定时间未收到下一个内容，抛出 IdleTimeoutError
    4. 提供重置计时器、获取空闲时间等方法
    
    使用场景：
    - AI流式响应超时检测
    - 网络流超时检测
    - 任何需要空闲超时的异步迭代场景
    """
    
    def __init__(
        self, 
        iterator: AsyncIterator[T], 
        timeout_seconds: float = 30.0,
        name: str = "iterator"
    ):
        """
        初始化空闲超时迭代器
        
        Args:
            iterator: 原始异步迭代器
            timeout_seconds: 空闲超时秒数，默认30秒
            name: 迭代器名称（用于日志）
        """
        self._iterator = iterator
        self._timeout = timeout_seconds
        self._name = name
        self._last_content_time: float = time.time()
        self._started = False
        self._count = 0
    
    def __aiter__(self) -> 'IdleTimeoutIterator[T]':
        """返回异步迭代器"""
        return self
    
    async def __anext__(self) -> T:
        """获取下一个元素，带空闲超时检测
        
        Returns:
            T: 下一个元素
            
        Raises:
            IdleTimeoutError: 空闲超时
            StopAsyncIteration: 迭代结束
        """
        if not self._started:
            self._started = True
            self._last_content_time = time.time()
            logger.debug(f"[IdleTimeoutIterator-{self._name}] 开始迭代，超时={self._timeout}秒")
        
        # 计算剩余空闲时间
        elapsed = time.time() - self._last_content_time
        remaining = self._timeout - elapsed
        
        if remaining <= 0:
            # 已超时
            logger.warning(f"[IdleTimeoutIterator-{self._name}] 空闲超时：已过{elapsed:.1f}秒（阈值{self._timeout}秒）")
            raise IdleTimeoutError(
                f"空闲超时：{self._name}超过{self._timeout}秒未收到内容",
                timeout_seconds=self._timeout
            )
        
        try:
            # 使用 asyncio.wait_for 设置超时
            result = await asyncio.wait_for(
                self._iterator.__anext__(),
                timeout=remaining
            )
            
            # 收到内容，重置计时器
            self._last_content_time = time.time()
            self._count += 1
            
            # 日志（每10个元素记录一次）
            if self._count % 10 == 1:
                logger.debug(f"[IdleTimeoutIterator-{self._name}] 收到第{self._count}个元素")
            
            return result
            
        except asyncio.TimeoutError:
            # 等待超时
            elapsed = time.time() - self._last_content_time
            logger.warning(f"[IdleTimeoutIterator-{self._name}] 空闲超时：等待{remaining:.1f}秒后超时（总共{elapsed:.1f}秒）")
            raise IdleTimeoutError(
                f"空闲超时：{self._name}等待内容超时",
                timeout_seconds=self._timeout
            )
        except StopAsyncIteration:
            # 迭代正常结束
            logger.debug(f"[IdleTimeoutIterator-{self._name}] 迭代结束，共{self._count}个元素")
            raise
    
    # ==================== 状态查询方法 ====================
    
    def get_elapsed_time(self) -> float:
        """获取从上次收到内容到现在经过的秒数"""
        return time.time() - self._last_content_time
    
    def get_remaining_time(self) -> float:
        """获取距离超时还有多少秒"""
        elapsed = time.time() - self._last_content_time
        return max(0.0, self._timeout - elapsed)
    
    def get_count(self) -> int:
        """获取已收到的元素数量"""
        return self._count
    
    def reset_timer(self) -> None:
        """手动重置计时器（用于外部控制）"""
        self._last_content_time = time.time()
        logger.debug(f"[IdleTimeoutIterator-{self._name}] 计时器已手动重置")
    
    def __repr__(self) -> str:
        return (f"IdleTimeoutIterator(name={self._name}, "
                f"timeout={self._timeout}s, "
                f"count={self._count}, "
                f"elapsed={self.get_elapsed_time():.1f}s)")


# ==================== 便捷函数 ====================

def wrap_with_idle_timeout(
    iterator: AsyncIterator[T], 
    timeout_seconds: float = 30.0,
    name: str = "iterator"
) -> IdleTimeoutIterator[T]:
    """
    便捷函数：包装异步迭代器，添加空闲超时检测
    
    Args:
        iterator: 原始异步迭代器
        timeout_seconds: 超时秒数
        name: 迭代器名称
    
    Returns:
        IdleTimeoutIterator: 包装后的迭代器
    
    Example:
        async for chunk in wrap_with_idle_timeout(ai_service.chat_stream(), timeout_seconds=30):
            process(chunk)
    """
    return IdleTimeoutIterator(iterator, timeout_seconds=timeout_seconds, name=name)