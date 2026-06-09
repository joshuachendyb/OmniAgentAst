# -*- coding: utf-8 -*-
"""
统一重试引擎

消除4套独立重试机制的重复:
1. llm_core._post_with_retry() — 非流式429重试
2. llm_core._StreamRetryContext — 流式429重试
3. retry_policy.RetryPolicy — 工具执行重试(含熔断器)
4. base_react内联 — parse/empty_response重试

各场景配置不同参数但共享同一引擎。
Author: 小沈 - 2026-05-27
"""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger


class BackoffStrategy(Enum):
    """退避策略枚举"""
    FIXED = "fixed"
    EXPONENTIAL = "exponential"


class RetryEngine:
    """
    通用重试引擎
    
    支持配置化退避策略和重试条件,各场景配置不同参数但共享同一引擎。
    实现SRP(重试策略单一职责)+ DRY(统一入口)+ OCP(新增重试场景只配置参数)。
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL,
        backoff_factor: float = 2.0,
        retryable_check: Optional[Callable[[Exception], bool]] = None,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ):
        """
        初始化重试引擎

        Args:
            max_retries: 最大重试次数
            backoff_strategy: 退避策略(固定/指数)
            backoff_factor: 退避因子(指数退避的基数)
            retryable_check: 判断异常是否可重试的函数
            on_retry: 每次重试前的回调
        """
        self._max_retries = max_retries
        self._backoff_strategy = backoff_strategy
        self._backoff_factor = backoff_factor
        self._retryable_check = retryable_check
        self._on_retry = on_retry
        self._attempt_count = 0

    def _calculate_delay(self, attempt: int) -> float:
        """
        计算退避延迟

        Args:
            attempt: 当前重试次数(从1开始)

        Returns:
            延迟秒数
        """
        if self._backoff_strategy == BackoffStrategy.FIXED:
            return self._backoff_factor
        return self._backoff_factor ** (attempt - 1)

    def _is_retryable(self, error: Exception) -> bool:
        """判断异常是否可重试"""
        if self._retryable_check is not None:
            return self._retryable_check(error)
        return True

    async def execute(self, operation: Callable, *args, **kwargs) -> Any:
        """
        执行操作(带重试)

        Args:
            operation: 异步操作函数
            *args, **kwargs: 操作参数

        Returns:
            操作结果

        Raises:
            Exception: 重试耗尽后抛出最后一次异常
        """
        self._attempt_count = 0
        last_error: Optional[Exception] = None

        while self._attempt_count <= self._max_retries:
            try:
                result = await operation(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                self._attempt_count += 1

                if not self._is_retryable(e):
                    raise

                if self._on_retry:
                    self._on_retry(self._attempt_count, e)
                else:
                    logger.warning(
                        f"[RetryEngine] 重试 {self._attempt_count}/{self._max_retries}: {str(e)[:100]}"
                    )

                if self._attempt_count >= self._max_retries:
                    raise

                delay = self._calculate_delay(self._attempt_count)
                await asyncio.sleep(delay)

        raise last_error


    async def _wait_before_retry(self, error: Optional[Exception]) -> None:
        """等待重试 - 小沈 2026-06-08"""
        delay = self._calculate_delay(self._attempt_count)
        if self._on_retry:
            self._on_retry(self._attempt_count, error)
        else:
            if error is None:
                logger.warning(f"[RetryEngine] 结果需重试 {self._attempt_count}/{self._max_retries},{delay:.0f}s后重试")
            else:
                logger.warning(f"[RetryEngine] 异常重试 {self._attempt_count}/{self._max_retries}: {str(error)[:100]}")
        await asyncio.sleep(delay)

    async def _try_context(self, ctx_factory: Callable, result_check: Callable[[Any], bool]) -> tuple:
        """尝试执行上下文操作 - 小沈 2026-06-08"""
        ctx = ctx_factory()
        result = await ctx.__aenter__()
        self._attempt_count += 1

        if not result_check(result):
            return ctx, result

        await ctx.__aexit__(None, None, None)

        if self._attempt_count >= self._max_retries:
            logger.error(f"[RetryEngine] 重试耗尽 {self._attempt_count}/{self._max_retries},返回最后结果")
            return None, result

        await self._wait_before_retry(None)
        return None, None

    async def _handle_context_exception(self, ctx, error: Exception):
        """处理上下文异常 - 小沈 2026-06-08"""
        if ctx is not None:
            await ctx.__aexit__(type(error), error, error.__traceback__)
        
        if not self._is_retryable(error):
            return error

        self._attempt_count += 1
        await self._wait_before_retry(error)

        if self._attempt_count >= self._max_retries:
            raise error

        return None

    async def execute_async_context(
        self,
        ctx_factory: Callable,
        result_check: Callable[[Any], bool],
    ) -> tuple:
        """
        异步上下文管理器模式执行(基于返回值判断重试)

        用于流式请求等场景:ctx_factory返回异步上下文管理器,
        result_check判断结果是否需要重试(True=需要重试)。

        与execute()的关键差异:
        - 基于返回值判断重试(而非异常)
        - 正确处理异步上下文管理器的__aenter__/__aexit__
        - 重试耗尽返回最后结果(不抛异常)

        Args:
            ctx_factory: 创建异步上下文管理器的工厂函数
            result_check: 结果检查函数,返回True表示需要重试

        Returns:
            (ctx, result) 元组:ctx为打开的上下文管理器(需调用方在用完后关闭),
            result为__aenter__的返回值
        """
        self._attempt_count = 0
        ctx = None
        result = None

        while self._attempt_count <= self._max_retries:
            try:
                ctx, result = await self._try_context(ctx_factory, result_check)
                if result is not None:
                    return ctx, result
            except Exception as e:
                exc = await self._handle_context_exception(ctx, e)
                if exc is not None:
                    raise exc
                ctx = None

        return ctx, result

    @property
    def attempt_count(self) -> int:
        """当前重试次数"""
        return self._attempt_count

    @property
    def max_retries(self) -> int:
        """最大重试次数"""
        return self._max_retries

    @property
    def exhausted(self) -> bool:
        """重试是否已耗尽(必须用 >=)"""
        return self._attempt_count >= self._max_retries

    @property
    def current_delay(self) -> float:
        """当前退避延迟(在 record_attempt() 之前调用)"""
        return self._calculate_delay(self._attempt_count + 1)

    def record_attempt(self) -> int:
        """手动记录一次重试尝试(用于非execute模式的重试场景,如空响应截断重试)"""
        self._attempt_count += 1
        return self._attempt_count

    def reset_attempts(self) -> None:
        """重置重试计数(用于收到有效响应后重置空响应计数)"""
        self._attempt_count = 0



def create_retry_engine(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> RetryEngine:
    """创建标准重试引擎 — 消除 network_retry/sse_retry 完全重复 — 小欧 2026-06-09"""
    return RetryEngine(
        max_retries=max_retries,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=backoff_factor,
    )


__all__ = [
    "BackoffStrategy",
    "RetryEngine",
    "create_retry_engine",
]
