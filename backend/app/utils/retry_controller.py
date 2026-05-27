"""
重试控制器 - 统一管理重试次数

设计原理：
1. 重试次数控制：最多3次（总共4次调用）
2. 状态重置：每次新请求时重置计数器
3. 简洁设计：只负责重试次数，不负责计时（计时由 IdleTimeoutIterator 负责）

【重构 2026-05-27 小沈】_calculate_retry_delay委托到RetryEngine统一退避策略
"""

from app.utils.logger import setup_logger
from app.utils.retry_engine import RetryEngine, BackoffStrategy

logger = setup_logger(__name__)

_DEFAULT_ENGINE = RetryEngine(
    max_retries=10,
    backoff_strategy=BackoffStrategy.EXPONENTIAL,
    backoff_factor=2.0,
)


class RetryController:
    """统一的重试次数控制器
    
    功能：
    - 重试次数管理：控制重试次数，判断是否还能重试
    - 状态重置：开始新请求时重置计数器
    
    注意：空闲超时检测由 IdleTimeoutIterator 负责，此类只管理重试次数
    """
    
    def __init__(self, max_retries: int = 3):
        """
        初始化控制器
        
        Args:
            max_retries: 最大重试次数，默认3次（总共4次调用）
        """
        self.max_retries = max_retries
        self.retry_count = 0
    
    def can_retry(self) -> bool:
        """
        是否还能重试
        
        Returns:
            bool: True=可以重试，False=已达到最大重试次数
        """
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> int:
        """
        增加重试次数
        
        Returns:
            int: 增加后的重试次数
        """
        self.retry_count += 1
        logger.info(f"[RetryController] 重试次数增加：{self.retry_count}/{self.max_retries}")
        return self.retry_count
    
    def get_retry_count(self) -> int:
        """
        获取当前重试次数
        
        Returns:
            int: 当前重试次数（0=首次调用，1=第1次重试，...）
        """
        return self.retry_count
    
    def is_first_attempt(self) -> bool:
        """
        是否是首次尝试
        
        Returns:
            bool: True=首次调用，False=重试中
        """
        return self.retry_count == 0
    
    def reset(self) -> None:
        """
        重置重试计数器
        
        用于开始全新的请求
        """
        self.retry_count = 0
        logger.debug("[RetryController] 重试计数器已重置")
    
    def __repr__(self) -> str:
        return f"RetryController(max_retries={self.max_retries}, retry_count={self.retry_count})"


def _calculate_retry_delay(
    retry_count: int, base: int = 2, max_wait: int = 30
) -> float:
    """
    计算指数退避等待时间 — 委托到RetryEngine统一退避策略 — 小沈 2026-05-27

    使用场景:
        重试场景下计算下次重试前的等待秒数，替代硬编码的 2**retry_count 退避逻辑。
        供 base_react._handle_parse_error、llm_core、chat_stream_query 共同复用。

    使用示例/常用名转换说明:
        _calculate_retry_delay(0)  → 1.0   (首次重试等待1秒)
        _calculate_retry_delay(1)  → 2.0
        _calculate_retry_delay(3)  → 8.0
        _calculate_retry_delay(5)  → 30.0  (max_wait截断)
        _calculate_retry_delay(10) → 30.0  (max_wait截断)
        _calculate_retry_delay(3, base=3, max_wait=60) → 27.0

    返回数据说明:
        float: 等待秒数，范围 [1.0, max_wait]

    Args:
        retry_count: 当前重试次数（0=首次重试）
        base: 指数底数，默认2
        max_wait: 最大等待秒数，默认30
    """
    if retry_count < 0:
        retry_count = 0
    if base < 2:
        base = 2
    engine = RetryEngine(
        max_retries=10,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=float(base),
    )
    delay = engine._calculate_delay(retry_count + 1)
    return min(delay, float(max_wait))