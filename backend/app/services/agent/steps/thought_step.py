# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-08-18 小欧 - §10.3.3(1): 删 tool_name/tool_params(工具动作由 action step 承载);
#   _extra_fields 仅输出 thought/reasoning(content 已由基类 to_dict 经 get_content 输出, 不重复);
#   get_content 返回 content(历史落库主文本, 前端历史展示读 thought/reasoning 不读 content)

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ThoughtStep(ReasoningStep):
    """思考步骤 - 仅落库不 yield 前端（§10.3.3(1)）"""

    TYPE: str = "thought"

    def __init__(
        self,
        step: int,
        content: str = "",
        thought: str = "",
        reasoning: str = "",
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning

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

    def _extra_fields(self) -> Dict[str, Any]:
        # content 由基类 to_dict() 经 get_content() 已输出, 此处不重复, 杜绝同值双字段
        return {"thought": self._thought, "reasoning": self._reasoning}
