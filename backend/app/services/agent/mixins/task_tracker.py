# -*- coding: utf-8 -*-
"""
TaskExecutionTracker - 任务执行追踪器

统一管理所有Agent的任务执行追踪。

- FileAgent: 追踪操作+统计+回滚（FileSafetyService + FileOperationSessionService）
- 其他Agent: 追踪执行统计（通用统计）

Author: 小健 - 2026-05-06
"""

from typing import Optional, Dict, Any
from app.utils.logger import logger


class TaskExecutionTracker:
    """
    任务执行追踪器（统一入口）
    
    根据 agent_id（意图类型）分发到对应的追踪服务：
    - file → FileOperationSessionService（操作追踪+统计+回滚）
    - 其他 → GenericTaskTracker（通用统计）
    """
    
    def __init__(self):
        self._trackers = {}  # {intent_type: tracker_instance}
        self._init_file_tracker()
        self._init_generic_tracker()
    
    def _init_file_tracker(self):
        """初始化file专用追踪器"""
        from app.services.agent.session import get_session_service
        self._trackers['file'] = get_session_service()
    
    def _init_generic_tracker(self):
        """初始化通用追踪器（非file意图使用）"""
        self._generic_tracker = GenericTaskTracker()
        for intent in ['time', 'shell', 'network', 'desktop', 'database', 
                       'system', 'document', 'code_execution']:
            self._trackers[intent] = self._generic_tracker
    
    def get_tracker(self, intent_type: str):
        """获取对应意图的追踪器"""
        return self._trackers.get(intent_type, self._generic_tracker)
    
    def create_task(self, task_id: str, agent_id: str, task_description: str):
        """
        创建任务追踪记录
        
        ⚠️ 修正-小沈 2026-05-06 14:37:45：
        FileOperationSessionService.create_session()不接受task_id参数，
        它自己生成sess-xxx。但safety用task_id记录操作。
        
        所以create_task只做统计记录，不应覆盖调用方的task_id。
        """
        tracker = self.get_tracker(agent_id)
        if tracker:
            try:
                tracker.create_session(agent_id=agent_id, task_description=task_description)
            except Exception as e:
                logger.warning(f"[TaskTracker] create_task失败: {e}")
    
    def complete_task(self, task_id: str, agent_id: str, success: bool = True):
        """完成任务追踪"""
        tracker = self.get_tracker(agent_id)
        if tracker:
            try:
                tracker.complete_session(task_id, success=success)
            except Exception as e:
                logger.error(f"[TaskTracker] complete_task失败: {e}")


class GenericTaskTracker:
    """
    通用任务追踪器（非file意图使用）
    
    只做轻量统计，不记录操作详情（无法回滚）。
    存储到内存dict（可选：后续扩展到SQLite）。
    """
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}  # {task_id: task_info}
    
    def create_session(self, agent_id: str, task_description: str) -> str:
        """创建任务记录（保持session命名，与FileOperationSessionService一致）"""
        from uuid import uuid4
        from datetime import datetime
        
        task_id = str(uuid4())
        self._tasks[task_id] = {
            "agent_id": agent_id,
            "task_description": task_description,
            "status": "running",
            "created_at": datetime.now().isoformat(),
        }
        logger.info(f"[GenericTaskTracker] 创建任务: {task_id}, agent={agent_id}")
        return task_id
    
    def complete_session(self, task_id: str, success: bool = True):
        """完成任务记录（保持session命名，与FileOperationSessionService一致）"""
        from datetime import datetime
        
        if task_id in self._tasks:
            self._tasks[task_id]["status"] = "completed" if success else "failed"
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()
            logger.info(f"[GenericTaskTracker] 完成任务: {task_id}, success={success}")


# 全局单例
_tracker_instance: Optional[TaskExecutionTracker] = None


def get_task_tracker() -> TaskExecutionTracker:
    """获取任务追踪器单例"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = TaskExecutionTracker()
    return _tracker_instance
