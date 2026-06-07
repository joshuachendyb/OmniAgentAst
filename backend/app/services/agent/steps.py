# -*- coding: utf-8 -*-
"""
Step 类 - 合并 11 个 step 子文件

合并 base / thought_step / action_step / observation_step / chunk_step / final_step / error_step / incident_step / start_step / factory

Author: 小沈 2026-04-15
Updated: 小欧 2026-06-07 合并
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.utils.time_utils import create_timestamp


class ReasoningStep(ABC):
    """ReasoningStep抽象基类"""

    def __init__(self, step: int, timestamp: Optional[int] = None):
        self._step = step
        self._timestamp = timestamp or create_timestamp()

    @property
    def step(self) -> int:
        return self._step

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @abstractmethod
    def get_type(self) -> str:
        pass

    @abstractmethod
    def get_content(self) -> str:
        pass

    @abstractmethod
    def is_done(self) -> bool:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.get_type(),
            "step": self._step,
            "timestamp": self._timestamp,
            "content": self.get_content()
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self._step}, type={self.get_type()})"


class ToolMixin:
    """ToolMixin混入类 - tool_name/tool_params字段"""

    def __init__(self, tool_name: str, tool_params: Optional[Dict[str, Any]] = None):
        self._tool_name = tool_name
        self._tool_params = tool_params or {}

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def tool_params(self) -> Dict[str, Any]:
        return self._tool_params

    def get_tool_name_safe(self) -> str:
        return self._tool_name or "finish"


class ThoughtStep(ToolMixin, ReasoningStep):
    """思考步骤 - type=thought"""

    def __init__(self, step: int, content: str, tool_name: str = "", tool_params: Dict[str, Any] = None,
                 thought: str = "", reasoning: str = "", timestamp: Optional[int] = None):
        ToolMixin.__init__(self, tool_name, tool_params)
        ReasoningStep.__init__(self, step, timestamp)
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning

    def get_type(self) -> str:
        return "thought"

    def get_content(self) -> str:
        return self._content

    @property
    def content(self) -> str:
        return self._content

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def reasoning(self) -> str:
        return self._reasoning

    def is_done(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "thought": self._thought, "reasoning": self._reasoning,
            "tool_name": self._tool_name, "tool_params": self._tool_params,
        })
        return base_dict


class ActionToolStep(ToolMixin, ReasoningStep):
    """工具执行步骤 - type=action_tool"""

    def __init__(self, step: int, tool_name: str, tool_params: Dict[str, Any],
                 execution_status: str = "success", summary: str = "",
                 execution_result: Any = None, error_message: str = "",
                 action_retry_count: int = 0, execution_time_ms: int = 0,
                 timestamp: Optional[int] = None):
        ToolMixin.__init__(self, tool_name, tool_params)
        ReasoningStep.__init__(self, step, timestamp)
        self._execution_status = execution_status
        self._summary = summary
        self._execution_result = execution_result
        self._error_message = error_message
        self._action_retry_count = action_retry_count
        self._execution_time_ms = execution_time_ms

    def get_type(self) -> str:
        return "action_tool"

    def get_content(self) -> str:
        return self._summary or self._error_message

    @property
    def execution_status(self) -> str:
        return self._execution_status

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def execution_result(self) -> Any:
        return self._execution_result

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def action_retry_count(self) -> int:
        return self._action_retry_count

    @property
    def execution_time_ms(self) -> int:
        return self._execution_time_ms

    @property
    def is_error(self) -> bool:
        return self._execution_status == "error"

    def is_done(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "execution_status": self._execution_status,
            "execution_result": self._execution_result,
            "raw_data": self._execution_result,
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
            "tool_name": self._tool_name,
            "tool_params": self._tool_params,
        })
        return base_dict


class ObservationStep(ToolMixin, ReasoningStep):
    """观察步骤 - type=observation"""

    def __init__(self, step: int, tool_name: str, tool_params: Dict[str, Any],
                 observation: str = "", return_direct: bool = False,
                 execution_status: str = "", code: str = "",
                 warning: Optional[str] = None, attachment: Any = None,
                 next_actions: Optional[List[Dict[str, str]]] = None,
                 summary: str = "", error_message: str = "",
                 timestamp: Optional[int] = None):
        ToolMixin.__init__(self, tool_name, tool_params)
        ReasoningStep.__init__(self, step, timestamp)
        self._observation = observation
        self._return_direct = return_direct
        self._execution_status = execution_status
        self._code = code
        self._warning = warning
        self._attachment = attachment
        self._next_actions = next_actions
        self._summary = summary
        self._error_message = error_message

    def get_type(self) -> str:
        return "observation"

    def get_content(self) -> str:
        return self._observation

    @property
    def observation(self) -> str:
        return self._observation

    @property
    def return_direct(self) -> bool:
        return self._return_direct

    @property
    def summary(self) -> str:
        return self._summary

    @property
    def error_message(self) -> str:
        return self._error_message

    def is_done(self) -> bool:
        return self._return_direct

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        summary_text = self._observation or self._summary or self._error_message or "执行完成"
        observation_obj = {
            "summary": summary_text,
            "tool_name": self._tool_name or "unknown",
            "tool_params": self._tool_params or {},
            "return_direct": self._return_direct or False,
        }
        if self._execution_status:
            observation_obj["execution_status"] = self._execution_status
        if self._error_message:
            observation_obj["error_message"] = self._error_message
        if self._warning:
            observation_obj["warning"] = self._warning
        if self._next_actions:
            observation_obj["next_actions"] = self._next_actions
        if self._attachment is not None:
            observation_obj["attachment"] = self._attachment
        d = {"observation": observation_obj}
        if self._code:
            d["code"] = self._code
        base_dict.update(d)
        return base_dict


class ChunkStep(ReasoningStep):
    """流式块步骤 - type=chunk"""

    def __init__(self, step: int, content: str, is_reasoning: bool = False,
                 thought: str = '', reasoning: str = '', thinking: str = '',
                 model: str = '', provider: str = '', timestamp: Optional[int] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._content = content
        self._is_reasoning = is_reasoning
        self._thought = thought
        self._reasoning = reasoning
        self._thinking = thinking
        self._model = model
        self._provider = provider

    def get_type(self) -> str:
        return "chunk"

    def get_content(self) -> str:
        return self._content

    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def reasoning(self) -> str:
        return self._reasoning

    @property
    def thinking(self) -> str:
        return self._thinking

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return self._provider

    def is_done(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "is_reasoning": self._is_reasoning,
            "thought": self._thought, "reasoning": self._reasoning,
            "_thinking": self._thinking,
            "model": self._model, "provider": self._provider,
        })
        return base_dict


class FinalStep(ReasoningStep):
    """最终回答步骤 - type=final"""

    def __init__(self, step: int, response: str, thought: str = "",
                 model: Optional[str] = None, provider: Optional[str] = None,
                 is_finished: bool = True, is_streaming: bool = False,
                 is_reasoning: bool = False, display_name: Optional[str] = None,
                 timestamp: Optional[int] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._response = response
        self._thought = thought
        self._model = model
        self._provider = provider
        self._is_finished = is_finished
        self._is_streaming = is_streaming
        self._is_reasoning = is_reasoning
        self._display_name = display_name or (f"{provider} ({model})" if provider and model else provider or model or "")

    def get_type(self) -> str:
        return "final"

    def get_content(self) -> str:
        return self._response

    @property
    def response(self) -> str:
        return self._response

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def model(self) -> Optional[str]:
        return self._model

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning

    @property
    def display_name(self) -> str:
        return self._display_name

    def is_done(self) -> bool:
        return True

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "response": self._response, "thought": self._thought,
            "model": self._model, "provider": self._provider,
            "is_finished": self._is_finished, "is_streaming": self._is_streaming,
            "is_reasoning": self._is_reasoning, "display_name": self._display_name,
        })
        return base_dict


class ErrorStep(ReasoningStep):
    """错误步骤 - type=error"""

    def __init__(self, step: int, error_type: str, error_message: str,
                 recoverable: bool = False, model: Optional[str] = None,
                 provider: Optional[str] = None, reasoning: str = "",
                 is_reasoning: bool = False, context: Optional[Dict[str, Any]] = None,
                 retry_after: Optional[int] = None, details: Optional[str] = None,
                 stack: Optional[str] = None, timestamp: Optional[int] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._error_type = error_type
        self._error_message = error_message
        self._recoverable = recoverable
        self._model = model
        self._provider = provider
        self._reasoning = reasoning
        self._is_reasoning = is_reasoning
        self._context = context
        self._retry_after = retry_after
        self._details = details
        self._stack = stack

    def get_type(self) -> str:
        return "error"

    def get_content(self) -> str:
        return self._error_message

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def recoverable(self) -> bool:
        return self._recoverable

    @property
    def model(self) -> Optional[str]:
        return self._model

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def reasoning(self) -> str:
        return self._reasoning

    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning

    @property
    def context(self) -> Optional[Dict[str, Any]]:
        return self._context

    @property
    def retry_after(self) -> Optional[int]:
        return self._retry_after

    @property
    def details(self) -> Optional[str]:
        return self._details

    @property
    def stack(self) -> Optional[str]:
        return self._stack

    def is_done(self) -> bool:
        return True

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "error_type": self._error_type, "error_message": self._error_message,
            "recoverable": self._recoverable, "model": self._model,
            "provider": self._provider, "reasoning": self._reasoning,
            "is_reasoning": self._is_reasoning, "context": self._context,
            "retry_after": self._retry_after, "details": self._details,
            "stack": self._stack,
        })
        return base_dict


class IncidentStep(ReasoningStep):
    """运行时事件步骤 - type=incident"""

    def __init__(self, step: int, incident_value: str, message: str,
                 content: Optional[str] = None, timestamp: Optional[int] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._incident_value = incident_value
        self._message = message
        self._content = content or message

    def get_type(self) -> str:
        return "incident"

    def get_content(self) -> str:
        return self._message

    @property
    def incident_value(self) -> str:
        return self._incident_value

    @property
    def message(self) -> str:
        return self._message

    @property
    def incident_content(self) -> str:
        return self._content

    def is_done(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "incident_value": self._incident_value, "message": self._message, "content": self._content,
        })
        return base_dict


class StartStep(ReasoningStep):
    """起始步骤 - type=start"""

    def __init__(self, step: int, display_name: str, provider: str, model: str,
                 task_id: str, user_message: str, security_check: Dict[str, Any],
                 timestamp: Optional[int] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._display_name = display_name
        self._provider = provider
        self._model = model
        self._task_id = task_id
        self._user_message = user_message
        self._security_check = security_check

    def get_type(self) -> str:
        return "start"

    def get_content(self) -> str:
        return self._user_message

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def user_message(self) -> str:
        return self._user_message

    @property
    def security_check(self) -> Dict[str, Any]:
        return self._security_check

    def is_done(self) -> bool:
        return True

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "display_name": self._display_name, "provider": self._provider, "model": self._model,
            "task_id": self._task_id, "user_message": self._user_message,
            "security_check": self._security_check,
        })
        return base_dict


class StepFactory:
    """StepFactory工厂类 - 统一构建入口"""

    @staticmethod
    def create_thought_step(step: int, content: str, tool_name: str = "",
                            tool_params: Dict[str, Any] = None, thought: str = "",
                            reasoning: str = "") -> ThoughtStep:
        return ThoughtStep(step=step, content=content, tool_name=tool_name,
                          tool_params=tool_params, thought=thought or content, reasoning=reasoning)

    @staticmethod
    def create_action_tool_step(step: int, tool_name: str, tool_params: Dict[str, Any],
                                execution_result: Dict[str, Any], execution_time_ms: int = 0) -> ActionToolStep:
        _status = execution_result.get("status", "success")
        return ActionToolStep(
            step=step, tool_name=tool_name, tool_params=tool_params or {},
            execution_status=_status,
            summary=execution_result.get("summary", ""),
            execution_result=execution_result.get("data"),
            error_message=(execution_result.get("error_message", "") or execution_result.get("message", "")) if execution_result.get("code", 0) != 0 else "",
            action_retry_count=execution_result.get("retry_count", 0),
            execution_time_ms=execution_time_ms,
        )

    @staticmethod
    def create_chunk_step(step: int, content: str, is_reasoning: bool = False,
                          thought: str = '', reasoning: str = '', thinking: str = '',
                          model: str = '', provider: str = '') -> ChunkStep:
        return ChunkStep(step=step, content=content, is_reasoning=is_reasoning,
                        thought=thought, reasoning=reasoning, thinking=thinking,
                        model=model, provider=provider)

    @staticmethod
    def create_observation_step(step: int, tool_name: str, tool_params: Dict[str, Any],
                                execution_result: Dict[str, Any], return_direct: bool = False) -> ObservationStep:
        observation_text = execution_result.get("summary", "")
        return ObservationStep(
            step=step, tool_name=tool_name, tool_params=tool_params or {},
            observation=observation_text, return_direct=return_direct,
            execution_status=execution_result.get("status", ""),
            code=execution_result.get("code", ""),
            warning=execution_result.get("warning"),
            attachment=execution_result.get("attachment"),
            next_actions=execution_result.get("next_actions"),
            summary=execution_result.get("summary", ""),
            error_message=execution_result.get("error_message", ""),
        )

    @staticmethod
    def create_final_step(step: int, response: str, thought: str = "",
                          model: Optional[str] = None, provider: Optional[str] = None) -> FinalStep:
        return FinalStep(step=step, response=response, thought=thought, model=model, provider=provider)

    @staticmethod
    def create_error_step(step: int, error_type: str, error_message: str,
                          recoverable: bool = False, model: Optional[str] = None,
                          provider: Optional[str] = None, reasoning: str = "",
                          is_reasoning: bool = False, context: Optional[Dict[str, Any]] = None,
                          retry_after: Optional[int] = None) -> ErrorStep:
        return ErrorStep(step=step, error_type=error_type, error_message=error_message,
                        recoverable=recoverable, model=model, provider=provider,
                        reasoning=reasoning, is_reasoning=is_reasoning,
                        context=context, retry_after=retry_after)

    @staticmethod
    def create_incident_step(step: int, incident_value: str, message: str,
                             content: Optional[str] = None) -> IncidentStep:
        return IncidentStep(step=step, incident_value=incident_value, message=message, content=content)

    @staticmethod
    def create_start_step(step: int, display_name: str, provider: str, model: str,
                          task_id: str, user_message: str, security_check: Dict[str, Any]) -> StartStep:
        return StartStep(step=step, display_name=display_name, provider=provider, model=model,
                        task_id=task_id, user_message=user_message, security_check=security_check)


__all__ = [
    "ReasoningStep", "ToolMixin",
    "ThoughtStep", "ActionToolStep", "ObservationStep",
    "ChunkStep", "FinalStep", "ErrorStep", "IncidentStep", "StartStep",
    "StepFactory",
    "create_timestamp",
]
