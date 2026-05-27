# -*- coding: utf-8 -*-
"""
ReactAgentMixin - ReAct Agent 公用逻辑混入类

提取FileReactAgent/TimeReactAgent的重复逻辑，
供新增的ShellReactAgent/NetworkReactAgent等复用。

Author: 小健 - 2026-05-06
Updated: 小沈 - 2026-05-12 (合并file_react独有逻辑: prompt_logger+temp_history+use_function_calling)
"""
from typing import Dict, Any, List, Optional, Tuple
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy
from app.services.agent.llm_adapter import LLMAdapter
from app.services.agent.strategy_manager import LLMStrategyManager
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.prompts.prompt_assembler import PromptAssembler


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
        """初始化工具加载和执行器 - 小沈 2026-05-10"""
        if tool_category:
            self._tools_dict = self.load_tools_by_category(tool_category)
        else:
            self._tools_dict = {}
        self.executor = ToolExecutor(self._tools_dict)
        logger.info(f"[{self.__class__.__name__}] 加载工具: {len(self._tools_dict)}个")
    
    def _init_llm_strategies(self):
        """初始化LLM调用策略 - 小健 2026-05-23

        创建策略对象和adapter，策略在首次LLM调用时懒确定并缓存。
        【2026-05-27 小沈】使用策略管理器统一管理策略生命周期
        """
        self.text_strategy = TextStrategy()
        self.adapter = LLMAdapter(self)
        self.strategy_manager = LLMStrategyManager(self.adapter)

        _cls = self.__class__.__name__
        _has_client = self.llm_client is not None
        _self_api_base = getattr(self, 'api_base', None) or (getattr(self.llm_client, 'api_base', None) if _has_client else None)
        _self_api_key = getattr(self, 'api_key', None) or (getattr(self.llm_client, 'api_key', None) if _has_client else None)
        _self_model = getattr(self, 'model', None) or (getattr(self.llm_client, 'model', None) if _has_client else None)
        logger.info(
            f"[{_cls}] _init_llm_strategies: llm_client={_has_client}, "
            f"api_base={_self_api_base}, model={_self_model}"
        )

        try:
            from app.services.tools.registry import tool_registry

            if self.llm_client and _self_api_base:
                self.adapter = LLMAdapter(
                    api_base=_self_api_base,
                    api_key=_self_api_key,
                    model=_self_model,
                )

                openai_tools = tool_registry.to_openai_tools(self.tool_category)
                self.tools_strategy = ToolsStrategy(tools=openai_tools)
                self.use_function_calling = True
                self.openai_tools = openai_tools
                logger.info(f"[{_cls}] _init_llm_strategies 成功: tools={len(openai_tools)}, use_function_calling=True, 策略待首次调用确定")
            else:
                self.adapter = None
                self.tools_strategy = None
                self.use_function_calling = False
                self.openai_tools = []
                self._strategy = "text"
                _reason = "llm_client is None" if not self.llm_client else "api_base为空"
                logger.warning(f"[{_cls}] _init_llm_strategies 跳过adapter({_reason}): 直接text模式")
        except Exception as e:
            logger.warning(f"[{_cls}] LLM策略初始化失败，降级到文本模式: {e}")
            self.adapter = None
            self.tools_strategy = None
            self.use_function_calling = False
            self.openai_tools = []
            self._strategy = "text"

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
    
    def _get_tools_summary(self, exclude_categories: Optional[set] = None) -> str:
        """获取跨分类工具概要（每轮实时生成） - 小健 2026-05-14

        Args:
            exclude_categories: 排除的分类集合（避免与detail重复）
        """
        from app.services.tools.registry import tool_registry
        return tool_registry.get_all_tools_summary(
            priority_category=self.tool_category or ToolCategory.FILE,
            exclude_categories=exclude_categories
        )
    
    def _get_tools_detail(self) -> str:
        """获取已加载分类工具的完整描述 - 小健 2026-05-14
        
        【重构 小健 2026-05-15】registry返回的单分类detail已自带"=== 分类名 ==="标题，
        此处只做多分类拼接，不再生成额外标题。
        【2026-05-18 小沈】使用resolve_category支持新旧分类名
        """
        from app.services.tools.registry import tool_registry, resolve_category
        parts = []
        loaded_cats = getattr(self, '_loaded_categories', set())
        for cat_name in sorted(loaded_cats):
            category = resolve_category(cat_name)
            if not category:
                continue
            try:
                detail = tool_registry.get_all_tools_detail(
                    priority_category=category,
                    category_filter=category
                )
                if detail.strip():
                    parts.append(detail)
            except Exception:
                continue
        return "\n\n".join(parts) if parts else ""
    
    def _build_candidates_hint(self) -> str:
        """构建候选意图提示 — 委托到PromptAssembler"""
        assembler = PromptAssembler(self.prompts, candidates=self._candidates)
        return assembler._build_candidates_hint()
    
    def _build_cross_tool_hint(self, category_name: str) -> str:
        """构建跨分类工具提示 — 委托到PromptAssembler"""
        assembler = PromptAssembler(self.prompts, category_name=category_name)
        return assembler._build_cross_tool_hint()
    

    def _build_system_prompt(self, category_name: str) -> str:
        """构建完整system prompt — 委托到PromptAssembler统一入口 — 小沈 2026-05-27
        
        SLAP原则：调用方只需调PromptAssembler.build_system_prompt()，
        不关心三层（SystemAdapter→BasePrompts→Mixin）拼接细节。
        """
        if hasattr(self, '_custom_system_prompt') and self._custom_system_prompt:
            return self._custom_system_prompt
        assembler = PromptAssembler(
            prompts=self.prompts,
            candidates=self._candidates,
            category_name=category_name,
        )
        return assembler.build_system_prompt()
    
    # ===== LLM调用 =====
    
    async def _call_llm(self) -> str:
        """LLM调用统一入口 — 策略由策略管理器统一管理"""
        self.llm_call_count += 1
        mb = self.message_builder
        messages = mb.prepare_messages_for_llm()
        strategy = await self.strategy_manager.get_strategy()  # 策略管理器统一处理
        messages = self._inject_tools_hint(messages, strategy)
        if strategy == "text":
            messages = self._inject_schema(messages)
        self._log_prompt(messages, strategy)
        response = await self._dispatch_strategy(strategy, messages)
        self._log_response(response)
        return response


    def _inject_tools_hint(self, history_dicts, strategy_method):
        """工具提示注入（含缓存） — text策略时注入工具描述，tools策略时不注入"""
        if strategy_method != "tools":
            try:
                loaded = getattr(self, '_loaded_categories', set())
                _last = getattr(self, '_last_injected_categories', None)
                if _last is None or loaded != _last:
                    detail = self._get_tools_detail()
                    summary = self._get_tools_summary(exclude_categories=loaded)
                    self._cached_tools_content = f"【已加载工具（完整）】\n{detail}\n\n【其他可用工具（概要）】\n{summary}"
                    self._last_injected_categories = frozenset(loaded)
                _cached = getattr(self, '_cached_tools_content', None)
                if _cached:
                    history_dicts = self.message_builder.inject_tools_info(history_dicts, _cached)
            except Exception as e:
                logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
        return history_dicts

    def _inject_schema(self, history_dicts):
        """Schema文本注入 — 小沈 2026-05-21"""
        if not hasattr(self, '_cached_schema_text'):
            self._cached_schema_text = self.message_builder.build_schema_text(getattr(self, 'openai_tools', []))
        if self._cached_schema_text:
            history_dicts = self.message_builder.inject_schema_text(history_dicts, self._cached_schema_text)
        return history_dicts

    def _log_prompt(self, assembled_messages, strategy_method):
        """prompt_logger调用前记录 — 小沈 2026-05-21"""
        prompt_logger = get_prompt_logger()
        # 【修复 小健 2026-05-24】P2-13: FC协议下tool_calls字符数也计入总量
        total_chars = 0
        for m in assembled_messages:
            total_chars += len(m.get("content") or "")
            for tc in (m.get("tool_calls") or []):
                if isinstance(tc, dict):
                    total_chars += len(str(tc))
                else:
                    total_chars += len(str(vars(tc))) if hasattr(tc, '__dict__') else len(str(tc))
        prompt_logger.log_llm_call(
            round_number=self.llm_call_count,
            messages=assembled_messages,
            model=getattr(self, 'model', 'unknown'),
            provider=getattr(self, 'provider', 'unknown'),
            call_type=strategy_method or "text",
            extra_params={
                "max_steps": self.max_steps,
                "use_function_calling": getattr(self, 'use_function_calling', False),
                "trim_info": getattr(self, '_last_trim_info', None),
                "total_chars": total_chars,
            }
        )
        try:
            prompt_logger.save()
        except Exception as e:
            logger.warning(f"Failed to save prompt log: {e}")

    async def _dispatch_strategy(self, strategy_method, messages):
        """策略分派 — 只有text和tools两种"""
        _cls = self.__class__.__name__
        conv_history = self.message_builder.conversation_history
        if strategy_method == "tools":
            if not self.tools_strategy:
                raise RuntimeError(f"[{_cls}] strategy=tools 但 tools_strategy未初始化")
            if getattr(self, 'openai_tools', None):
                self.tools_strategy.tools = self.openai_tools
            response = await self.tools_strategy.call(
                llm_client=self.llm_client, messages=messages,
                conversation_history=conv_history)
            # 保存原始FC响应供FC协议注入使用（替代llm_client._last_chat_response）
            self._last_fc_raw_response = getattr(self.llm_client, '_last_chat_response', None)
            return response
        else:
            self._last_fc_raw_response = None
            return await self.text_strategy.call(
                llm_client=self.llm_client, messages=messages,
                conversation_history=conv_history)

    def _log_response(self, response):
        """prompt_logger调用后记录 — 小沈 2026-05-21"""
        response_type = "text"
        if response:
            if "action_tool" in response:
                response_type = "action_tool"
            elif "thought" in response:
                response_type = "thought"
            elif "observation" in response:
                response_type = "observation"
        prompt_logger = get_prompt_logger()
        prompt_logger.log_llm_response(
            round_number=self.llm_call_count,
            response_content=response,
            response_type=response_type,
            finish_reason="stop"
        )
    
    # ===== 任务追踪管理 =====
