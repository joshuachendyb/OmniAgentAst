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
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.llm_strategies import TextStrategy
from app.services.agent.llm_adapter import LLMAdapter  # 【修复 2026-04-30 小沈】添加LLMAdapter导入
from app.services.prompts.time import TimePrompts
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
        
        self.prompts = TimePrompts()
        
        # 【修复 2026-04-30 小沈】使用 load_tools_by_category（原 _load_tools 改名），条件统一为 if self.tool_category
        if self.tool_category:
            self._tools_dict = self.load_tools_by_category(self.tool_category)
        
        self.executor = ToolExecutor(self._tools_dict)
        
        self.text_strategy = TextStrategy()
        
        # 【修复 2026-04-30 小沈】添加 LLMAdapter 自适应策略（与 FileReactAgent 对齐）
        # adapter 默认 None，需外部注入才生效，不改变现有行为
        self.adapter = None
        self.use_function_calling = False
        self.openai_tools = []
        self.tools_strategy = None
        self.response_format_strategy = None
        
        # 【新增 2026-04-30 小沈】存储候选意图列表
        self._candidates = candidates if candidates else []
        
        logger.info(f"TimeReactAgent initialized (task_id: {task_id}, tool_category: {effective_category}, tools: {len(self._tools_dict)}, candidates: {self._candidates})")
    
    # ========== 跨分类工具支持方法（2026-04-30 小沈）==========
    
    def _get_tools_summary(self) -> str:
        """
        获取跨分类工具概要（每轮实时生成，确保动态注册的工具被包含）

        设计文档 v1.5 4.2节

        Returns:
            格式化的工具概要字符串
        """
        from app.services.tools.registry import tool_registry
        return tool_registry.get_all_tools_summary(
            priority_category=ToolCategory.TIME
        )
    
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt（含跨工具提示 + 候选意图）"""
        base = self.prompts.get_system_prompt()
        candidates_hint = ""
        if self._candidates:
            candidates_list = ", ".join(self._candidates)
            candidates_hint = (
                f"\n\n【候选意图】已识别出以下可能的意图类别: {candidates_list}。"
                "你可以根据实际任务需要，访问任意候选分类的工具。"
            )
        cross_tool_hint = (
            "\n\n【注意】除了时间日期工具，你还可以使用其他分类的工具。"
            "例如：需要操作文件时可以用 read_file/write_file，"
            "需要执行命令时可以用 execute_command 等。"
            "根据任务需要自由选择合适的工具。"
        )
        return base + candidates_hint + cross_tool_hint
    
    def _get_task_prompt(self, task: str, context: Optional[Dict] = None) -> str:
        """获取任务 Prompt"""
        return task
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应（支持 LLMAdapter 自适应策略）
        
        【修复 2026-04-30 小沈】添加 adapter 策略选择，与 FileReactAgent 对齐。
        当 adapter 未注入时（默认None），行为与修改前完全一致（使用 TextStrategy）。
        """
        self.llm_call_count += 1
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            # 【修复 2026-04-30 小沈】工具概要改为独立system消息插入history
            # 避免追加到 Observation 末尾导致语义混乱
            try:
                tools_summary = self._get_tools_summary()
                summary_msg = {"role": "system", "content": f"【当前可用工具列表】\n{tools_summary}"}
                history_dicts = list(history_dicts) + [summary_msg]
            except Exception as e:
                logger.warning(f"[ToolSummary] TimeAgent注入工具概要失败: {e}")
            
            # 【修复 2026-04-30 小沈】自适应策略选择（与 FileReactAgent 对齐）
            if self.adapter:
                strategy = await self.adapter.ensure_capability()
                logger.info(f"[TimeAgent] Using method: {strategy.method}")
                
                if strategy.method == "response_format" and self.response_format_strategy:
                    response = await self.response_format_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
                elif strategy.method == "tools" and self.tools_strategy:
                    response = await self.tools_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
                else:
                    response = await self.text_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
            else:
                # 无 adapter 时，使用普通文本模式（与修改前行为一致）
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