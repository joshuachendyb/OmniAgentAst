# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-08 清理空壳
"""
from typing import Any, List, Optional, Dict

from app.services.agent.core_agent import BaseAgent
from app.services.agent.agent_config import AgentConfig
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
import json
from app.utils.logger import logger
from app.utils.json_utils import parse_json


class UniversalAgent(BaseAgent):
    """配置驱动的通用 Agent"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: Optional[AgentConfig] = None,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            intent_type = config.intent_type if config else "unknown"
            raise ValueError(f"task_id is required for {intent_type} operation tracking")

        effective_category = tool_category or (config.category if config else None)
        if max_steps is None:
            if config and config.max_steps:
                effective_max_steps = config.max_steps
            else:
                from app.config import get_config
                effective_max_steps = get_config().get_max_steps()
        else:
            effective_max_steps = max_steps
        rollback_enabled = config.rollback_enabled if config else True

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=effective_max_steps,
            rollback_enabled=rollback_enabled,
            candidates=candidates,
            **kwargs
        )

        if config:
            self.config = config
            self.prompts = config.prompt_class()
            logger.info(
                f"UniversalAgent initialized (intent={config.intent_type}, task_id={task_id}, category={effective_category})"
            )
        else:
            logger.info(
                f"UniversalAgent initialized (task_id={task_id}, category={effective_category})"
            )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        base_prompt = self.prompts.build_full_system_prompt()
        candidates_hint = self._build_candidates_hint()
        cross_tool_hint = self._build_cross_tool_hint()
        parts = [base_prompt]
        if candidates_hint:
            parts.append(candidates_hint)
        if cross_tool_hint:
            parts.append(cross_tool_hint)
        return "\n\n".join(parts)

    def _build_candidates_hint(self) -> str:
        if not self._candidates:
            return ""
        from app.services.agent.agent_config import resolve_agent_config
        names = []
        for c in self._candidates:
            cfg = resolve_agent_config(c)
            if cfg:
                names.append(f"{cfg.category_display_name}({c})")
        if not names:
            return ""
        return f"【候选意图】用户任务可能属于以下分类: {', '.join(names)}。如当前工具无法完成,可尝试其他分类的工具。"

    def _build_cross_tool_hint(self) -> str:
        loaded = getattr(self, '_loaded_categories', set())
        if len(loaded) <= 1:
            return ""
        from app.services.agent.agent_config import AGENT_REGISTRY
        loaded_names = []
        for intent_type, cfg in AGENT_REGISTRY.items():
            if cfg.category.value in loaded:
                loaded_names.append(cfg.category_display_name)
        if not loaded_names:
            return ""
        return f"【跨分类工具】当前已加载多分类工具: {', '.join(loaded_names)}。可跨分类调用工具完成任务。"

    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.prompts.get_task_prompt(task)

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_after_loop(self):
        pass

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    async def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        return await self._retry_engine.execute_tool_with_retry(tool_name, tool_params)

    async def _call_llm(self) -> str:
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()

        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})

        openai_tools = self._get_openai_tools()

        if openai_tools:
            return await self._call_llm_fc(messages, openai_tools)
        return await self._call_llm_text(messages)

    def _get_openai_tools(self) -> list:
        if hasattr(self, '_cached_openai_tools') and self._cached_openai_tools:
            return self._cached_openai_tools
        from app.services.tools.tool_description import to_openai_tools
        from app.services.tools.registry import tool_registry
        category = getattr(self, 'tool_category', None)
        self._cached_openai_tools = to_openai_tools(tool_registry, category=category)
        return self._cached_openai_tools

    async def _call_llm_fc(self, messages: list, openai_tools: list) -> str:
        try:
            response = await self.llm_client.chat(
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )
        except Exception as e:
            logger.warning(f"[FC] chat_with_tools失败,降级text: {e}")
            return await self._call_llm_text(messages)

        choices = response.get("choices", [])
        if not choices:
            return ""

        msg = choices[0].get("message", {})
        tool_calls = msg.get("tool_calls", [])
        content = msg.get("content", "")

        if tool_calls:
            return self._format_tool_calls(tool_calls, content)

        if content:
            return content

        return '{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}'

    async def _call_llm_text(self, messages: list) -> str:
        try:
            response = await self.llm_client.chat(messages=messages)
        except Exception as e:
            logger.error(f"[text] chat调用失败: {e}")
            return ""

        choices = response.get("choices", [])
        if not choices:
            return ""

        content = choices[0].get("message", {}).get("content", "")
        return content or ""

    def _format_tool_calls(self, tool_calls: list, content: str = "") -> str:
        if not tool_calls:
            return '{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}'

        if len(tool_calls) == 1:
            func = tool_calls[0].get("function", {})
            tool_name = func.get("name", "")
            tool_params = parse_json(func.get("arguments", "{}")) or {}
            thought = content.strip() if content else f"Calling tool: {tool_name}"
            return json.dumps({
                "thought": thought,
                "reasoning": f"FC调用: {tool_name}",
                "tool_name": tool_name,
                "tool_params": tool_params,
            }, ensure_ascii=False)

        first = tool_calls[0]
        func = first.get("function", {})
        tool_name = func.get("name", "")
        tool_params = parse_json(func.get("arguments", "{}")) or {}
        pending = []
        for tc in tool_calls[1:]:
            f = tc.get("function", {})
            args = parse_json(f.get("arguments", "{}")) or {}
            pending.append({"tool_name": f.get("name", ""), "tool_params": args})
        thought = content.strip() if content else f"Calling {len(tool_calls)} tools"
        return json.dumps({
            "thought": thought,
            "reasoning": f"FC调用: {tool_name} +{len(pending)} pending",
            "tool_name": tool_name,
            "tool_params": tool_params,
            "_pending_calls": pending,
        }, ensure_ascii=False)

    def _build_executed_tool_summary(self) -> str:
        if not hasattr(self, '_executed_tool_summary') or not self._executed_tool_summary:
            return ""
        done = [s for s in self._executed_tool_summary if '→success' in s]
        if not done:
            return ""
        parts = []
        for entry in done[-8:]:
            if '|' in entry:
                tool_status, data_hint = entry.split('|', 1)
                parts.append(f"{tool_status}({data_hint})")
            else:
                parts.append(entry)
        return ("【已执行工具(勿重复)】" + "; ".join(parts)
                + "\n注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!")
