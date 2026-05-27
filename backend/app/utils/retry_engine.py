# -*- coding: utf-8 -*-
"""
统一重试引擎

消除4套独立重试机制的重复：
1. llm_core._post_with_retry() — 非流式429重试
2. llm_core._StreamRetryContext — 流式429重试
3. retry_policy.RetryPolicy — 工具执行重试（含熔断器）
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
    
    支持配置化退避策略和重试条件，各场景配置不同参数但共享同一引擎。
    实现SRP（重试策略单一职责）+ DRY（统一入口）+ OCP（新增重试场景只配置参数）。
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
            backoff_strategy: 退避策略（固定/指数）
            backoff_factor: 退避因子（指数退避的基数）
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
            attempt: 当前重试次数（从1开始）

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
        执行操作（带重试）

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

    async def execute_context(
        self, operation_factory: Callable, *args, **kwargs
    ) -> Any:
        """
        异步上下文管理器模式执行（用于流式请求等场景）

        每次重试都创建新的operation实例（通过factory函数）。

        Args:
            operation_factory: 创建操作实例的工厂函数
            *args, **kwargs: 工厂参数

        Returns:
            操作实例
        """
        self._attempt_count = 0

        while self._attempt_count <= self._max_retries:
            try:
                return operation_factory(*args, **kwargs)
            except Exception as e:
                self._attempt_count += 1

                if not self._is_retryable(e):
                    raise

                if self._on_retry:
                    self._on_retry(self._attempt_count, e)

                if self._attempt_count >= self._max_retries:
                    raise

                delay = self._calculate_delay(self._attempt_count)
                await asyncio.sleep(delay)

        raise RuntimeError("RetryEngine: max retries exceeded")

    @property
    def attempt_count(self) -> int:
        """当前重试次数"""
        return self._attempt_count

    @property
    def max_retries(self) -> int:
        """最大重试次数"""
        return self._max_retries


def create_rate_limit_retry_engine(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
    is_rate_limit_fn: Optional[Callable[[Exception], bool]] = None,
) -> RetryEngine:
    """
    创建429限流重试引擎

    专门处理HTTP 429限流重试，指数退避+max_retries=3。
    统一llm_core._post_with_retry()和_StreamRetryContext的核心429重试逻辑。

    Args:
        max_retries: 最大重试次数
        backoff_factor: 退避因子
        is_rate_limit_fn: 判断是否为限流异常的函数

    Returns:
        配置好的RetryEngine实例
    """
    return RetryEngine(
        max_retries=max_retries,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=backoff_factor,
        retryable_check=is_rate_limit_fn,
    )


__all__ = [
    "BackoffStrategy",
    "RetryEngine",
    "create_rate_limit_retry_engine",
]
