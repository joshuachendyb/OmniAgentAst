# -*- coding: utf-8 -*-
"""
PromptBuildMixin — Prompt构建+日志职责混入类

负责：
- _inject_tools_hint: 工具提示注入（含缓存）
- _inject_schema: Schema文本注入
- _build_system_prompt: 构建完整system prompt
- _build_candidates_hint: 构建候选意图提示
- _build_cross_tool_hint: 构建跨分类工具提示
- _log_prompt: prompt_logger调用前记录
- _log_response: prompt_logger调用后记录

Author: 小沈 - 2026-05-29 (从react_agent_mixin.py拆分)
"""
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.prompts.prompt_assembler import PromptAssembler
from app.services.agent.agent_utils.message_utils import inject_tools_info, inject_schema_text, build_schema_text


class PromptBuildMixin:
    """Prompt构建+日志职责混入类"""

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
                    history_dicts = inject_tools_info(history_dicts, _cached)
            except Exception as e:
                logger.warning(f"[ToolSummary] 注入工具概要失败: {e}")
        return history_dicts

    def _inject_schema(self, history_dicts):
        """Schema文本注入 — 小沈 2026-05-21"""
        if not hasattr(self, '_cached_schema_text'):
            self._cached_schema_text = build_schema_text(getattr(self, 'openai_tools', []))
        if self._cached_schema_text:
            history_dicts = inject_schema_text(history_dicts, self._cached_schema_text)
        return history_dicts

    def _build_candidates_hint(self) -> str:
        """构建候选意图提示 — 委托到PromptAssembler"""
        assembler = PromptAssembler(self.prompts, candidates=self._candidates)
        return assembler.build_candidates_hint()

    def _build_cross_tool_hint(self, category_name: str) -> str:
        """构建跨分类工具提示 — 委托到PromptAssembler"""
        assembler = PromptAssembler(self.prompts, category_name=category_name)
        return assembler.build_cross_tool_hint()

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
