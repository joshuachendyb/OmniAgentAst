# -*- coding: utf-8 -*-
"""
执行器增强模块 - 小健

T3: 执行器增强（重试+熔断+错误分类）
参考文档: Omni系统tool-实现分析报告 v1.15 第6.2.3节

创建时间: 2026-04-19 09:30:00
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Any, Callable, List, Optional

from app.services.agent.tool_executor import ErrorType, ErrorClassifier

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"         # 打开（熔断）
    HALF_OPEN = "half_open"  # 半开（尝试）


class CircuitBreaker:
    """熔断器"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败次数阈值（达到后熔断）
            recovery_timeout: 恢复超时（秒）
            success_threshold: 成功次数阈值（达到后恢复）
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self._failure_count = 0
        self._success_count = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time: Optional[float] = None
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            # 检查是否应该进入半开状态
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state
    
    def record_success(self) -> None:
        """记录成功"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info("Circuit breaker reset to CLOSED")
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)
    
    def record_failure(self) -> None:
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning("Circuit breaker OPEN after failure in HALF_OPEN")
        elif self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        return self.state != CircuitState.OPEN


class RetryPolicy:
    """重试策略"""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        retryable_errors: Optional[List[str]] = None
    ):
        """
        初始化重试策略
        
        Args:
            max_retries: 最大重试次数
            backoff_factor: 退避因子
            retryable_errors: 可重试错误列表
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retryable_errors = retryable_errors or ["timeout", "network_error"]
        
        self._circuit_breaker = CircuitBreaker()
    
    async def execute_with_retry(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行操作（带重试）
        
        Args:
            operation: 异步操作函数
            *args, **kwargs: 操作参数
        
        Returns:
            结果dict: {"status": "success", "result": ...} 或 {"status": "error", "error": ..., "retry_count": N}
        """
        attempt_count = 0
        last_error: Optional[Exception] = None
        
        while attempt_count <= self.max_retries:
            try:
                # 检查熔断器
                if not self._circuit_breaker.can_execute():
                    return {
                        "status": "error",
                        "error": "Circuit breaker is OPEN",
                        "error_type": ErrorType.CIRCUIT_OPEN.value,
                        "retry_count": attempt_count
                    }
                
                # 执行操作
                result = await operation(*args, **kwargs)
                
                # 成功记录
                self._circuit_breaker.record_success()
                return {
                    "status": "success",
                    "result": result,
                    "retry_count": attempt_count
                }
                
            except Exception as e:
                last_error = e
                attempt_count += 1
                
                # 分类错误
                error_type = ErrorClassifier.classify(e)
                
                # 检查是否可重试
                if not ErrorClassifier.is_retryable(error_type, self.retryable_errors):
                    # 不可重试，记录失败并返回
                    self._circuit_breaker.record_failure()
                    return {
                        "status": "error",
                        "error": str(e),
                        "error_type": error_type.value,
                        "retry_count": attempt_count - 1
                    }
                
                # 记录失败
                self._circuit_breaker.record_failure()
                
                # 检查是否还有重试机会
                if attempt_count > self.max_retries:
                    logger.warning(f"Max retries {self.max_retries} exceeded")
                    return {
                        "status": "error",
                        "error": str(e),
                        "error_type": error_type.value,
                        "retry_count": attempt_count
                    }
                
                # 等待后重试（指数退避）
                if attempt_count <= self.max_retries:
                    wait_time = self.backoff_factor ** (attempt_count - 1)
                    logger.info(f"Retrying after {wait_time}s (attempt {attempt_count}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
        
        # 最后的错误
        return {
            "status": "error",
            "error": str(last_error),
            "error_type": ErrorType.UNKNOWN.value,
            "retry_count": attempt_count
        }
    
    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """获取熔断器"""
        return self._circuit_breaker