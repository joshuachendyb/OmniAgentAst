# -*- coding: utf-8 -*-
"""
extract_metadata — 从 conversation.py 拷出

拷贝来源: conversation.py 第82-101行
"""

from typing import List, Dict, Any, Optional


def extract_metadata(execution_steps: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[str]]:
    """拷贝自 conversation.py 第82-101行"""
    if not execution_steps:
        return {"model": None, "provider": None, "display_name": None}
    for step in execution_steps:
        if step.get("type") == "start":
            model = step.get("model")
            provider = step.get("provider")
            display_name = step.get("display_name")
            if not display_name and provider and model:
                display_name = f"{provider} ({model})"
            return {"model": model, "provider": provider, "display_name": display_name}
    return {"model": None, "provider": None, "display_name": None}
