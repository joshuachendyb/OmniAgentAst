# -*- coding: utf-8 -*-
"""
会话服务基类 (Session Service Base)

【创建时间】2026-03-21 小沈
【重构说明】
根据架构设计文档 12.1.5.1 节，创建通用会话服务基类。
未来其他意图（network、desktop、system、database）可继承此类实现自己的会话服务。

当前 file 意图的会话服务（FileOperationSessionService）位于：
- agent/session.py

file 意图特有的统计字段位于：
- intents/definitions/file/file_stats.py

通用会话服务接口定义：
- create_session: 创建会话
- complete_session: 完成会话
- get_session: 获取会话
- get_recent_sessions: 获取最近会话

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4


class SessionServiceBase(ABC):
    """
    会话服务基类 (抽象基类)
    
    定义通用会话服务的接口，未来其他意图类型可继承此类。
    
    通用接口：
    - create_session: 创建新会话
    - complete_session: 完成会话
    - get_session: 获取会话信息
    - get_recent_sessions: 获取最近的会话列表
    
    各意图特有功能在子类中实现：
    - file 意图: FileOperationSessionService (agent/session.py)
    """
    
    @abstractmethod
    def create_session(self, agent_id: str, task_description: str) -> str:
        """
        创建新的会话
        
        Args:
            agent_id: Agent标识符
            task_description: 任务描述
            
        Returns:
            session_id: 会话唯一标识符
        """
        pass
    
    @abstractmethod
    def complete_session(self, session_id: str, success: bool = True) -> None:
        """
        完成会话
        
        Args:
            session_id: 会话ID
            success: 是否成功完成
        """
        pass
    
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话信息字典，如果不存在返回 None
        """
        pass
    
    @abstractmethod
    def get_recent_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的会话列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            会话记录列表
        """
        pass
    
    def _generate_session_id(self) -> str:
        """
        生成会话ID
        
        Returns:
            格式为 "sess-{uuid}" 的会话ID
        """
        return f"sess-{uuid4().hex}"
    
    def _get_current_timestamp(self) -> datetime:
        """
        获取当前时间戳
        
        Returns:
            当前 datetime 对象
        """
        return datetime.now()


class SessionStatsMixin:
    """
    会话统计混入类
    
    提供通用的会话统计功能。
    各意图特有的统计字段通过子类扩展。
    """
    
    def __init__(self):
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        获取会话统计信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            统计信息字典
        """
        return self._stats_cache.get(session_id)
    
    def update_session_stats(
        self, 
        session_id: str, 
        total_operations: int = 0,
        success_count: int = 0,
        failed_count: int = 0
    ) -> None:
        """
        更新会话统计信息
        
        Args:
            session_id: 会话ID
            total_operations: 总操作数
            success_count: 成功数
            failed_count: 失败数
        """
        self._stats_cache[session_id] = {
            "session_id": session_id,
            "total_operations": total_operations,
            "success_count": success_count,
            "failed_count": failed_count,
            "updated_at": datetime.now()
        }
    
    def clear_stats_cache(self) -> None:
        """清空统计缓存"""
        self._stats_cache.clear()


__all__ = [
    "SessionServiceBase",
    "SessionStatsMixin",
]
