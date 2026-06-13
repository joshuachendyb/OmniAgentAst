# -*- coding: utf-8 -*-
"""
UniversalAgent — 配置驱动的通用 Agent

Author: 小沈 - 2026-06-07
Updated: 小沈 - 2026-06-12 tool_calls原生消费,移除JSON roundtrip
"""
from typing import Any, List, Optional, Dict, Set
import json
from pathlib import Path

from app.services.agent.core_agent import BaseAgent
from app.services.agent.types import AgentResult
from app.services.tools.tool_types import ToolCategory
from app.services.prompts.system_prompts import SystemPrompts
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger


_INITIAL_CATEGORIES: Set[ToolCategory] = {ToolCategory.FUND_RUNTIME}

# tool_search 动态描述配置
_CATEGORIES_CONFIG_PATH = Path(__file__).resolve().parent.parent / "tools" / "meta" / "tool_categories.json"

# 分类一句话概要 — 用于 tool_search 动态描述
_CATEGORY_SUMMARIES: Dict[ToolCategory, str] = {
    ToolCategory.FILE: "文件读写、目录浏览、文件搜索和内容分析",
    ToolCategory.NET_PROCESS: "HTTP请求、文件下载、网络搜索和连通性测试",
    ToolCategory.SCREEN: "窗口管理、鼠标/键盘控制、屏幕截图和剪贴板交互",
    ToolCategory.DOC_CONTENT: "PDF/Word/Excel/PPT文档的读写和数据分析",
    ToolCategory.SYSTEM: "命令执行、系统查询、进程管理和环境配置",
}


class UniversalAgent(BaseAgent):
    """通用 Agent — 初始仅加载 FUND_RUNTIME,其余分类通过 tool_search 动态注入"""

    # 【修复P2-1】工具缓存TTL常量 — 北京老陈 2026-06-13
    TOOL_CACHE_TTL = 300

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
        self._patch_search_desc()

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
        self._patch_search_desc()

    async def _call_llm(self):
        """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()
        openai_tools = self._get_openai_tools()

        prompt_logger = get_prompt_logger()
        prompt_logger.log_llm_call(
            round_number=self.llm_call_count,
            messages=messages,
            model=getattr(self.llm_client, 'model', 'unknown'),
            provider=getattr(self.llm_client, 'provider', 'unknown'),
            call_type="tools",
            extra_params={"tool_count": len(openai_tools) if openai_tools else 0},
        )

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
        _raw_chunks: list = []

        try:
            async for chunk in self.llm_client.request_stream(
                messages=messages,
                tools=openai_tools, tool_choice="auto",
            ):
                if chunk.raw_data:
                    _raw_chunks.append(chunk.raw_data)

                if chunk.stream_error:
                    stream_error = chunk.stream_error
                    break

                if chunk.tool_calls:
                    # 【修复P1-1】累积tool_calls而非覆盖 — 北京老陈 2026-06-13
                    if tool_calls_result is None:
                        tool_calls_result = chunk.tool_calls
                    else:
                        tool_calls_result.extend(chunk.tool_calls)

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
            raw_msg = f"LLM调用异常: {e}"
            prompt_logger = get_prompt_logger()
            prompt_logger.log_llm_response(
                round_number=self.llm_call_count,
                response_content=raw_msg,
                raw_response=raw_msg,
                response_type="answer",
                finish_reason="error",
            )
            yield ("response", {"type": "answer", "content": raw_msg})
            return

        if stream_error:
            logger.error(f"[FC] 流式错误: {stream_error}")
            raw_msg = f"LLM流式错误: {stream_error}"
            prompt_logger = get_prompt_logger()
            prompt_logger.log_llm_response(
                round_number=self.llm_call_count,
                response_content=raw_msg,
                raw_response=raw_msg,
                response_type="answer",
                finish_reason="error",
            )
            yield ("response", {"type": "answer", "content": raw_msg})
            return

        complete_raw = "\n".join(_raw_chunks)

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
            prompt_logger = get_prompt_logger()
            prompt_logger.log_llm_response(
                round_number=self.llm_call_count,
                response_content=f"tool={first['tool_name']}, params={first['tool_params']}",
                raw_response=complete_raw,
                response_type="action",
                finish_reason="tool_calls",
                extra_info={
                    "tool_name": first["tool_name"],
                    "parallel_calls": len(_pending_calls),
                },
            )
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
        prompt_logger = get_prompt_logger()
        prompt_logger.log_llm_response(
            round_number=self.llm_call_count,
            response_content=content,
            raw_response=complete_raw,
            response_type="answer",
            finish_reason="stop",
        )
        yield ("response", {"type": "answer", "content": content, "thought": ""})

    def _get_openai_tools(self) -> list:
        """获取已加载分类的OpenAI格式工具定义,含TTL缓存"""
        import time
        current_time = time.time()
        cache_ts = getattr(self, '_cache_timestamp', 0)
        cached = getattr(self, '_cached_openai_tools', None)
        if cached and current_time - cache_ts < self.TOOL_CACHE_TTL:
            return cached

        from app.services.tools.registry import tool_registry
        self._cached_openai_tools = tool_registry.to_openai_tools(categories=self._loaded_categories)
        self._cache_timestamp = current_time
        return self._cached_openai_tools

    def invalidate_tool_cache(self):
        """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
        self._cached_openai_tools = None
        self._cache_timestamp = 0

    def _patch_search_desc(self):
        """动态更新 tool_search 描述: 列出未加载分类的概要+工具名"""
        if not _CATEGORIES_CONFIG_PATH.exists():
            return

        # 【修复P1-4】文件内容缓存，避免每次调用都读磁盘 — 北京老陈 2026-06-13
        import time
        now = time.time()
        if not hasattr(self, '_categories_config_cache'):
            self._categories_config_cache = None
            self._categories_config_ts = 0
        if now - self._categories_config_ts < 60:
            categories_config = self._categories_config_cache
        else:
            with open(_CATEGORIES_CONFIG_PATH, "r", encoding="utf-8") as f:
                categories_config = json.load(f)
            self._categories_config_cache = categories_config
            self._categories_config_ts = now

        unloaded = [cat for cat in ToolCategory
                    if cat != ToolCategory.FUND_RUNTIME and cat not in self._loaded_categories]

        from app.services.tools.registry import tool_registry

        ts_meta = tool_registry.get_tool("tool_search")
        if not ts_meta:
            return
        base_desc = ts_meta.description

        if not unloaded:
            return

        lines = []
        for cat in sorted(unloaded, key=lambda c: c.order):
            cfg = categories_config.get(cat.value, {})
            summary = cfg.get("summary", cat.name_cn)
            tools = cfg.get("tools", {})
            tool_items = list(tools.items())
            name_str = ", ".join(f"{k}:{v}" for k, v in tool_items[:5])
            if len(tool_items) > 5:
                name_str += "..."
            lines.append(f"- {cat.name_cn}({cat.value}): {summary} [{name_str}]")

        ts_meta.description = base_desc + "\n\n当前未加载分类:\n" + "\n".join(lines)


