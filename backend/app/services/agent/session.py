# -*- coding: utf-8 -*-
"""
文件操作会话管理服务 (File Operation Session Service)

【创建时间】2026-03-20
【重构时间】2026-03-21 小沈
【设计依据】多意图处理架构设计-小沈-2026-03-20.md (v2.18) - 12.1.5.1节
【重构说明】
  - 继承自 SessionServiceBase（通用会话服务基类）
  - file专用统计使用 FileSessionStats（位于 intents/definitions/file/file_stats.py）

Author: 小沈 - 2026-03-21
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

# 【小沈重构 2026-05-22】数据库配置迁移至 app/db/
from app.db.models.operation_models import SessionRecord
from app.db.models.operation_enums import OperationStatus
from app.db.operations_db import get_connection as get_operations_connection
from app.utils.logger import logger
from app.services.agent.session_base import SessionServiceBase, SessionStatsMixin
from app.services.intents.definitions.file.file_stats import FileSessionStats


class FileOperationSessionService(SessionServiceBase, SessionStatsMixin):
    """
    文件操作会话管理服务
    
    继承自 SessionServiceBase，实现文件操作特有的会话管理。
    file专用统计字段使用 FileSessionStats。
    
    功能：
    1. 创建和管理会话
    2. 更新会话状态和统计
    3. 生成会话报告
    """
    
    def __init__(self):
        # 【小沈重构 2026-05-22】数据库初始化已由 app.db.operations_db 模块级处理
        # 不再需要 FileSafetyConfig 和 _init_db
        pass
    
    def _init_db(self):
        """初始化数据库（建表已由app.db.operations_db模块级处理）"""
        # 建表已由 app.db.operations_db 模块级 init_database() 统一处理
        # 此处无需任何操作
        pass
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return get_operations_connection()
    
    def create_task(self, agent_id: str, task_description: str) -> str:
        """
        创建新的文件操作任务
        
        Args:
            agent_id: Agent标识符
            task_description: 任务描述
            
        Returns:
            task_id: 任务唯一标识符
        """
        task_id = f"task-{self._generate_task_id()}"
        
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO file_operation_sessions 
                (task_id, agent_id, task_description, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                task_id, agent_id, task_description, 
                OperationStatus.PENDING.value, datetime.now()
            ))
            
            conn.commit()
            
            logger.info(f"Session created: {task_id} - {task_description}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
            
        finally:
            if conn:
                conn.close()
    
    def complete_task(self, task_id: str, success: bool = True):
        """
        完成任务
        
        Args:
            task_id: 任务ID
            success: 是否成功完成
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE file_operation_sessions 
                SET status = ?, completed_at = ?
                WHERE task_id = ?
            ''', (
                OperationStatus.COMPLETED.value if success else OperationStatus.FAILED.value,
                datetime.now(),
                task_id
            ))
            
            conn.commit()
            logger.info(f"Session completed: {task_id} (success={success})")
            
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
            raise
            
        finally:
            if conn:
                conn.close()
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息 - 小沈-2026-05-06"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM file_operation_sessions WHERE task_id = ?
            ''', (task_id,))
            
            row = cursor.fetchone()
            if row is None:
                return None
            
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
            
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None
            
        finally:
            if conn:
                conn.close()
    
    def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的任务列表 - 小沈-2026-05-06"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM file_operation_sessions 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            tasks = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return tasks
            
        except Exception as e:
            logger.error(f"Failed to get recent tasks: {e}")
            return []
            
        finally:
            if conn:
                conn.close()


_task_tracker_instance: Optional[FileOperationSessionService] = None


def get_task_tracker() -> FileOperationSessionService:
    """获取会话服务单例"""
    global _task_tracker_instance
    if _task_tracker_instance is None:
        _task_tracker_instance = FileOperationSessionService()
    return _task_tracker_instance


get_session_service = get_task_tracker
