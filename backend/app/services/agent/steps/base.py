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
