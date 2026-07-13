# -*- coding: utf-8 -*-
"""
ReasoningStep 抽象基类


Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.utils.time_utils import create_timestamp


class ReasoningStep(ABC):
    """所有Step类的抽象基类 — 小健 2026-06-18 添加model/provider property"""

    TYPE: str = ""
    IS_DONE: bool = False

    def __init__(self, step: int, timestamp: Optional[int] = None):
        self._step = step
        self._timestamp = timestamp or create_timestamp()
        self._model: Optional[str] = None
        self._provider: Optional[str] = None

    @property
    def step(self) -> int:
        return self._step

    @property
    def timestamp(self) -> int:
        return self._timestamp

    @property
    def model(self) -> Optional[str]:
        return self._model

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def type(self) -> str:
        """类型property — 小健 2026-06-18"""
        return self.TYPE

    def get_type(self) -> str:
        """兼容旧代码"""
        return self.type

    @abstractmethod
    def get_content(self) -> str:
        pass

    @property
    def is_done(self) -> bool:
        """是否完成property — 小健 2026-06-18"""
        return self.IS_DONE

    def _extra_fields(self) -> Dict[str, Any]:
        return {}

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "type": self.get_type(),
            "step": self._step,
            "timestamp": self._timestamp,
            "content": self.get_content(),
        }
        d.update(self._extra_fields())
        return d

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self._step}, type={self.get_type()})"


def create_step_counter() -> Callable[[], int]:
    """创建统一的步骤计数器函数 — 小欧 2026-06-08"""
    step_counter = 0

    def next_step() -> int:
        nonlocal step_counter
        step_counter += 1
        return step_counter

    return next_step


@dataclass
class AgentResult:
    """Agent执行结果 — 小沈"""
    success: bool
    message: str
    steps: List[ReasoningStep]
    total_steps: int
    task_id: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# MetaStep — 运行时元事件
# (start/cancelled/paused/resumed/retrying/authorization_required)
# 小沈 2026-07-13: 实现直接放在 base.py(与 ReasoningStep 基类同文件), 
# 没有单独的 meta_step.py 文件;
# 此前 steps/__init__.py 注释误写 meta_step.py, 已修正。
# 如需严格 SRP 拆分再单独抽 meta_step.py。
class MetaStep(ReasoningStep):
    """运行时元事件 - start/cancelled/paused/resumed/retrying/authorization_required — 小欧 2026-07-12 / 小沈 2026-07-13 注释修正位置"""

    def __init__(
        self,
        step: int,
        type: str,
        *,
        message: str = "",
        timestamp: Optional[int] = None,
        **kwargs: Any
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = type
        self._message = message
        self._kwargs = kwargs

    def get_content(self) -> str:
        return self._message

    def _extra_fields(self) -> Dict[str, Any]:
        fields = dict(self._kwargs)
        if self._message:
            fields["message"] = self._message
        return fields
