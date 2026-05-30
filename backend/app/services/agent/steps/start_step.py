from typing import Any, Dict, Optional

from .base import ReasoningStep


class StartStep(ReasoningStep):
    """
    StartStep类 - 起始步骤

    表示任务开始时的起始事件：
    - type: "start"
    - is_done() = True → 不参与循环

    字段说明：
    - display_name: 模型显示名称
    - provider: 提供商
    - model: 模型名称
    - task_id: 任务ID
    - user_message: 用户消息
    - security_check: 安全检查结果
    """

    def __init__(
        self,
        step: int,
        display_name: str,
        provider: str,
        model: str,
        task_id: str,
        user_message: str,
        security_check: Dict[str, Any],
        timestamp: Optional[int] = None
    ):
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
            "display_name": self._display_name,
            "provider": self._provider,
            "model": self._model,
            "task_id": self._task_id,
            "user_message": self._user_message,
            "security_check": self._security_check,
        })
        return base_dict
