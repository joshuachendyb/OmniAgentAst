# -*- coding: utf-8 -*-
"""
build_intent_prompt — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第59-113行
【清理 2026-06-07 小欧】DRY:删除硬编码_INTENT_DESCRIPTIONS,从ToolCategory.name_cn自动派生
"""

from typing import List, Dict

from app.services.intents.intent_mapper import get_aliases_for_intent
from app.services.tools.tool_types import IntentType, ToolCategory

_INTENT_DEFINITIONS: Dict[str, str] = {}
for intent_type in IntentType:
    intent_name = intent_type.value
    cat = intent_type.category
    _INTENT_DEFINITIONS[intent_name] = cat.name_cn
    for alias in get_aliases_for_intent(intent_type):
        _INTENT_DEFINITIONS[alias] = f"(已合并到{intent_name})" + cat.name_cn


def build_intent_prompt(text: str, labels: List[str]) -> str:
    """拷贝自 intent_classifier.py 第94-113行"""
    definitions_lines = []
    for label in labels:
        if label in _INTENT_DEFINITIONS:
            definitions_lines.append(f"- {label}: {_INTENT_DEFINITIONS[label]}")

    definitions_str = "\n".join(definitions_lines)

    return f"""你是一个意图分类助手。需要完成两个任务:
1. 文本矫正:仅修正明显的错别字和标点错误。严禁纠正:专有名词、人名、地名、文件名、路径、技术术语、缩写、非中文词汇。如无法判断是否为错别字,保持原样。
2. 意图分类:分析用户意图,返回所有候选意图的置信度分布

意图定义:
{definitions_str}

用户输入:{text}

请输出JSON,不要其他内容:
{{"corrected": "矫正后的文本", "intent": "最佳意图标签", "confidence": 0.0-1.0, "all_intents": {{"意图标签1": 置信度, "意图标签2": 置信度, ...}}}}"""
