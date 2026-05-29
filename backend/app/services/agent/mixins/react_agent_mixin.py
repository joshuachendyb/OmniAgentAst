# -*- coding: utf-8 -*-
"""
ReactAgentMixin - ReAct Agent 公用逻辑混入类

提取FileReactAgent/TimeReactAgent的重复逻辑，
供新增的ShellReactAgent/NetworkReactAgent等复用。

Author: 小健 - 2026-05-06
Updated: 小沈 - 2026-05-12 (合并file_react独有逻辑: prompt_logger+temp_history+use_function_calling)
Updated: 小沈 - 2026-05-29 (拆分为3个子Mixin + 组合入口)
"""
from typing import List, Optional

from app.services.agent.mixins.tool_init_mixin import ToolInitMixin
from app.services.agent.mixins.llm_dispatch_mixin import LLMDispatchMixin
from app.services.agent.mixins.prompt_build_mixin import PromptBuildMixin
from app.utils.logger import logger


class ReactAgentMixin(ToolInitMixin, LLMDispatchMixin, PromptBuildMixin):
    """
    ReAct Agent 公用逻辑混入类（组合入口）
    
    继承3个职责子Mixin：
    - ToolInitMixin: 工具加载职责（_init_tools_and_executor, _get_tools_summary, _get_tools_detail）
    - LLMDispatchMixin: LLM调用+策略分发（_init_llm_strategies, _call_llm, _dispatch_strategy）
    - PromptBuildMixin: Prompt构建+日志（_inject_tools_hint, _inject_schema, _build_system_prompt, _log_prompt, _log_response）
    
    使用方式：
        class ShellReactAgent(ReactAgentMixin, BaseAgent):
            def __init__(self, ...):
                super().__init__(...)
                self._init_tools_and_executor(tool_category)
                self._init_llm_strategies()
                self._init_task_tracking()
    """
    
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
        
        from app.services.task import get_tracker
        self._task_tracker = get_tracker()
        self._task_created_by_agent = False
    
    def _init_candidates(self, candidates: Optional[List[str]] = None):
        """初始化候选意图列表"""
        self._candidates = candidates if candidates else []
    
    # ===== 任务追踪管理 =====
