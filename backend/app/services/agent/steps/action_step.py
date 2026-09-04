# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-08-18 小欧 - §10.3.3(2): 废除 action_tool, 新建 action(type="action");
#   字段收敛为 exec_type/tools(tools 元素含 tool/target/params, params 供回放重建 FC 参数)

from typing import Any, Dict, List, Optional

from .base import ReasoningStep


class ActionStep(ReasoningStep):
    """工具执行前信号 step - 执行前 yield 一次（§10.3.3(2)）"""

    TYPE: str = "action"

    def __init__(
        self,
        step: int,
        exec_type: str = "single",
        tools: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._exec_type = exec_type
        self._tools = tools or []

    def get_content(self) -> str:
        return ""

    @property
    def exec_type(self) -> str:
        return self._exec_type

    @property
    def tools(self) -> List[Dict[str, Any]]:
        return self._tools

    def _extra_fields(self) -> Dict[str, Any]:
        return {"exec_type": self._exec_type, "tools": self._tools}
