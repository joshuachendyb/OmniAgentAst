# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 默认 timestamp 改 get_utc_timestamp() (UTC Z 字符串), 消除 create_timestamp 毫秒 int 依赖
# 2026-07-18 - 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致; property 返回类型 int→str
"""
ReasoningStep 抽象基类


Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.utils.time_utils import get_utc_timestamp


class ReasoningStep(ABC):
    """所有Step类的抽象基类 — 小健 2026-06-18 添加model/provider property"""

    TYPE: str = ""
    IS_DONE: bool = False

    def __init__(self, step: int, timestamp: Optional[str] = None):
        self._step = step
        self._timestamp = timestamp or get_utc_timestamp()  # 小欧 2026-07-18 时间归一化: 默认UTC Z字符串
        self._model: Optional[str] = None
        self._provider: Optional[str] = None

    @property
    def step(self) -> int:
        return self._step

    @property
    def timestamp(self) -> str:
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
        content: str = "",
        timestamp: Optional[str] = None,
        **kwargs: Any
    ):
        # 【字段契约】北京老陈 2026-07-13: MetaStep 文本统一用 content(单一权威字段)。
        # 选 content 不选 message 的决策依据:
        #   1) 与 ThoughtStep/FinalStep/ErrorStep 一致——基类 to_dict() 已通过 get_content() 输出
        #      content 键, MetaStep 须复用同一契约, 否则各 Step 序列化的文本字段名不统一;
        #   2) 旧 message 字段与前端读取字段名错位: 调用方用 content= 时序列化结果无 message 键,
        #      前端若读 message 则取消/重试提示显示为空(真实跨层缺陷, 已修);
        #   3) 后端为主、前端迎合后端——后端定 content 为权威字段, 前端改读 content。
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = type
        self._content = content
        self._kwargs = kwargs

    def get_content(self) -> str:
        return self._content

    def _extra_fields(self) -> Dict[str, Any]:
        # 【序列化规则】小欧 2026-07-13: content 已由基类 to_dict() 经 get_content() 输出,
        # 此处仅透传构造时传入的其余 kw(confirm_id/tool_name/params/safety_level/wait_time/data 等),
        # 不再单独输出 message 键, 避免同值双字段(字段双份/错位)。
        return dict(self._kwargs)
