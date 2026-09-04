# -*- coding: utf-8 -*-
"""
display_utils — display_name相关公共函数

【公共函数规范】
本文件是公共utility模块,所有display_name相关公共函数必须在此定义。
禁止在业务代码(api/v1/、services/等)中重复定义公共函数。
调用方统一从此处导入:from app.utils.display_utils import xxx

Author: 小沈 - 2026-05-28
"""

# 编辑历史:
# 2026-08-25 - 小欧 - 合规重构(北京老陈驱动): 新增 format_llm_data_text(将工具结果 llm_data 格式化为前端展示文本, JSON美化失败回退str);
#   原函数体为 action_handler.build_observation 内嵌闭包(纯函数被囚为闭包, 违反1.3公用函数规范-分层/复用优先), 现拆至全局层 display_utils(逐字复制, 逻辑零改动), action_handler 改直接 import 调用并删死 import json

import json
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
    
    统一格式:"{provider} ({model})"
    
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
    # 复用extract_display_name_from_steps避免重复遍历 — 小欧 2026-07-10 M-55
    display_name = extract_display_name_from_steps(execution_steps)
    for step in execution_steps:
        if step.get("type") == "start":
            model = step.get("model")
            provider = step.get("provider")
            if not display_name and provider and model:
                display_name = build_display_name(provider, model)
            return {"model": model, "provider": provider, "display_name": display_name}
    return {"model": None, "provider": None, "display_name": None}


def format_param_value(val: Any) -> str:
    """将参数默认值格式化为字符串(供LLM提示文本使用)

    统一处理:None→""、bool→"true"/"false"、int/float→str()、其他→str()
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


def format_llm_data_text(llm_data: Dict[str, Any]) -> str:
    """将工具结果 llm_data 格式化为前端展示文本(JSON 美化, 失败回退 str)

    纯函数(无外部状态), 供 build_observation 等编排层复用; 原为 action_handler 内嵌闭包,
    2026-08-25 小欧 合规重构拆出至全局层(逐字复制, 逻辑零改动)。

    Args:
        llm_data: 工具结果中的 llm_data 字典

    Returns:
        美化 JSON 字符串(ensure_ascii=False, indent=2); 空/非 dict → ""; 序列化失败 → str(llm_data)
    """
    if not llm_data:
        return ""
    try:
        return json.dumps(llm_data, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(llm_data)


__all__ = [
    "extract_display_name_from_steps",
    "build_display_name",
    "extract_metadata_from_steps",
    "format_param_value",
    "format_llm_data_text",
]
