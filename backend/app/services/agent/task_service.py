# -*- coding: utf-8 -*-
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正
# 原则：绝不搞向后兼容，旧名必须彻底清除
"""
任务操作服务 (Task Operation Service)
 
【创建时间】2026-03-20
【重构时间】2026-03-21 小沈
【设计依据】多意图处理架构设计-小沈-2026-03-20.md (v2.18) - 12.1.5.1节
【重构说明】
  - 继承自 TaskServiceBase
  - file专用统计使用 FileSessionStats（位于 intents/definitions/file/file_stats.py）

Author: 小沈 - 2026-03-21
"""

from datetime import datetime
from typing import Optional, List, Dict, Any

from app.db import db
from app.db.models.operation_models import TaskRecord
from app.db.models.operation_enums import OperationStatus
from app.utils.logger import logger
from app.services.agent.task_base import TaskServiceBase, TaskStatsMixin
from app.services.intents.definitions.file.file_stats import FileSessionStats


class TaskOperationService(TaskServiceBase, TaskStatsMixin):
    """
    任务操作服务
    
    继承自 TaskServiceBase，实现任务操作服务。
    file专用统计字段使用 FileSessionStats。
    
    功能：
    1. 创建和管理会话
    2. 更新会话状态和统计
    3. 生成会话报告
    """
    
    def __init__(self):
        pass
    
    def create_task(self, agent_id: str, task_description: str) -> str:
        """
        创建新的文件操作任务
        
        Args:
            agent_id: Agent标识符
            task_description: 任务描述
            
        Returns:
            task_id: 任务唯一标识符
        """
        task_id = self._generate_task_id()
        
        try:
            with db.get_conn("operations") as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO task_operations 
                    (task_id, agent_id, task_description, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    task_id, agent_id, task_description, 
                    OperationStatus.PENDING.value, datetime.now()
                ))
            
            logger.info(f"Task created: {task_id} - {task_description}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    def complete_task(self, task_id: str, success: bool = True):
        """
        完成任务
        
        Args:
            task_id: 任务ID
            success: 是否成功完成
        """
        try:
            with db.get_conn("operations") as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE task_operations 
                    SET status = ?, completed_at = ?
                    WHERE task_id = ?
                ''', (
                    OperationStatus.COMPLETED.value if success else OperationStatus.FAILED.value,
                    datetime.now(),
                    task_id
                ))
            
            logger.info(f"Task completed: {task_id} (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            raise
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息 - 小沈-2026-05-06"""
        try:
            with db.get_conn("operations") as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM task_operations WHERE task_id = ?
                ''', (task_id,))
                
                row = cursor.fetchone()
                if row is None:
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None
    
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务列表 - 小沈-2026-05-06"""
        try:
            with db.get_conn("operations") as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM task_operations 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                columns = [desc[0] for desc in cursor.description]
                tasks = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get recent tasks: {e}")
            return []


_task_tracker_instance: Optional[TaskOperationService] = None


def get_task_service() -> TaskOperationService:
    """获取任务服务单例"""
    global _task_tracker_instance
    if _task_tracker_instance is None:
        _task_tracker_instance = TaskOperationService()
    return _task_tracker_instance
