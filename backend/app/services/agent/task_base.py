# -*- coding: utf-8 -*-
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正
# 原则：绝不搞向后兼容，旧名必须彻底清除
"""
任务追踪服务基类 (Task Tracker Service Base)

【创建时间】2026-03-21 小沈
【重构说明】
根据架构设计文档 12.1.5.1 节，创建通用任务追踪服务基类。
未来其他意图（network、desktop、system、database）可继承此类实现自己的任务追踪服务。

当前 task 追踪服务（TaskOperationService）位于：
- agent/task_service.py

file 意图特有的统计字段位于：
- intents/definitions/file/file_stats.py

通用任务追踪服务接口定义：
- create_task: 创建任务
- complete_task: 完成任务
- get_task: 获取任务
- get_recent_tasks: 获取最近任务

Author: 小沈 - 2026-03-21
【更新】小沈 - 2026-05-06 session→task命名纠正
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4


class TaskServiceBase(ABC):
    """
    任务追踪服务基类 (抽象基类)
    
    定义通用任务追踪服务的接口，未来其他意图类型可继承此类。
    
    通用接口：
    - create_task: 创建新任务
    - complete_task: 完成任务
    - get_task: 获取任务信息
    - get_recent_tasks: 获取最近的任务列表
    
    各意图特有功能在子类中实现：
    - 意图: TaskOperationService (agent/task_service.py)
    """
    
    @abstractmethod
    def create_task(self, agent_id: str, task_description: str) -> str:
        """
        创建新的任务
        
        Args:
            agent_id: Agent标识符
            task_description: 任务描述
            
        Returns:
            task_id: 任务唯一标识符
        """
        pass
    
    @abstractmethod
    def complete_task(self, task_id: str, success: bool = True) -> None:
        """
        完成任务
        
        Args:
            task_id: 任务ID
            success: 是否成功完成
        """
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息字典，如果不存在返回 None
        """
        pass
    
    @abstractmethod
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的任务列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            任务记录列表
        """
        pass
    
    def _generate_task_id(self) -> str:
        """
        生成任务ID - 小沈-2026-05-06
        
        Returns:
            格式为 "task-{uuid}" 的任务ID
        """
        return f"task-{uuid4().hex}"
    
    def _get_current_timestamp(self) -> datetime:
        """
        获取当前时间戳
        
        Returns:
            当前 datetime 对象
        """
        return datetime.now()


class TaskStatsMixin:
    """
    任务统计混入类 - 小沈-2026-05-06 session→task命名纠正
    
    提供通用的任务统计功能。
    各意图特有的统计字段通过子类扩展。
    """
    
    def __init__(self):
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
    
    def get_task_stats(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务统计信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            统计信息字典
        """
        return self._stats_cache.get(task_id)
    
    def update_task_stats(
        self, 
        task_id: str, 
        total_operations: int = 0,
        success_count: int = 0,
        failed_count: int = 0
    ) -> None:
        """
        更新任务统计信息
        
        Args:
            task_id: 任务ID
            total_operations: 总操作数
            success_count: 成功数
            failed_count: 失败数
        """
        self._stats_cache[task_id] = {
            "task_id": task_id,
            "total_operations": total_operations,
            "success_count": success_count,
            "failed_count": failed_count,
            "updated_at": datetime.now()
        }
    

__all__ = [
    "TaskServiceBase",
    "TaskStatsMixin",
]
