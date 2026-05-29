# -*- coding: utf-8 -*-
"""
PromptBuildMixin — Prompt构建+日志职责混入类

负责：
- _build_system_prompt: 构建完整system prompt
- _build_candidates_hint: 构建候选意图提示
- _build_cross_tool_hint: 构建跨分类工具提示
- _log_prompt: prompt_logger调用前记录
- _log_response: prompt_logger调用后记录

Author: 小沈 - 2026-05-29 (从react_agent_mixin.py拆分)
Updated: 小沈 - 2026-05-29 (ISP修复: _inject_tools_hint/_inject_schema移入ToolInitMixin)
"""
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.prompts.prompt_assembler import PromptAssembler


class PromptBuildMixin:
    """Prompt构建+日志职责混入类"""

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
        total_chars = sum(
            len(str(m.get("content") or "")) +
            sum(len(str(tc)) for tc in (m.get("tool_calls") or []))
            for m in assembled_messages
        )
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
