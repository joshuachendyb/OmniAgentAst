# -*- coding: utf-8 -*-
"""
Agent Mixin 显式接口约束 — Protocol定义

【ISP-002 2026-05-29 小健】
将隐式接口依赖转为Protocol定义，实现接口隔离原则。
Protocol是结构子类型，不需要宿主类显式声明实现。

使用场景:
  # 类型检查时使用
  def some_function(host: HandlerHostProtocol):
      ...

返回数据说明:
  HandlerHostProtocol: ReActHandlerMixin对宿主类的13项显式接口
"""
from typing import Any, Dict, List, Optional, Protocol


class HandlerHostProtocol(Protocol):
    """ReActHandlerMixin 对宿主类的显式接口约束 — 小健 2026-05-29"""
    conversation_history: List[Dict[str, Any]]
    message_builder: Any
    status: Any
    parse_retry_count: int
    max_parse_retries: int
    llm_call_count: int
    tool_category: Any

    async def _emit_step(self, step: Any) -> Dict[str, Any]: ...
    def _exit_with_error(self, step_count: int, error_type: str, message: str) -> Dict[str, Any]: ...
    def _on_after_loop(self) -> None: ...
    async def _execute_tool_step(
        self, tool_name: str, tool_params: Dict[str, Any],
        step_count: int, is_primary: bool = True
    ) -> Any: ...
