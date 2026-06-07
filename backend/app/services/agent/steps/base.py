# -*- coding: utf-8 -*-
"""
ReasoningStep 抽象基类

【2026-06-07 mixin 体系已彻底删除 - AI助手小欧】
- ToolMixin 已删除,tool_name/tool_params 字段已移除

Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp


class ReasoningStep(ABC):
    """所有Step类的抽象基类"""

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
            "content": self.get_content(),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self._step}, type={self.get_type()})"
