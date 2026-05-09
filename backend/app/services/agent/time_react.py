# -*- coding: utf-8 -*-
"""
TimeReactAgent - 时间工具 ReAct Agent

参考: 文档5.4节+7.3节完整代码

继承 BaseAgent，专用于时间操作场景的 ReAct 智能体。

【创建 2026-04-26 小沈】
【Phase 3验证 2026-04-26 小沈】

Author: 小沈 - 2026-04-26
【TimePrompts 2026-04-30 小沈】使用 TimePrompts 类替代硬编码 system_prompt
"""

# 必须先导入触发工具注册 - 导入整个模块
import app.services.tools.time.time_tools as _

from typing import Any, Optional, Dict

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.mixins.react_agent_mixin import ReactAgentMixin  # 【步骤5改用ReactAgentMixin】
from app.services.tools.registry import ToolCategory
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.llm_strategies import TextStrategy
from app.services.agent.llm_adapter import LLMAdapter
from app.services.prompts.time import TimePrompts
from app.utils.logger import logger


class TimeReactAgent(ReactAgentMixin, BaseAgent):
    """
    时间工具Agent - 按文档5.4+7.3实现
    """
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        candidates: Optional[list] = None,  # 【新增 2026-04-30 小沈】候选意图列表
        **kwargs
    ):
        """初始化 TimeReactAgent
        
        Args:
            llm_client: LLM 客户端
            task_id: 任务ID
            tool_category: 工具分类
            max_steps: 最大步数
            candidates: 候选意图列表，用于跨分类工具访问
        """
        effective_category = tool_category or ToolCategory.TIME
        
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # 【步骤7】使用ReactAgentMixin的任务追踪管理
        self._init_task_tracking(enable=True)
        
        self.prompts = TimePrompts()
        
        # 【修复 2026-04-30 小沈】使用 load_tools_by_category（原 _load_tools 改名），条件统一为 if self.tool_category
        if self.tool_category:
            self._tools_dict = self.load_tools_by_category(self.tool_category)
        
        self.executor = ToolExecutor(self._tools_dict)
        
        # FC通道由mixin._init_llm_strategies()统一初始化 - 小沈 2026-05-09
        self._init_llm_strategies()
        
        # 【新增 2026-04-30 小沈】存储候选意图列表
        self._candidates = candidates if candidates else []
        
        logger.info(f"TimeReactAgent initialized (task_id: {task_id}, tool_category: {effective_category}, tools: {len(self._tools_dict)}, candidates: {self._candidates})")
    
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt - 小沈2026-05-06改用Mixin动态方法"""
        return self._build_system_prompt("时间日期")
    
    def _get_task_prompt(self, task: str, context: Optional[Dict] = None) -> str:
        """获取任务 Prompt - 小沈2026-05-06统一走self.prompts"""
        return self.prompts.get_task_prompt(task)
    
    async def _get_llm_response(self) -> str:
        """获取LLM响应 - 小沈2026-05-06统一走Mixin的_call_llm_with_summary"""
        return await self._call_llm_with_summary()
    
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        return await self.executor.execute(action, params)
    
    async def rollback(self, step_number=None) -> bool:
        """时间操作无需回滚 - 小沈2026-05-06添加"""
        return True