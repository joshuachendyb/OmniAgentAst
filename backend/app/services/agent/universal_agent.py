# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
"""
from typing import Any, List, Optional, Dict

from app.services.agent.core_agent import BaseAgent
from app.services.agent.agent_config import AgentConfig
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class UniversalAgent(BaseAgent):
    """配置驱动的通用 Agent"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: Optional[AgentConfig] = None,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        **kwargs
    ):
        if not task_id:
            raise ValueError("task_id is required for operation tracking")

        effective_category = tool_category
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
            **kwargs
        )

        if config:
            self.config = config
            self.prompts = config.prompt_class()

        logger.info(
            f"UniversalAgent initialized (task_id={task_id})"
        )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        return self.prompts.build_full_system_prompt()

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_before_loop(self, sys_prompt: str, task: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_after_loop(self):
        pass

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    async def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        return await self._retry_engine.execute_tool_with_retry(tool_name, tool_params)

    async def _call_llm(self):
        """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()
        openai_tools = self._get_openai_tools()

        if not openai_tools:
            logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")

        async for item in self._call_llm_fc_stream(messages, openai_tools):
            yield item

    async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
        """FC模式流式调用 — tool_calls原生消费,不经过JSON roundtrip — 小沈 2026-06-12"""
        from app.services.agent.steps import ChunkStep

        full_content = ""
        full_reasoning = ""
        tool_calls_result = None
        stream_error = None

        try:
            async for chunk in self.llm_client.request_stream(
                messages=messages,
                tools=openai_tools, tool_choice="auto",
            ):
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                    break

                if chunk.tool_calls:
                    tool_calls_result = chunk.tool_calls

                if chunk.content:
                    if getattr(chunk, "is_reasoning", False):
                        full_reasoning += chunk.content
                        yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=True))
                    else:
                        full_content += chunk.content
                        yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=False))

                if chunk.is_done:
                    break
        except Exception as e:
            logger.error(f"[FC] 流式异常: {e}")
            yield ("response", {"type": "answer", "content": f"LLM调用异常: {e}"})
            return

        if stream_error:
            logger.error(f"[FC] 流式错误: {stream_error}")
            yield ("response", {"type": "answer", "content": f"LLM流式错误: {stream_error}"})
            return

        if tool_calls_result:
            first = tool_calls_result[0]
            fc_context = {
                "tool_call_id": first.get("tool_call_id", ""),
                "tool_calls": first.get("tool_calls", []),
            }
            _pending_calls = []
            for tc in tool_calls_result[1:]:
                _pending_calls.append({
                    "tool_name": tc["tool_name"],
                    "tool_params": tc["tool_params"],
                    "_tool_call_id": tc.get("tool_call_id", ""),
                })
            logger.info(f"[FC] LLM原始响应(action): tool={first['tool_name']}, parallel={len(_pending_calls)}")
            yield ("response", {
                "type": "action",
                "fc_context": fc_context,
                "_pending_calls": _pending_calls,
                "tool_name": first["tool_name"],
                "tool_params": first["tool_params"],
                "tool_call_id": first.get("tool_call_id", ""),
                "tool_calls": first.get("tool_calls", []),
            })
            return

        content = full_content or full_reasoning or ""
        logger.info(f"[FC] LLM原始响应(answer): {content}")
        yield ("response", {"type": "answer", "content": content, "thought": ""})

    def _get_openai_tools(self) -> list:
        """获取OpenAI格式工具定义 — 小沈 2026-06-09 添加TTL缓存过期
        P0修复: 多分类加载时传category=None,确保extra_tools对LLM可见 — 小沈 2026-06-11"""
        import time
        current_time = time.time()
        cache_ts = getattr(self, '_cache_timestamp', 0)
        cache_ttl = getattr(self, '_cache_ttl', 300)
        cached = getattr(self, '_cached_openai_tools', None)
        if cached and current_time - cache_ts < cache_ttl:
            return cached
        
        from app.services.tools.registry import tool_registry
        loaded = getattr(self, '_loaded_categories', set())
        category = getattr(self, 'tool_category', None)
        if len(loaded) > 1:
            category = None
        self._cached_openai_tools = tool_registry.to_openai_tools(category=category)
        self._cache_timestamp = current_time
        return self._cached_openai_tools

    def invalidate_tool_cache(self):
        """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
        self._cached_openai_tools = None
        self._cache_timestamp = 0


