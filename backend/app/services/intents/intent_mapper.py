"""
统一意图映射模块 — 走直线

resolve_category和normalize_intent共用_lookup_intent,消除重复

小沈 - 2026-06-08
"""

from typing import List, Optional
from app.services.tools.tool_types import ToolCategory, IntentType, INTENT_MAPPING


def _lookup_intent(intent_str: str) -> Optional[IntentType]:
    key = intent_str.upper()
    return INTENT_MAPPING.get(key)



def get_agent_intent_names() -> List[str]:
    return [intent_type.value for intent_type in IntentType]


def resolve_category(intent_str: str) -> ToolCategory:
    intent = _lookup_intent(intent_str)
    return intent.category if intent else ToolCategory.FUND_RUNTIME


def normalize_intent(intent_str: str) -> str:
    intent = _lookup_intent(intent_str)
    return intent.value if intent else "system"
