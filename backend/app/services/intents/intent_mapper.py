"""
统一意图映射模块

责任:意图字符串→IntentType/ToolCategory 的运行时映射
数据定义已全部移至 app.services.tools.tool_types(OCP 单一定义源)

小健 - 2026-06-07 清理别名映射 — 删除INTENT_ALIASES(39条别名),统一用INTENT_MAPPING
"""

from typing import List
from app.services.tools.tool_types import ToolCategory, IntentType, INTENT_MAPPING


def get_crss_intent_names() -> List[str]:
    """获取CRSS使用的意图名称列表(大写)"""
    return list(INTENT_MAPPING.keys())


def get_agent_intent_names() -> List[str]:
    """获取Agent配置使用的意图名称列表(小写)"""
    return [intent_type.value for intent_type in IntentType]


def resolve_category(intent_str: str) -> ToolCategory:
    """解析意图字符串到ToolCategory"""
    if intent_str.upper() in INTENT_MAPPING:
        return INTENT_MAPPING[intent_str.upper()].category
    return ToolCategory.SYSTEM


def normalize_intent(intent_str: str) -> str:
    """规范化意图字符串"""
    if intent_str.upper() in INTENT_MAPPING:
        return INTENT_MAPPING[intent_str.upper()].value
    return "system"
