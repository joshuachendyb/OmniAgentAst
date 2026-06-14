# -*- coding: utf-8 -*-
"""
ReasoningStep 抽象基类


Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp


class ReasoningStep(ABC):
    """所有Step类的抽象基类"""

    TYPE: str = ""
    IS_DONE: bool = False

    def __init__(self, step: int, timestamp: Optional[int] = None):
        self._step = step
        self._timestamp = timestamp or create_timestamp()

    @property
    def step(self) -> int:
        return self._step

    @property
    def timestamp(self) -> int:
        return self._timestamp

    def get_type(self) -> str:
        return self.TYPE

    @abstractmethod
    def get_content(self) -> str:
        pass

    def is_done(self) -> bool:
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
