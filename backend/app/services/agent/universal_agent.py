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

        strategy = "tools" if self.tool_category is not None else None
        base_prompt = self.prompts.build_full_system_prompt(strategy=strategy)
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

    async def _call_llm(self):
        """调用LLM — FC优先,降级text流式 — 小沈 2026-06-11"""
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()

        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})

        openai_tools = self._get_openai_tools()

        if not openai_tools:
            logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")

        async for item in self._call_llm_fc_stream(messages, openai_tools):
            yield item

    async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
        """FC模式流式调用 — 异常/纯文本降级text流式 — 小沈 2026-06-11"""
        from app.services.agent.steps import ChunkStep

        full_content = ""
        full_reasoning = ""
        stream_error = None
        chunk_step_count = 0

        try:
            async for chunk in self.llm_client.request_stream(
                messages=messages,
                mode="tools",
                tools=openai_tools,
                tool_choice="auto",
            ):
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                    break

                if chunk.content:
                    chunk_step_count += 1
                    if getattr(chunk, "is_reasoning", False):
                        full_reasoning += chunk.content
                        yield ("chunk", ChunkStep(
                            step=self.llm_call_count,
                            content=chunk.content,
                            is_reasoning=True,
                        ))
                    else:
                        full_content += chunk.content
                        yield ("chunk", ChunkStep(
                            step=self.llm_call_count,
                            content=chunk.content,
                            is_reasoning=False,
                        ))

                if chunk.is_done:
                    break

            logger.info(f"[FC] 流式完成, content_len={len(full_content)}, reasoning_len={len(full_reasoning)}, chunks={chunk_step_count}")

        except Exception as e:
            logger.warning(f"[FC] request_stream异常,降级text流式: {e}")
            async for item in self._call_llm_text_stream(messages):
                yield item
            return

        if stream_error:
            logger.error(f"[FC] 流式错误,降级text流式: {stream_error}")
            async for item in self._call_llm_text_stream(messages):
                yield item
            return

        if full_content:
            parsed = parse_json(full_content)
            if parsed and "tool_name" in parsed:
                yield ("response", full_content)
                return

        if full_content.strip():
            logger.warning("[FC] LLM返回纯文本(无tool_name),降级text流式")
            async for item in self._call_llm_text_stream(messages):
                yield item
            return

        if full_reasoning and not full_content:
            full_content = full_reasoning

        yield ("response", full_content.strip())

    async def _call_llm_text_stream(self, messages: list):
        """Text模式流式调用 — 实时输出内容 - 小沈 2026-06-09"""
        from app.services.agent.steps import ChunkStep

        full_content = ""
        full_reasoning = ""
        chunk_step_count = 0

        try:
            async for chunk in self.llm_client.request_stream(
                messages=messages,
                mode="text",
            ):
                if chunk.stream_error:
                    logger.error(f"[text] 流式错误: {chunk.stream_error}")
                    break

                if chunk.content:
                    chunk_step_count += 1
                    if getattr(chunk, "is_reasoning", False):
                        full_reasoning += chunk.content
                        yield ("chunk", ChunkStep(
                            step=self.llm_call_count,
                            content=chunk.content,
                            is_reasoning=True,
                        ))
                    else:
                        full_content += chunk.content
                        yield ("chunk", ChunkStep(
                            step=self.llm_call_count,
                            content=chunk.content,
                            is_reasoning=False,
                        ))

                if chunk.is_done:
                    break

            logger.info(f"[text] 流式调用完成, content_len={len(full_content)}, reasoning_len={len(full_reasoning)}, chunks={chunk_step_count}")

        except Exception as e:
            logger.error(f"[text] request_stream失败,降级text: {e}")
            response = await self._call_llm_text_nostream(messages)
            yield ("response", response)
            return

        if not full_content and full_reasoning:
            full_content = full_reasoning

        yield ("response", full_content.strip())

    async def _call_llm_text_nostream(self, messages: list) -> str:
        """Text模式非流式调用(降级用) - 小沈 2026-06-09"""
        try:
            response = await self.llm_client.request(messages=messages, mode="text")
        except Exception as e:
            logger.error(f"[text] request调用失败: {e}")
            return ""

        if isinstance(response, str):
            return response

        if hasattr(response, 'content'):
            return response.content or ""

        if isinstance(response, dict):
            choices = response.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "") or ""

        return ""

    def _get_openai_tools(self) -> list:
        """获取OpenAI格式工具定义 — 小沈 2026-06-09 添加TTL缓存过期"""
        import time
        current_time = time.time()
        cache_ts = getattr(self, '_cache_timestamp', 0)
        cache_ttl = getattr(self, '_cache_ttl', 300)
        cached = getattr(self, '_cached_openai_tools', None)
        if cached and current_time - cache_ts < cache_ttl:
            return cached
        
        from app.services.tools.registry import tool_registry
        category = getattr(self, 'tool_category', None)
        self._cached_openai_tools = tool_registry.to_openai_tools(category=category)
        self._cache_timestamp = current_time
        return self._cached_openai_tools

    def invalidate_tool_cache(self):
        """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
        self._cached_openai_tools = None
        self._cache_timestamp = 0

    def _update_executed_tool_summary(self, tool_name: str, result: dict, tool_params: dict = None):
        """更新已执行工具汇总（含数据摘要）— 小沈 2026-06-09
        
        Args:
            tool_name: 工具名称
            result: 工具执行结果
            tool_params: 工具参数（可选）
        """
        if not hasattr(self, '_executed_tool_summary'):
            self._executed_tool_summary = []
        
        from app.services.agent.observation_formatter import extract_status
        from app.utils.data_utils import extract_data_summary
        
        if isinstance(result, dict):
            status = extract_status(result)
            data_summary = extract_data_summary(result.get("data"))
        else:
            status = "success"
            data_summary = ""
        
        entry = f"{tool_name}→{status}"
        if data_summary:
            entry += f"|{data_summary}"
        self._executed_tool_summary.append(entry)

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
