from typing import Any, Dict, List, Optional

from .base import ReasoningStep


class ToolStep(ReasoningStep):
    """工具执行步骤 - 执行(action_tool)+观察(observation)合并"""

    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        *,
        step_type: str = "action_tool",
        execution_status: str = "success",
        summary: str = "",
        execution_result: Any = None,
        error_message: str = "",
        action_retry_count: int = 0,
        execution_time_ms: int = 0,
        observation: str = "",
        return_direct: bool = False,
        code: str = "",
        warning: Optional[str] = None,
        attachment: Any = None,
        next_actions: Optional[List[Dict[str, str]]] = None,
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = step_type
        self._tool_name = tool_name
        self._tool_params = tool_params
        self._execution_status = execution_status
        self._summary = summary
        self._execution_result = execution_result
        self._error_message = error_message
        self._action_retry_count = action_retry_count
        self._execution_time_ms = execution_time_ms
        self._observation = observation
        self._return_direct = return_direct
        self._code = code
        self._warning = warning
        self._attachment = attachment
        self._next_actions = next_actions

    def get_content(self) -> str:
        return self._observation or self._summary or self._error_message or ""

    @property
    def is_error(self) -> bool:
        return self._execution_status == "error"

    def _extra_fields(self) -> Dict[str, Any]:
        if self.TYPE == "action_tool":
            return {
                "tool_name": self._tool_name or "",
                "tool_params": self._tool_params or {},
                "execution_status": self._execution_status,
                "execution_result": self._execution_result,
                "action_retry_count": self._action_retry_count,
                "execution_time_ms": self._execution_time_ms,
            }
        extra: Dict[str, Any] = {}
        summary_text = self._observation or self._summary or self._error_message or "执行完成"
        obs: Dict[str, Any] = {
            "summary": summary_text,
            "tool_name": self._tool_name or "unknown",
            "tool_params": self._tool_params or {},
            "return_direct": self._return_direct or False,
        }
        if self._execution_status:
            obs["execution_status"] = self._execution_status
        if self._error_message:
            obs["error_message"] = self._error_message
        if self._warning:
            obs["warning"] = self._warning
        if self._next_actions:
            obs["next_actions"] = self._next_actions
        if self._attachment is not None:
            obs["attachment"] = self._attachment
        extra["observation"] = obs
        if self._code:
            extra["code"] = self._code
        return extra
