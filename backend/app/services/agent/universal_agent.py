# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
"""
from typing import Any, List, Optional, Dict, Set

from app.services.agent.core_agent import BaseAgent
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
from app.services.prompts.system.system_prompts import SystemPrompts
from app.utils.logger import logger


_INITIAL_CATEGORIES: Set[ToolCategory] = {ToolCategory.FUND_RUNTIME}


class UniversalAgent(BaseAgent):
    """通用 Agent — 初始仅加载 FUND_RUNTIME,其余分类通过 tool_search 动态注入"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
        initial_categories=None,
        **kwargs
    ):
        if not task_id:
            raise ValueError("task_id is required for operation tracking")

        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()

        if initial_categories is None:
            initial_categories = _INITIAL_CATEGORIES

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            max_steps=max_steps,
            initial_categories=initial_categories,
            **kwargs
        )

        self._loaded_categories: Set[ToolCategory] = set(initial_categories)
        self.prompts = SystemPrompts()

        logger.info(
            f"UniversalAgent initialized (task_id={task_id})"
        )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        return self.prompts.build_full_system_prompt()

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    async def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._retry_engine.execute_tool_with_retry(tool_name, tool_params)
        if tool_name == "tool_search":
            self._auto_inject_from_search(result)
        return result

    def _auto_inject_from_search(self, result: Dict[str, Any]) -> None:
        llm_matches = result.get("llm_data", {}).get("matches", [])
        new_cats = set()
        for m in llm_matches:
            try:
                cat = ToolCategory(m["category"])
            except (ValueError, KeyError):
                continue
            if cat not in self._loaded_categories:
                new_cats.add(cat)
        if not new_cats:
            return
        for cat in new_cats:
            self._loaded_categories.add(cat)
            self._tool_manager.load_category(cat)
        self.invalidate_tool_cache()

    async def _call_llm(self):
        """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()
        openai_tools = self._get_openai_tools()

        if not openai_tools:
            logger.error("[call_llm] 无可用工具")

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
        """获取已加载分类的OpenAI格式工具定义,含TTL缓存"""
        import time
        current_time = time.time()
        cache_ts = getattr(self, '_cache_timestamp', 0)
        cache_ttl = getattr(self, '_cache_ttl', 300)
        cached = getattr(self, '_cached_openai_tools', None)
        if cached and current_time - cache_ts < cache_ttl:
            return cached

        from app.services.tools.registry import tool_registry
        self._cached_openai_tools = tool_registry.to_openai_tools(categories=self._loaded_categories)
        self._cache_timestamp = current_time
        return self._cached_openai_tools

    def invalidate_tool_cache(self):
        """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
        self._cached_openai_tools = None
        self._cache_timestamp = 0


