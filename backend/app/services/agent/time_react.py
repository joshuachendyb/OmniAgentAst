# -*- coding: utf-8 -*-
"""
TimeReactAgent - 时间工具 ReAct Agent

参考: 文档5.4节+7.3节完整代码

继承 BaseAgent，专用于时间操作场景的 ReAct 智能体。

【创建 2026-04-26 小沈】
【Phase 3验证 2026-04-26 小沈】

Author: 小沈 - 2026-04-26
"""

# 必须先导入触发工具注册 - 导入整个模块
import app.services.tools.time.time_tools as _

from typing import Any, Optional, Dict

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.llm_strategies import TextStrategy
from app.utils.logger import logger


class TimeReactAgent(ToolLoaderMixin, BaseAgent):
    """
    时间工具Agent - 按文档5.4+7.3实现
    """
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        **kwargs
    ):
        """初始化 TimeReactAgent"""
        effective_category = tool_category or ToolCategory.TIME
        
        import app.services.tools.time.time_tools as time_tools_register
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        self.system_prompt = "你是一个时间工具助手，可以回答时间相关的问题。"
        
        if self.tool_category == ToolCategory.TIME:
            self._tools_dict = ToolLoaderMixin._load_tools(self, ToolCategory.TIME)
        
        self.executor = ToolExecutor(self._tools_dict)
        
        self.text_strategy = TextStrategy()
        
        logger.info(f"TimeReactAgent initialized (task_id: {task_id}, tool_category: {effective_category}, tools: {len(self._tools_dict)})")
    
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        return self.system_prompt
    
    def _get_task_prompt(self, task: str, context: Optional[Dict] = None) -> str:
        """获取任务 Prompt"""
        return task
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        self.llm_call_count += 1
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            response = await self.text_strategy.call(
                llm_client=self.llm_client,
                message=last_message,
                history_dicts=history_dicts,
                conversation_history=self.conversation_history
            )
            return response
        except Exception as e:
            logger.error(f"TimeReactAgent LLM error: {e}")
            raise
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        return await self.executor.execute(action, params)