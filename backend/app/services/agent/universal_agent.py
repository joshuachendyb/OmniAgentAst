# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-08 清理空壳
"""
from typing import Any, List, Optional, Dict

from app.services.agent.core_agent import BaseAgent
from app.services.agent.agent_config import AgentConfig
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class UniversalAgent(BaseAgent):
    """配置驱动的通用 Agent"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: Optional[AgentConfig] = None,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            intent_type = config.intent_type if config else "unknown"
            raise ValueError(f"task_id is required for {intent_type} operation tracking")

        effective_category = tool_category or (config.category if config else None)
        if max_steps is None:
            if config and config.max_steps:
                effective_max_steps = config.max_steps
            else:
                from app.config import get_config
                effective_max_steps = get_config().get_max_steps()
        else:
            effective_max_steps = max_steps
        rollback_enabled = config.rollback_enabled if config else True

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=effective_max_steps,
            rollback_enabled=rollback_enabled,
            candidates=candidates,
            **kwargs
        )

        if config:
            self.config = config
            self.prompts = config.prompt_class()
            logger.info(
                f"UniversalAgent initialized (intent={config.intent_type}, task_id={task_id}, category={effective_category})"
            )
        else:
            logger.info(
                f"UniversalAgent initialized (task_id={task_id}, category={effective_category})"
            )

    def _get_system_prompt(self) -> str:
        if hasattr(self, 'config') and self.config:
            return f"System: {self.config.category_display_name}"
        return "System: 通用助手"

    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.prompts.get_task_prompt(task)
