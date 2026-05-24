# -*- coding: utf-8 -*-
"""
回滚能力 Mixin — 从 FileReactAgent 提取的可插拔回滚能力

Author: 小强 - 2026-05-23
"""
from typing import Dict, Any, Optional

from app.utils.logger import logger


class RollbackMixin:
    """可插拔的回滚能力"""
    
    async def rollback(self, step_number: Optional[int] = None) -> bool:
        """
        回滚操作
        
        Args:
            step_number: 要回滚到的步骤号（None 表示回滚所有）
            
        Returns:
            是否成功
        """
        try:
            if not self.task_id:
                raise ValueError("Session ID is required for rollback")
            
            if step_number is None:
                result = await self.executor.execute('rollback_session', {'task_id': self.task_id})
                success = result.get("status") == "success"
            else:
                steps_to_rollback = [s for s in self.steps if s.step_number > step_number]
                
                if not steps_to_rollback:
                    return False
                
                success = True
                for step in sorted(steps_to_rollback, key=lambda s: s.step_number, reverse=True):
                    observation = step.observation or {}
                    result_data = observation.get("result", {}) if isinstance(observation, dict) else {}
                    operation_id = result_data.get("operation_id")
                    if operation_id:
                        step_result = await self.executor.execute('rollback_operation', {'operation_id': operation_id})
                        step_success = step_result.get("status") == "success" if isinstance(step_result, dict) else bool(step_result)
                        success = success and step_success
                    else:
                        raise ValueError(f"No operation_id found for step {step.step_number}")
            
            from app.services.agent.types import AgentStatus
            self.status = AgentStatus.ROLLED_BACK
            return success
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
