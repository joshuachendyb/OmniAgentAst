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
        # 【Phase 1 小健 2026-05-14】按当前分类+support_tool注册（support_tool含finish，所有Agent必需）
        from app.services.tools import ensure_tools_registered
        if tool_category:
            ensure_tools_registered(categories=[tool_category.value, "support_tool"])
        else:
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
        _self_api_base = getattr(self, 'api_base', None)
        _self_api_key = getattr(self, 'api_key', None)
        _self_model = getattr(self, 'model', None)
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
                # 【诊断 2026-05-10 小健】llm_client无api_base，无法初始化adapter
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
        """获取已加载分类工具的完整描述（使用场景+示例+返回格式） - 小健 2026-05-14

        【关键设计】按_loaded_categories输出detail，而非只输出初始分类。
        动态加载新分类后，_loaded_categories会扩展，下一轮LLM调用会自动
        包含新分类的完整工具描述。

        例如：NetworkAgent初始化时_loaded_categories={"network"}
        → 只输出network分类的detail
        动态加载shell后_loaded_categories={"network","shell"}
        → 输出network+shell两个分类的detail
        """
        from app.services.tools.registry import tool_registry, ToolCategory
        parts = []
        loaded_cats = getattr(self, '_loaded_categories', set())
        for cat_name in sorted(loaded_cats):
            try:
                category = ToolCategory(cat_name)
                detail = tool_registry.get_all_tools_detail(
                    priority_category=category,
                    category_filter=category
                )
                if detail.strip():
                    parts.append(detail)
            except (ValueError, Exception):
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
    
    def _tools_to_schema_text(self) -> str:
        """将openai_tools转换为文本格式（方案C）- 小沈 2026-05-10
        
        直接复用tools结构，转换为LLM可读的文本格式。
        替代G6（get_parameter_reminder），只在text和response策略下使用。
        
        Returns:
            Schema文本（如："timer_set: delay(number, required), callback(string, required)"）
        """
        if not hasattr(self, 'openai_tools') or not self.openai_tools:
            return ""
        
        lines = ["【Tools Schema参考（仅作参考，实际调用仍以JSON格式返回）】:"]
        
        for tool in self.openai_tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            params = func.get("parameters", {})
            properties = params.get("properties", {})
            required = params.get("required", [])
            
            if not properties:
                lines.append(f"{name}: 无参数")
                continue
            
            params_list = []
            for pname, pinfo in properties.items():
                ptype = pinfo.get("type", "any")
                pdefault = pinfo.get("default")
                is_required = pname in required
                
                if pdefault is not None:
                    params_list.append(f"{pname}({ptype}, default={pdefault})")
                elif is_required:
                    params_list.append(f"{pname}({ptype}, required)")
                else:
                    params_list.append(f"{pname}({ptype}, optional)")
            
            lines.append(f"{name}: {', '.join(params_list)}")
        
        return "\n".join(lines)
    
    async def _call_llm_with_summary(self) -> str:
        """LLM调用统一入口（含工具概要注入+方案C Schema注入+adapter策略选择+prompt_logger+temp_history）
        
        【2026-05-10 小沈】方案C：text和response策略下注入Schema文本替代G6
        【2026-05-12 小沈】合并file_react独有逻辑：prompt_logger + temp_history + use_function_calling分支
        """
        self.llm_call_count += 1
        _cls = self.__class__.__name__
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            # ========== temp_history集成（v2.4新增，小沈2026-05-12）==========
            # 将chunk过程中的临时历史合并到history_dicts，让LLM下一轮能看到chunk输出
            if hasattr(self, 'temp_history') and self.temp_history:
                history_dicts = list(history_dicts) + list(self.temp_history)
            
            # 【Phase 1优化 小健 2026-05-14】分级注入：已加载分类Detail + 其他分类Summary(exclude)
            try:
                loaded = getattr(self, '_loaded_categories', set())
                detail_text = self._get_tools_detail()
                summary_text = self._get_tools_summary(exclude_categories=loaded)
                tools_msg = {
                    "role": "system",
                    "content": f"【已加载工具（完整）】\n{detail_text}\n\n【其他可用工具（概要）】\n{summary_text}"
                }
                history_dicts = list(history_dicts) + [tools_msg]
            except Exception as e:
                logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
            
            # ========== debug日志（原file_react独有，小沈2026-05-12合入）==========
            logger.debug(f"[Debug] _call_llm_with_summary - conversation_history长度: {len(self.conversation_history)}")
            logger.debug(f"[Debug] _call_llm_with_summary - history_dicts长度: {len(history_dicts)}")
            for i, h in enumerate(history_dicts):
                logger.debug(f"[Debug] history[{i}] role={h.get('role')}, content长度={len(h.get('content', ''))}")
            logger.debug(f"[Debug] _call_llm_with_summary - last_message长度: {len(last_message)}")
            logger.debug(f"[Debug] _call_llm_with_summary - last_message内容: {last_message[:200]}")
            
            # ========== 确定策略 + Schema注入（小沈2026-05-12重构）==========
            # 提前确定策略，统一处理Schema注入，确保prompt_logger记录完整组装后的消息
            strategy_method = None
            if self.adapter:
                strategy = await self.adapter.ensure_capability()
                strategy_method = strategy.method
                logger.info(f"[{_cls}] 执行策略: {strategy.method}")
            elif getattr(self, 'use_function_calling', False) and getattr(self, 'openai_tools', None):
                strategy_method = "tools"
                logger.info(f"[{_cls}] 无adapter，使用Function Calling模式")
            else:
                logger.info(f"[{_cls}] _call_llm_with_summary adapter=None → 走text兜底")
            
            # 方案C：text和response_format策略下注入tools Schema文本（tools策略不注入）
            if strategy_method in ("text", "response_format"):
                schema_text = self._tools_to_schema_text()
                if schema_text:
                    schema_msg = {"role": "system", "content": schema_text}
                    history_dicts = list(history_dicts) + [schema_msg]
                    logger.info(f"[{_cls}] 注入工具Schema ({strategy_method}模式)")
            elif strategy_method is None:
                # 兜底也注入Schema
                schema_text = self._tools_to_schema_text()
                if schema_text:
                    schema_msg = {"role": "system", "content": schema_text}
                    history_dicts = list(history_dicts) + [schema_msg]
                    logger.info("[Schema Injection] Injected tools schema for text fallback")
            
            # ========== prompt_logger: 调用前记录（小沈2026-05-12修正）==========
            # 必须在prompt完整组装后记录，包含：temp_history + 工具概要 + Schema注入
            prompt_logger = get_prompt_logger()
            assembled_messages = list(history_dicts) + [{"role": "user", "content": last_message}]
            prompt_logger.log_llm_call(
                round_number=self.llm_call_count,
                messages=assembled_messages,
                model=getattr(self, 'model', 'unknown'),
                provider=getattr(self, 'provider', 'unknown'),
                call_type=strategy_method or "text",
                extra_params={
                    "max_steps": self.max_steps,
                    "use_function_calling": getattr(self, 'use_function_calling', False)
                }
            )
            try:
                prompt_logger.save()
            except Exception as e:
                logger.warning(f"Failed to save prompt log: {e}")
            
            # ========== 执行策略调用LLM ==========
            response = None
            if strategy_method == "text":
                response = await self.text_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
            elif strategy_method == "response_format" and self.response_format_strategy:
                response = await self.response_format_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
            elif strategy_method == "tools" and self.tools_strategy:
                if getattr(self, 'openai_tools', None):
                    self.tools_strategy.tools = self.openai_tools
                response = await self.tools_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
            
            # text兜底（策略无匹配时）
            if response is None:
                if strategy_method is not None:
                    logger.warning(
                        f"[{_cls}] _call_llm_with_summary 策略无匹配分支: method={strategy_method}, "
                        f"has_tools_strategy={self.tools_strategy is not None}, "
                        f"has_response_format_strategy={self.response_format_strategy is not None} → 走text兜底"
                    )
                response = await self.text_strategy.call(
                    llm_client=self.llm_client, message=last_message,
                    history_dicts=history_dicts, conversation_history=self.conversation_history)
            
            # ========== prompt_logger: 调用后记录（原file_react独有，小沈2026-05-12合入）==========
            response_type = "text"
            if response:
                if "action_tool" in response:
                    response_type = "action_tool"
                elif "thought" in response:
                    response_type = "thought"
                elif "observation" in response:
                    response_type = "observation"
            prompt_logger.log_llm_response(
                round_number=self.llm_call_count,
                response_content=response,
                response_type=response_type,
                finish_reason="stop"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"[{_cls}] LLM client error: {e}")
            raise
    
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
