# -*- coding: utf-8 -*-
"""
ReactAgentMixin - ReAct Agent 公用逻辑混入类

提取FileReactAgent/TimeReactAgent的重复逻辑，
供新增的ShellReactAgent/NetworkReactAgent等复用。

Author: 小健 - 2026-05-06
"""
from typing import Dict, Any, List, Optional, Tuple
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy, ResponseFormatStrategy
from app.services.agent.llm_adapter import LLMAdapter
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class ReactAgentMixin(ToolLoaderMixin):
    """
    ReAct Agent 公用逻辑混入类
    
    使用方式：
        class ShellReactAgent(ReactAgentMixin, BaseAgent):
            def __init__(self, ...):
                super().__init__(...)
                self._init_tools_and_executor(tool_category)
                self._init_llm_strategies()
                self._init_task_tracking()
    """
    
    def _init_tools_and_executor(self, tool_category: Optional[ToolCategory] = None):
        """初始化工具加载和执行器"""
        if tool_category:
            self._tools_dict = self.load_tools_by_category(tool_category)
        else:
            self._tools_dict = {}
        self.executor = ToolExecutor(self._tools_dict)
        logger.info(f"[{self.__class__.__name__}] 加载工具: {len(self._tools_dict)}个")
    
    def _init_llm_strategies(self):
        """初始化LLM调用策略"""
        self.text_strategy = TextStrategy()
        self.adapter = None
        self.use_function_calling = False
        self.openai_tools = []
        self.tools_strategy = None
        self.response_format_strategy = None
    
    def _init_task_tracking(self, enable: bool = True):
        """
        初始化任务执行追踪
        
        替代原来的_init_session()，明确语义：任务追踪（使用_init_task_tracking()）
        - task_id = 任务执行实例ID（一次Agent.run()的生命周期）
        - tracker = 按意图类型分发的追踪服务
        
        Args:
            enable: 是否启用追踪（默认True）
                - FileReactAgent: True（需要追踪写操作）
                - TimeReactAgent: True（统一接口）
                - ShellReactAgent: True（追踪命令执行）
                - 如需自定义追踪逻辑，设为False后自己实现
        """
        if not enable:
            self._task_tracker = None
            self._task_created_by_agent = False
            return
        
        from app.services.agent.mixins.task_tracker import get_task_tracker
        self._task_tracker = get_task_tracker()
        self._task_created_by_agent = False
    
    def _init_candidates(self, candidates: Optional[List[str]] = None):
        """初始化候选意图列表"""
        self._candidates = candidates if candidates else []
    
    # ===== 跨分类工具支持 =====
    
    def _get_tools_summary(self) -> str:
        """获取跨分类工具概要（每轮实时生成）"""
        from app.services.tools.registry import tool_registry
        return tool_registry.get_all_tools_summary(
            priority_category=self.tool_category or ToolCategory.FILE
        )
    
    def _build_candidates_hint(self) -> str:
        """构建候选意图提示"""
        if not self._candidates:
            return ""
        candidates_list = ", ".join(self._candidates)
        return (
            f"\n\n【候选意图】已识别出以下可能的意图类别: {candidates_list}。"
            "你可以根据实际任务需要，访问任意候选分类的工具。"
        )
    
    def _build_cross_tool_hint(self, category_name: str) -> str:
        """构建跨分类工具提示"""
        return (
            f"\n\n【注意】除了{category_name}工具，你还可以使用其他分类的工具。"
            "根据任务需要自由选择合适的工具，不受初始分类限制。"
        )
    
    def _build_system_prompt(self, category_name: str) -> str:
        """构建完整system prompt（base + candidates + cross）"""
        if hasattr(self, '_custom_system_prompt') and self._custom_system_prompt:
            return self._custom_system_prompt
        base = self.prompts.get_system_prompt()
        return base + self._build_candidates_hint() + self._build_cross_tool_hint(category_name)
    
    # ===== LLM调用 =====
    
    async def _call_llm_with_summary(self) -> str:
        """LLM调用统一入口（含工具概要注入+adapter策略选择）"""
        self.llm_call_count += 1
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        last_message = self.conversation_history[-1]["content"]
        history_dicts = self.conversation_history[:-1]
        
        # 注入工具概要
        try:
            tools_summary = self._get_tools_summary()
            summary_msg = {"role": "system", "content": f"【当前可用工具列表】\n{tools_summary}"}
            history_dicts = list(history_dicts) + [summary_msg]
        except Exception as e:
            logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
        
        # adapter策略选择
        if self.adapter:
            strategy = await self.adapter.ensure_capability()
            if strategy.method == "response_format" and self.response_format_strategy:
                return await self.response_format_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
            elif strategy.method == "tools" and self.tools_strategy:
                return await self.tools_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
        
        # 默认文本模式
        return await self.text_strategy.call(
            llm_client=self.llm_client, message=last_message,
            history_dicts=history_dicts, conversation_history=self.conversation_history)
    
    # ===== 任务追踪管理 =====
    
    def _on_task_init(self, task: str, context=None):
        """任务开始追踪Hook"""
        from app.services.agent.mixins.task_tracker import get_task_tracker
        if not self.task_id:
            # task_id为空时才需要创建
            from uuid import uuid4
            self.task_id = str(uuid4())
            self._task_created_by_agent = True
        
        # 创建追踪记录
        if self._task_tracker:
            agent_id = self.__class__.__name__.replace('ReactAgent', '').lower()
            self._task_tracker.create_task(
                task_id=self.task_id,
                agent_id=agent_id,
                task_description=task
            )
    
    def _on_task_complete(self):
        """任务结束追踪Hook"""
        if self._task_created_by_agent and self.task_id and self._task_tracker:
            try:
                agent_id = self.__class__.__name__.replace('ReactAgent', '').lower()
                self._task_tracker.complete_task(self.task_id, agent_id=agent_id, success=True)
                self._task_created_by_agent = False
            except Exception as e:
                logger.error(f"Failed to complete task tracking: {e}")
