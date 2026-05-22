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
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy, ResponseFormatStrategy
from app.services.agent.llm_adapter import LLMAdapter
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger


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
        """初始化工具加载和执行器 - 小沈 2026-05-10
        
        首次调用时触发工具注册（ensure_tools_registered），后续调用跳过。
        """
        # 全量注册所有工具
        from app.services.tools import ensure_tools_registered
        ensure_tools_registered()
        
        if tool_category:
            self._tools_dict = self.load_tools_by_category(tool_category)
        else:
            self._tools_dict = {}
        self.executor = ToolExecutor(self._tools_dict)
        logger.info(f"[{self.__class__.__name__}] 加载工具: {len(self._tools_dict)}个")
    
    def _init_llm_strategies(self):
        """初始化LLM调用策略 - 小沈 2026-05-09
        
        FC通道启用：adapter初始化+异常降级。
        如果llm_client有api_base属性，尝试初始化LLMAdapter和ToolsStrategy；
        初始化失败则降级到纯文本模式。
        """
        self.text_strategy = TextStrategy()
        
        # 【诊断+修复 2026-05-10 小健】api_base/api_key/model 在 self 上（kwargs setattr），
        # 不在 self.llm_client 上，之前检查 self.llm_client.api_base 永远 False
        _cls = self.__class__.__name__
        _has_client = self.llm_client is not None
        _self_api_base = getattr(self, 'api_base', None) or (getattr(self.llm_client, 'api_base', None) if _has_client else None)
        _self_api_key = getattr(self, 'api_key', None) or (getattr(self.llm_client, 'api_key', None) if _has_client else None)
        _self_model = getattr(self, 'model', None) or (getattr(self.llm_client, 'model', None) if _has_client else None)
        _client_api_base = getattr(self.llm_client, 'api_base', None) if _has_client else None
        logger.info(
            f"[{_cls}] _init_llm_strategies 诊断: llm_client={_has_client}, "
            f"self.api_base={_self_api_base}, self.model={_self_model}, "
            f"llm_client.api_base={_client_api_base}"
        )
        
        try:
            from app.services.tools.registry import tool_registry
            
            # 【修复 2026-05-10 小健】从 self 上取 api_base/api_key/model，
            # 这些由 base_react.__init__ 通过 kwargs setattr 到 self 上
            if self.llm_client and _self_api_base:
                self.adapter = LLMAdapter(
                    api_base=_self_api_base,
                    api_key=_self_api_key,
                    model=_self_model,
                    auto_detect=False
                )
                
                openai_tools = tool_registry.to_openai_tools(self.tool_category)
                self.tools_strategy = ToolsStrategy(tools=openai_tools)
                # 【三策略适配 2026-05-09】传入工具枚举的response_format schema
                # 【2026-05-10 小沈】enum追加"finish"，确保LLM知道finish也是合法tool_name
                # 见文档第14章: 让response_format下LLM也知道有哪些工具可选
                tool_names = [t["function"]["name"] for t in openai_tools] + ["finish"]
                self.response_format_strategy = ResponseFormatStrategy(response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "execute_tool",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "thought": {"type": "string", "description": "分析当前状态和下一步决策"},
                                "reasoning": {"type": "string", "description": "为什么选这个工具、参数如何确定"},
                                "tool_name": {
                                    "type": "string",
                                    "enum": tool_names,
                                    "description": "工具名称，可选值：" + ", ".join(tool_names)
                                },
                                "tool_params": {
                                    "type": "object",
                                    "description": "工具参数。各工具的参数名和类型见Tools Schema参考"
                                }
                            },
                            "required": ["thought", "reasoning", "tool_name", "tool_params"]
                        }
                    }
                })
                self.use_function_calling = True
                self.openai_tools = openai_tools
                self._last_strategy_method = None
                # 【诊断 2026-05-10 小健】adapter初始化成功日志
                logger.info(
                    f"[{_cls}] _init_llm_strategies 成功: adapter=LLMAdapter, "
                    f"tools_strategy=ToolsStrategy({len(openai_tools)}tools), "
                    f"response_format_strategy=ResponseFormatStrategy(strict=True), "
                    f"use_function_calling=True"
                )
            else:
                self.adapter = None
                self.tools_strategy = None
                self.response_format_strategy = None
                self.use_function_calling = False
                self.openai_tools = []
                self._last_strategy_method = None
                logger.warning(
                    f"[{_cls}] _init_llm_strategies 跳过adapter: "
                    f"llm_client={_has_client}, self.api_base={_self_api_base} → 降级纯文本模式"
                )
        except Exception as e:
            logger.warning(f"[{_cls}] LLM策略初始化失败，降级到文本模式: {e}")
            self.adapter = None
            self.tools_strategy = None
            self.response_format_strategy = None
            self.use_function_calling = False
            self.openai_tools = []
            self._last_strategy_method = None

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
    
    def _init_session(self, enable: bool = True):
        """向后兼容：调用_init_task_tracking()"""
        self._init_task_tracking(enable=enable)
    
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
        """构建完整system prompt
        
        【2026-05-07 小沈重构】统一组装架构：
        基类build_full_system_prompt()负责公共规则(OUTPUT_FORMAT/TOOL_CALL_RULES/safety/param/rollback)
        mixin追加动态部分(candidates/cross/finish_rule)
        """
        if hasattr(self, '_custom_system_prompt') and self._custom_system_prompt:
            return self._custom_system_prompt
        base = self.prompts.build_full_system_prompt()
        return (base 
                + self._build_candidates_hint() 
                + self._build_cross_tool_hint(category_name) 
               )
    
    # ===== LLM调用 =====
    
    async def _call_llm_with_summary(self) -> str:
        """LLM调用统一入口 — 小沈 2026-05-21 简化版"""
        self.llm_call_count += 1
        mb = self.message_builder
        last_message, history_dicts = mb.split_history_for_llm()
        history_dicts = mb.merge_temp_history(history_dicts)
        strategy_method = await self._select_strategy()
        history_dicts = self._inject_tools(history_dicts, strategy_method)
        # safety: 兼容 message_builder 可能还没有 _executed_tool_summary 的场景
        _ets = getattr(mb, '_executed_tool_summary', [])
        history_dicts = mb.inject_executed_summary(history_dicts, _ets)
        if strategy_method == "text":
            history_dicts = self._inject_schema(history_dicts)
        assembled = mb.assemble_messages(history_dicts, last_message)
        self._log_prompt(assembled, strategy_method)
        response = await self._dispatch_strategy(strategy_method, last_message, history_dicts)
        self._log_response(response)
        return response

    async def _select_strategy(self) -> str:
        """策略选择+降级 — 小沈 2026-05-21"""
        _cls = self.__class__.__name__
        if not self.adapter:
            logger.warning(f"[{_cls}] adapter未初始化，降级到text策略")
            return "text"
        strategy = await self.adapter.ensure_capability()
        return strategy.method

    def _inject_tools(self, history_dicts, strategy_method):
        """工具信息注入（含缓存） — 小沈 2026-05-21"""
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

    def _try_json_object_fallback(self) -> bool:
        """兜底：text策略下试json_object — 小沈 2026-05-23
        策略选择器可能因探测失败而降级为text，但模型的_capability_cache
        实际标记了supports_response_format=True，此时试一次json_object。
        注意：capability只区分"是否支持response_format"，不区分
        json_object/json_schema，若模型只支持后者会试失败（被except兜回text）。
        """
        if not self.adapter or not self.response_format_strategy:
            return False
        cap = getattr(self.adapter, '_capability_cache', None)
        if cap is None:
            return False
        return getattr(cap, 'supports_response_format', False)

    def _log_prompt(self, assembled_messages, strategy_method):
        """prompt_logger调用前记录 — 小沈 2026-05-21"""
        prompt_logger = get_prompt_logger()
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
                "total_chars": sum(len(m.get("content","")) for m in assembled_messages),
            }
        )
        try:
            prompt_logger.save()
        except Exception as e:
            logger.warning(f"Failed to save prompt log: {e}")

    async def _dispatch_strategy(self, strategy_method, last_message, history_dicts):
        """策略分派调用LLM — 小沈 2026-05-21"""
        _cls = self.__class__.__name__
        if strategy_method == "text":
            if self._try_json_object_fallback():
                try:
                    return await self.response_format_strategy.call(
                        llm_client=self.llm_client, message=last_message,
                        history_dicts=history_dicts, conversation_history=self.message_builder.conversation_history)
                except Exception as e:
                    logger.warning(f"[{_cls}] json_object兜底失败，回退text: {e}")
            return await self.text_strategy.call(
                llm_client=self.llm_client, message=last_message,
                history_dicts=history_dicts, conversation_history=self.message_builder.conversation_history)
        elif strategy_method == "response_format":
            if not self.response_format_strategy:
                raise RuntimeError(f"[{_cls}] strategy=response_format 但 response_format_strategy未初始化")
            return await self.response_format_strategy.call(
                llm_client=self.llm_client, message=last_message,
                history_dicts=history_dicts, conversation_history=self.message_builder.conversation_history)
        elif strategy_method == "tools":
            if not self.tools_strategy:
                raise RuntimeError(f"[{_cls}] strategy=tools 但 tools_strategy未初始化")
            if getattr(self, 'openai_tools', None):
                self.tools_strategy.tools = self.openai_tools
            return await self.tools_strategy.call(
                llm_client=self.llm_client, message=last_message,
                history_dicts=history_dicts, conversation_history=self.message_builder.conversation_history)
        else:
            raise RuntimeError(f"[{_cls}] 未知的strategy_method={strategy_method}")

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
