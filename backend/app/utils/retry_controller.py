"""
重试控制器 - 统一管理重试次数

设计原理：
1. 重试次数控制：最多3次（总共4次调用）
2. 状态重置：每次新请求时重置计数器
3. 简洁设计：只负责重试次数，不负责计时（计时由 IdleTimeoutIterator 负责）

使用方法：
    controller = RetryController(max_retries=3)
    
    # 检查是否还能重试
    if controller.can_retry():
        controller.increment_retry()
        # 执行重试...
    
    # 开始新请求时
    controller.reset()
"""

import logging

logger = logging.getLogger(__name__)


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