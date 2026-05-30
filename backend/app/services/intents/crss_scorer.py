"""
CRSS意图评分器 - 双维度打分：类型（第一层） + 动作（第二层）

评分逻辑：
1. 类型层：用户要对"什么"操作 → 指向ToolCategory
2. 动作层：用户要"做什么" → 通过兼容矩阵调制类型分
3. 无类型匹配时 → 动作推断类型（兜底）
4. 无任何匹配时 → 返回{}给LLM兜底

小沈 - 2026-05-01, 重构 - 小沈 - 2026-05-13
"""

import re
from typing import Dict, List, Optional, Tuple

from app.constants import CRSS_ACTION_INFERENCE_WEIGHT, CRSS_ACTION_MODULATION_FACTOR, CRSS_DANGEROUS_COMMAND_BONUS
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import setup_logger


logger = setup_logger(__name__)

# 常量已迁移到 constants.py — 北京老陈 2026-05-30
from app.constants import CRSS_CONFIDENCE_THRESHOLD


def _ascii_word_boundary_match(keyword: str, text: str) -> bool:
    pattern = f'(?<![a-zA-Z0-9_]){re.escape(keyword)}(?![a-zA-Z0-9_])'
    return bool(re.search(pattern, text, re.IGNORECASE))


# 第一层：类型关键词已迁移到 intent_mapper.py 的 CRSS_TYPE_KEYWORDS
# 使用统一的意图映射模块获取意图名称和关键词
from app.services.intents.intent_mapper import get_crss_intent_names, CRSS_TYPE_KEYWORDS, resolve_category

INTENT_NAMES = get_crss_intent_names()


# ====================================================================
# 第二层：动作兼容矩阵——用户要"做什么"
# 动作命中后通过兼容系数调制类型分：最终分 = 类型分 × (1 + 兼容系数)
# 无类型分时，用动作反推类型（兜底分）
# ====================================================================

ACTION_DEFINITIONS = {
    "read": {
        "keywords": ['cat', 'ls', 'type', 'dir', '读取', '查看', '列出', '打开'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.2,
            ToolCategory.SYSTEM: 0.8,
            ToolCategory.NETWORK: 0.5,
            ToolCategory.DESKTOP: 0.5,
        }
    },
    "create": {
        "keywords": ['create', 'mkdir', 'touch', '新建', '创建', '新增', '添加'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.0,
        }
    },
    "delete": {
        "keywords": ['rm', 'del', 'delete', 'remove', '删除', '清除', '移除'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.2,
            ToolCategory.DESKTOP: 0.5,
        }
    },
    "execute": {
        "keywords": ['run', 'exec', 'execute', '运行', '执行', '启动', '编译'],
        "compatibility": {
            ToolCategory.SYSTEM: 1.5,
        }
    },
    "query": {
        "keywords": ['select', 'query', 'search', 'find', 'grep', '查询', '搜索', '查找'],
        "compatibility": {
            ToolCategory.DOCUMENT: 1.5,
            ToolCategory.SYSTEM: 1.0,
            ToolCategory.FILE: 1.0,
        }
    },
    "navigate": {
        "keywords": ['open', 'launch', 'start', '打开', '启动', '进入'],
        "compatibility": {
            ToolCategory.DESKTOP: 1.5,
            ToolCategory.FILE: 1.0,
            ToolCategory.NETWORK: 0.8,
        }
    },
    "configure": {
        "keywords": ['set', 'config', 'change', '修改', '设置', '配置', '调整'],
        "compatibility": {
            ToolCategory.SYSTEM: 1.2,
            ToolCategory.DESKTOP: 1.0,
            ToolCategory.NETWORK: 1.0,
        }
    },
    "capture": {
        "keywords": ['screenshot', 'capture', '截图', '录屏', '拍照'],
        "compatibility": {
            ToolCategory.DESKTOP: 1.5,
        }
    },
}


# TYPE_CATEGORY_MAP 已删除，统一使用 intent_mapper.resolve_category()


def _match_keywords(keywords: list, chinese_keywords: list, text: str) -> float:
    """计算关键词匹配总分（中文+2.0/个，英文+1.0/个）"""
    score = 0
    for kw in chinese_keywords:
        if kw in text and not _is_negated(kw, text):
            score += 2.0
    for pattern in keywords:
        # 【修复 小健 2026-05-24】P2-16: 只去掉\b边界标记，其他反斜杠转义保留原样
        keyword = pattern.replace(r'\b', '')
        if keyword != pattern and '\\' in keyword:
            keyword = keyword.replace(r'\\', '\\')
        if _ascii_word_boundary_match(keyword, text):
            score += 1.0
    return score


def _is_negated(keyword: str, text: str) -> bool:
    """检查中文关键词前是否有否定前缀 - 小健 2026-05-13
    【修复 小健 2026-05-24】P2-15: 检查所有出现位置，若存在未被否定的出现则返回False
    """
    negation_words = ["不", "没", "别", "勿", "无", "未", "非", "没有", "不要", "不用"]
    start = 0
    has_non_negated = False
    while True:
        idx = text.find(keyword, start)
        if idx < 0:
            break
        prefix = text[max(0, idx - 2):idx].strip()
        if not any(negation in prefix for negation in negation_words):
            has_non_negated = True
            break
        start = idx + len(keyword)
    return not has_non_negated and text.find(keyword) >= 0


def _compute_intent_scores(command: str) -> Dict[ToolCategory, float]:
    """
    双维度CRSS加权评分

    流程：
    1. 计算类型分（CRSS_TYPE_KEYWORDS匹配）
    2. 计算动作分（ACTION_DEFINITIONS匹配）
    3. 最终分 = 类型分 × (1 + 动作兼容系数)
    4. 无类型分时 → 动作推断类型分（兜底）
    5. 归一化到[0,1)

    Returns:
        Dict[ToolCategory, float] 置信度从高到低排序
    """
    if not command or not command.strip():
        return {}

    command_lower = command.lower().strip()
    type_raw: Dict[ToolCategory, float] = {}

    # ===== 步骤1: 类型分 =====
    for type_name, kw in CRSS_TYPE_KEYWORDS.items():
        cat = resolve_category(type_name)
        score = _match_keywords(kw.get("keywords", []), kw.get("chinese_keywords", []), command_lower)
        if score > 0:
            type_raw[cat] = type_raw.get(cat, 0) + score
            logger.info(f"[CRSS] 类型匹配 {type_name}=+{score}")

    # ===== 步骤2: 动作分 =====
    action_scores = {}
    for action_name, defn in ACTION_DEFINITIONS.items():
        action_score = 0
        for kw in defn["keywords"]:
            if kw in command_lower:
                action_score += 0.5
            elif _ascii_word_boundary_match(kw, command_lower):
                action_score += 0.5
        if action_score > 0:
            action_scores[action_name] = action_score
            logger.info(f"[CRSS] 动作匹配 {action_name}=+{action_score}")

    # ===== 步骤3: 双维度合成 =====
    final_raw: Dict[ToolCategory, float] = {}

    if type_raw:
        # 有类型分 → 用动作兼容矩阵调制（支持多分类，各分类独立计算）
        for cat, type_score in type_raw.items():
            final_raw[cat] = type_score  # 基础类型分
            for action_name, action_score in action_scores.items():
                action_def = ACTION_DEFINITIONS[action_name]
                compat = action_def["compatibility"].get(cat, 0.3)
                final_raw[cat] += type_score * compat * CRSS_ACTION_MODULATION_FACTOR  # 动作调制
    elif action_scores:
        # 无类型分 → 用动作反推类型
        for action_name, action_score in action_scores.items():
            defn = ACTION_DEFINITIONS[action_name]
            for cat, compat in defn["compatibility"].items():
                if compat >= 1.0:
                    final_raw[cat] = final_raw.get(cat, 0) + action_score * CRSS_ACTION_INFERENCE_WEIGHT
        if final_raw:
            logger.info(f"[CRSS] 无类型匹配，动作推断类型: {[c.value for c in final_raw.keys()]}")

    if not final_raw:
        return {}

    # ===== 步骤4: 归一化 =====
    scores = {}
    for cat, raw in final_raw.items():
        adjusted = 1.0 - (2.0 ** (-raw))
        scores[cat] = round(adjusted, 4)

    return dict(sorted(scores.items(), key=lambda x: -x[1]))


def detect_intent_v2(command: str) -> Tuple[Optional[ToolCategory], List[ToolCategory], float]:
    """
    双维度意图检测

    Returns:
        tuple: (primary_intent, candidates, confidence)
    """
    if not command or not command.strip():
        return None, [], 0.0

    scores = _compute_intent_scores(command)

    if not scores:
        logger.info(f"[CRSS v2] 无匹配 → None，等待LLM兜底")
        return None, [], 0.0

    sorted_items = list(scores.items())
    primary = sorted_items[0][0]
    candidates = [cat for cat, _ in sorted_items]
    confidence = sorted_items[0][1]

    logger.info(
        f"[CRSS v2] 结果 → primary={primary.value}, "
        f"confidence={confidence:.4f}, all={list(scores.keys())}"
    )
    return primary, candidates, confidence


__all__ = [
    'CRSS_TYPE_KEYWORDS',
    'ACTION_DEFINITIONS',
    '_compute_intent_scores',
    'detect_intent_v2',
    'CRSS_CONFIDENCE_THRESHOLD',
]


