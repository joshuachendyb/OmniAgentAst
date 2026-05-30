# -*- coding: utf-8 -*-
"""
通用LRU缓存模块

功能：提供通用的LRU缓存实现，支持并发访问、异常处理和日志记录

设计原则：
- SRP：职责单一，只负责缓存管理
- DRY：复用现有数据结构（OrderedDict）
- KISS：实现简单，易于理解
- OCP：可扩展，支持配置参数

作者：小沈
创建时间：2026-05-30
"""

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

from app.utils.logger import logger


class LRUCache:
    """通用LRU缓存
    
    特点：
    1. 线程安全：使用threading.Lock保证并发安全
    2. 异常处理：缓存异常不影响主流程
    3. 日志记录：异常必须记录，统计定期记录
    4. 自动清理：LRU策略，防止内存泄漏
    """
    
    def __init__(self, max_size: int = 1000, log_interval: int = 100):
        """
        初始化缓存
        
        Args:
            max_size: 最大缓存条目数
            log_interval: 日志记录间隔（操作次数）
        """
        self._cache: OrderedDict = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._operation_count = 0
        self._log_interval = log_interval
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存
        
        Args:
            key: 缓存key
            
        Returns:
            缓存值，未命中返回None
        """
        try:
            with self._lock:
                if key in self._cache:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    self._operation_count += 1
                    self._log_if_needed()
                    return self._cache[key]
                self._misses += 1
                self._operation_count += 1
                self._log_if_needed()
                return None
        except Exception as e:
            # 缓存异常不影响主流程
            logger.error(f"[LRUCache] get异常: {e}")
            return None
    
    def set(self, key: str, value: Any):
        """设置缓存
        
        Args:
            key: 缓存key
            value: 缓存值
        """
        try:
            with self._lock:
                if key in self._cache:
                    self._cache.move_to_end(key)
                self._cache[key] = value
                if len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)
        except Exception as e:
            # 缓存异常不影响主流程
            logger.error(f"[LRUCache] set异常: {e}")
    
    def _log_if_needed(self):
        """根据间隔记录统计日志"""
        if self._operation_count % self._log_interval == 0:
            stats = self.get_stats()
            logger.info(f"[LRUCache] 统计: {stats}")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2%}"
        }
    
    def clear(self):
        """清空缓存"""
        try:
            with self._lock:
                self._cache.clear()
                self._hits = 0
                self._misses = 0
                self._operation_count = 0
        except Exception as e:
            logger.error(f"[LRUCache] clear异常: {e}")


def make_cache_key(data: Any) -> str:
    """生成缓存key
    
    Args:
        data: 要缓存的数据
        
    Returns:
        MD5哈希值作为缓存key
    """
    try:
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode()).hexdigest()
    except Exception as e:
        # 生成key失败时，使用默认key
        logger.error(f"[LRUCache] make_cache_key异常: {e}")
        return str(id(data))
