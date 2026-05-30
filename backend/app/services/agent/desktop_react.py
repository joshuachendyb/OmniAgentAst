# -*- coding: utf-8 -*-
"""
DesktopReactAgent - 桌面操作 ReAct Agent。

继承层级：
  BaseAgent → GenericReactAgent → UniversalReactAgent → DesktopReactAgent

Author: 小健 - 2026-05-06（修正-小沈 2026-05-06：rollback返回False）
"""
from typing import Any, Optional, Dict, List

from app.services.agent.universal_react import UniversalReactAgent
from app.constants import DEFAULT_MAX_STEPS
from app.services.prompts.desktop.desktop_prompts import DesktopPrompts
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class DesktopReactAgent(UniversalReactAgent):
    """桌面操作 ReAct Agent — 第三层：加桌面专用prompts"""
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            raise ValueError("task_id is required for desktop operation tracking")
        
        effective_category = tool_category or ToolCategory.DESKTOP
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            config=None,
            tool_category=effective_category,
            max_steps=max_steps,
            candidates=candidates,
            **kwargs
        )
        
        # Desktop专用prompts
        self.prompts = DesktopPrompts()
        
        logger.info(f"DesktopReactAgent initialized (task_id: {task_id}, category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        return self._build_system_prompt("桌面操作")
    
    def _get_task_prompt(self, task: str, context=None) -> str:
        return self.prompts.get_task_prompt(task)
