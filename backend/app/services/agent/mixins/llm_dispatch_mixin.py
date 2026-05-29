# -*- coding: utf-8 -*-
"""
LLMDispatchMixin — LLM调用+策略分发职责混入类

负责：
- _init_llm_strategies: 初始化LLM调用策略
- _call_llm: LLM调用统一入口
- _dispatch_strategy: 策略分派

Author: 小沈 - 2026-05-29 (从react_agent_mixin.py拆分)
Updated: 小沈 - 2026-05-29 (DRY修复: 提取_resolve_llm_attr)
"""
from typing import Any, Optional

from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy
from app.services.agent.strategy_manager import LLMStrategyManager
from app.services.llm.capability_detector import CapabilityDetector
from app.utils.logger import logger


def _resolve_llm_attr(obj, attr_name: str) -> Optional[Any]:
    """从self或llm_client获取LLM属性 — 消除getattr重复 — 小沈 2026-05-29"""
    value = getattr(obj, attr_name, None)
    if value is None and getattr(obj, 'llm_client', None) is not None:
        value = getattr(obj.llm_client, attr_name, None)
    return value


class LLMDispatchMixin:
    """LLM调用+策略分发职责混入类"""

    def _init_llm_strategies(self):
        """初始化LLM调用策略 - 小健 2026-05-23

        创建策略对象和detector，策略在首次LLM调用时懒确定并缓存。
        【2026-05-27 小沈】使用CapabilityDetector替代LLMAdapter
        """
        self.text_strategy = TextStrategy()

        _cls = self.__class__.__name__
        _has_client = self.llm_client is not None
        _self_api_base = _resolve_llm_attr(self, 'api_base')
        _self_api_key = _resolve_llm_attr(self, 'api_key')
        _self_model = _resolve_llm_attr(self, 'model')
        logger.info(
            f"[{_cls}] _init_llm_strategies: llm_client={_has_client}, "
            f"api_base={_self_api_base}, model={_self_model}"
        )

        try:
            from app.services.tools.registry import tool_registry

            if self.llm_client and _self_api_base:
                self.detector = CapabilityDetector(
                    api_base=_self_api_base,
                    api_key=_self_api_key,
                    model=_self_model,
                )
                self.strategy_manager = LLMStrategyManager(self.detector)

                openai_tools = tool_registry.to_openai_tools(self.tool_category)
                self.tools_strategy = ToolsStrategy(tools=openai_tools)
                self.use_function_calling = True
                self.openai_tools = openai_tools
                logger.info(f"[{_cls}] _init_llm_strategies 成功: tools={len(openai_tools)}, use_function_calling=True, 策略待首次调用确定")
            else:
                self.detector = None
                self.strategy_manager = None
                self.tools_strategy = None
                self.use_function_calling = False
                self.openai_tools = []
                self._strategy = "text"
                _reason = "llm_client is None" if not self.llm_client else "api_base为空"
                logger.warning(f"[{_cls}] _init_llm_strategies 跳过detector({_reason}): 直接text模式")
        except Exception as e:
            logger.warning(f"[{_cls}] LLM策略初始化失败，降级到文本模式: {e}")
            self.detector = None
            self.strategy_manager = None
            self.tools_strategy = None
            self.use_function_calling = False
            self.openai_tools = []
            self._strategy = "text"

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
