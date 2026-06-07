# -*- coding: utf-8 -*-
"""
run_stream - 从 base_react.py 拆出

"""
from typing import Any, Dict, Optional, AsyncGenerator


async def run_stream(
    self,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """占位循环 - mixin 体系已删除,业务逻辑待重构"""
    if max_steps is None:
        from app.config import get_config
        max_steps = get_config().get_max_steps()
    for step_count in range(1, max_steps + 1):
        yield {"type": "not_implemented", "step": step_count}
