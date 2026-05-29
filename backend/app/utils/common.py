# -*- coding: utf-8 -*-
"""
通用公共函数 — 未归类的公共函数集中于此

【公共函数规范】
本文件是公共utility模块，所有未归类的公共函数必须在此定义。
禁止在业务代码（api/v1/、services/等）中重复定义公共函数。
调用方统一从此处导入：from app.utils.common import xxx

Author: 小沈 - 2026-05-28
"""

from typing import Optional, List, Dict, Any


def extract_display_name_from_steps(execution_steps_data: list) -> Optional[str]:
    """从 execution_steps 中提取 display_name 信息"""
    if not execution_steps_data:
        return None

    for step in execution_steps_data:
        if isinstance(step, dict):
            if step.get("type") in ["start", "chunk", "final"]:
                model = step.get("model", "")
                provider = step.get("provider", "")
                if model or provider:
                    return build_display_name(provider, model)
    return None


def build_display_name(provider: str = "", model: str = "") -> str:
    """构建display_name字符串
    
    统一格式："{provider} ({model})"
    
    Args:
        provider: 提供商名称
        model: 模型名称
        
    Returns:
        display_name字符串
    """
    if provider and model:
        return f"{provider} ({model})"
    elif model:
        return model
    elif provider:
        return provider
    return ""


def extract_metadata_from_steps(execution_steps: Optional[List[Dict[str, Any]]]) -> Dict[str, Optional[str]]:
    """从execution_steps的start步骤提取model/provider/display_name
    
    Args:
        execution_steps: 执行步骤列表
        
    Returns:
        dict: {"model": str|None, "provider": str|None, "display_name": str|None}
    """
    if not execution_steps:
        return {"model": None, "provider": None, "display_name": None}
    for step in execution_steps:
        if step.get("type") == "start":
            model = step.get("model")
            provider = step.get("provider")
            display_name = step.get("display_name")
            if not display_name and provider and model:
                display_name = build_display_name(provider, model)
            return {"model": model, "provider": provider, "display_name": display_name}
    return {"model": None, "provider": None, "display_name": None}


def format_param_value(val: Any) -> str:
    """将参数默认值格式化为字符串（供LLM提示文本使用）

    统一处理：None→""、bool→"true"/"false"、int/float→str()、其他→str()
    调用方根据需要加 "default=" 等前缀。

    Args:
        val: 参数值

    Returns:
        格式化后的字符串
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    return str(val)


__all__ = [
    "extract_display_name_from_steps",
    "build_display_name",
    "extract_metadata_from_steps",
    "format_param_value",
]
