"""
文件操作会话管理服务 (File Operation Session Service)
管理文件操作会话的生命周期和统计信息
"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

from app.models.file_operations import SessionRecord, OperationStatus
from app.utils.logger import logger


class FileOperationSessionService:
    """
    文件操作会话管理服务
    
    功能：
    1. 创建和管理会话
    2. 更新会话状态和统计
    3. 生成会话报告
    """
    
    def __init__(self):
        # 【修复-波次4】使用延迟导入避免循环导入风险
        # FileSafetyConfig 只在方法内部使用，不在模块级别导入
        from app.services.file_operations.safety import FileSafetyConfig
        self.config = FileSafetyConfig()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.config.DB_PATH))
    
    def create_session(self, agent_id: str, task_description: str) -> str:
        """
        创建新的文件操作会话
        
        Args:
            agent_id: Agent标识符
            task_description: 任务描述
            
        Returns:
            session_id: 会话唯一标识符
        """
        session_id = f"sess-{uuid4().hex}"
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO file_operation_sessions 
                (session_id, agent_id, task_description, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                session_id, agent_id, task_description, 
                OperationStatus.PENDING.value, datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Session created: {session_id} - {task_description}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    def complete_session(self, session_id: str, success: bool = True):
        """
        完成会话
        
        Args:
            session_id: 会话ID
            success: 是否成功完成
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 统计操作结果
            cursor.execute('''
                SELECT COUNT(*), 
                       SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)
                FROM file_operations WHERE session_id = ?
            ''', (session_id,))
            
            total, success_count, failed_count = cursor.fetchone()
            total = total or 0
            success_count = success_count or 0
            failed_count = failed_count or 0
            
            # 更新会话状态
            status = OperationStatus.SUCCESS.value if success and failed_count == 0 else \
                     OperationStatus.FAILED.value if failed_count > 0 else \
                     OperationStatus.SUCCESS.value
            
            cursor.execute('''
                UPDATE file_operation_sessions 
                SET status = ?, total_operations = ?, success_count = ?, 
                    failed_count = ?, completed_at = ?
                WHERE session_id = ?
            ''', (status, total, success_count, failed_count, datetime.now(), session_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Session completed: {session_id} - {success_count}/{total} succeeded")
            
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
    
    def get_session(self, session_id: str) -> Optional[SessionRecord]:
        """
        获取会话信息
        
        Args:
            session_id: 会话ID
            
        Returns:
            SessionRecord或None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM file_operation_sessions WHERE session_id = ?
            ''', (session_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return SessionRecord(
                    id=row[0],
                    session_id=row[1],
                    agent_id=row[2],
                    task_description=row[3],
                    status=OperationStatus(row[4]),
                    total_operations=row[5],
                    success_count=row[6],
                    failed_count=row[7],
                    rolled_back_count=row[8],
                    report_generated=bool(row[9]),
                    report_path=row[10],
                    created_at=row[11],
                    completed_at=row[12]
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None
    
    def get_recent_sessions(self, limit: int = 10) -> list:
        """
        获取最近的会话列表
        
        Args:
            limit: 返回数量限制
            
        Returns:
            会话记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM file_operation_sessions 
                ORDER BY created_at DESC LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            sessions = []
            for row in rows:
                sessions.append(SessionRecord(
                    id=row[0],
                    session_id=row[1],
                    agent_id=row[2],
                    task_description=row[3],
                    status=OperationStatus(row[4]),
                    total_operations=row[5],
                    success_count=row[6],
                    failed_count=row[7],
                    rolled_back_count=row[8],
                    report_generated=bool(row[9]),
                    report_path=row[10],
                    created_at=row[11],
                    completed_at=row[12]
                ))
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []


# 单例模式
_session_service_instance: Optional[FileOperationSessionService] = None


def get_session_service() -> FileOperationSessionService:
    """获取会话服务单例"""
    global _session_service_instance
    if _session_service_instance is None:
        _session_service_instance = FileOperationSessionService()
    return _session_service_instance
