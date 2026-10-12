# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-08-18 小欧 - 落码: ObservationStep 仅携带 tool_result 数组(每元素自包含);
#   删 llm_data/other_data/parallel_results 顶层字段; get_content 返回 ""(数据在 tool_result, 不重复发 content)
# 2026-10-12 小欧 - 启用 content（北京老陈令）: __init__ 内自算 content_items 对象数组,
#   get_content 返回一句一工具的人话句子, _extra_fields 增返回 content_items;
#   调用方(observation_builder / react_step)零改动, 两条 emit 路径天然一致 — 小欧 2026-10-12

from typing import Any, Dict, List, Optional

from .base import ReasoningStep
from .observation_content import build_content_items, render_line


class ObservationStep(ReasoningStep):
    """观察步骤 - 仅承载 tool_result 数组"""

    TYPE: str = "observation"

    def __init__(
        self,
        step: int,
        *,
        tool_result: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._tool_result = tool_result or []
        self._content_items = build_content_items(self._tool_result)

    def get_content(self) -> str:
        """一个工具一句话, 行数 == content_items 元素数 — 小欧 2026-10-12"""
        return "\n".join(render_line(item) for item in self._content_items)

    @property
    def content_items(self) -> List[Dict[str, Any]]:
        return self._content_items

    @property
    def tool_result(self) -> List[Dict[str, Any]]:
        return self._tool_result

    def _extra_fields(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"content_items": self._content_items}
        if self._tool_result:
            result["tool_result"] = self._tool_result
        return result
