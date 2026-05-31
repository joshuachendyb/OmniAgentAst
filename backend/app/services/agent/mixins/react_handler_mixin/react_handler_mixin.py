# -*- coding: utf-8 -*-
"""
ReActHandlerMixin — ReAct循环处理逻辑混入类

从 base_react.py 拆出，遵循 SRP：
- BaseAgent：ReAct循环骨架 + 状态初始化 + 抽象方法 + Hook + 工具方法
- ReActHandlerMixin：所有 _handle_* / _execute_* 响应处理逻辑

Author: 小沈 - 2026-05-28
"""

from app.services.agent.mixins.react_handler_mixin.merge_thought_text import MergeThoughtTextMixin
from app.services.agent.mixins.react_handler_mixin.handle_chunk_type import HandleChunkTypeMixin
from app.services.agent.mixins.react_handler_mixin.complete_chunk import CompleteChunkMixin
from app.services.agent.mixins.react_handler_mixin.handle_completion_type import HandleCompletionTypeMixin
from app.services.agent.mixins.react_handler_mixin.handle_thought_only import HandleThoughtOnlyMixin
from app.services.agent.mixins.react_handler_mixin.handle_parse_error import HandleParseErrorMixin
from app.services.agent.mixins.react_handler_mixin.handle_action_type import HandleActionTypeMixin
from app.services.agent.mixins.react_handler_mixin.handle_observation_flow import HandleObservationFlowMixin
from app.services.agent.mixins.react_handler_mixin.handle_pending_calls import HandlePendingCallsMixin
from app.services.agent.mixins.react_handler_mixin.handle_empty_response import HandleEmptyResponseMixin
from app.services.agent.mixins.react_handler_mixin.handle_run_exception import HandleRunExceptionMixin


class ReActHandlerMixin(
    MergeThoughtTextMixin,
    HandleChunkTypeMixin,
    CompleteChunkMixin,
    HandleCompletionTypeMixin,
    HandleThoughtOnlyMixin,
    HandleParseErrorMixin,
    HandleActionTypeMixin,
    HandleObservationFlowMixin,
    HandlePendingCallsMixin,
    HandleEmptyResponseMixin,
    HandleRunExceptionMixin,
):
    """ReAct循环响应处理逻辑 — 小沈 2026-05-28

    本混入类依赖宿主（BaseAgent及其子类）提供以下属性/方法：
    - self.conversation_history (property)
    - self.message_builder
    - self.status
    - self._parse_retry_engine / self._empty_response_retry_engine
    - self.llm_call_count
    - self.tool_category
    - self._emit_step()
    - self._exit_with_error()
    - self._check_interrupt()
    - self._on_after_loop()
    - self._execute_tool_step()
    """
    pass
