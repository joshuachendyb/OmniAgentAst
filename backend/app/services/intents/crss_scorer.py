"""
CRSS意图评分器 - 从chat_router.py重构出来的独立模块

功能：
- INTENT_KEYWORDS 分类关键词定义
- _compute_intent_scores 加权评分函数
- detect_intent_v2 意图检测主函数

设计文档：v1.5 3.1.2节
小沈 - 2026-05-01
"""

import re
import logging
from typing import Dict, List, Optional

from app.services.tools.base import ToolCategory

logger = logging.getLogger(__name__)

# 置信度阈值
CRSS_CONFIDENCE_THRESHOLD = 0.3


def _ascii_word_boundary_match(keyword: str, text: str) -> bool:
    r"""
    ASCII-only 词边界检查（解决Python 3中 \w 包含中文的问题）
    
    Python 3 的 \b 将中文字符视为 \w，导致 '运行npm' 中 \bnpm\b 失效。
    此函数只将 [a-zA-Z0-9_] 视为词字符，中文视为非词字符。
    
    Args:
        keyword: 关键词（如 'npm'）
        text: 被搜索的文本
        
    Returns:
        是否匹配
    """
    # 用 ASCII-only 的 \w 构建自定义边界模式
    pattern = f'(?<![a-zA-Z0-9_]){re.escape(keyword)}(?![a-zA-Z0-9_])'
    return bool(re.search(pattern, text, re.IGNORECASE))


# 操作关键词定义（按ToolCategory分类）
INTENT_KEYWORDS: Dict[str, Dict] = {
    "SHELL": {
        "keywords": [
            # 危险命令已经在 DANGEROUS_COMMANDS 中，这里只添加执行类关键词
            r'\bnpm\b', r'\bpip\b', r'\bnode\b', r'\build\b', r'\brun\b',
            r'\bexec\b', r'\bexecute\b', r'\bgcc\b', r'\bg++\b', r'\bpython\b',
            r'\bgit\b', r'\bdocker\b', r'\bgradle\b', r'\bmvn\b', r'\bmake\b',
            '执行命令', '运行脚本', '终端', 'shell'
        ],
        "chinese_keywords": ['执行命令', '运行脚本', '终端']
    },
    "TIME": {
        "keywords": [
            r'\bdate\b', r'\btime\b', r'\bnow\b', r'\bclock\b',
            r'\bcalendar\b', r'\bschedule\b',
        ],
        "chinese_keywords": ['时间', '日期', '现在几点', '今天星期', '几月几号', '什么时候']
    },
    "NETWORK": {
        "keywords": [
            r'\bping\b', r'\bcurl\b', r'\bwget\b', r'\bssh\b', r'\btelnet\b',
            r'\bnc\b', r'\bnetcat\b', r'\bnmap\b', r'\bhttp\b', r'\bhttps\b',
            r'\bftp\b', r'\bsocket\b',
        ],
        "chinese_keywords": ['下载', '端口', '扫描', '网络', '请求', 'API']
    },
    "DESKTOP": {
        "keywords": [
            r'\bscreenshot\b', r'\bcapture\b',
            r'\bclick\b', r'\btype\b', r'\bpress\b', r'\bkey\b',
        ],
        "chinese_keywords": ['截图', '录屏', '点击', '输入', '按键', '键盘', '鼠标']
    },
    "ENV": {
        "keywords": [
            r'\bPATH\b', r'\bHOME\b', r'\bTEMP\b', r'\bTMP\b',
        ],
        "chinese_keywords": ['环境变量', 'PATH', '系统变量']
    },
    "SYSTEM": {
        "keywords": [
            r'\bcpu\b', r'\bmemory\b', r'\bram\b', r'\bdisk\b',
            r'\btasklist\b', r'\bprocess\b', r'\bservice\b',
        ],
        "chinese_keywords": ['系统信息', 'CPU', '内存', '进程', '服务', '磁盘', '系统配置']
    },
    "DATABASE": {
        "keywords": [
            r'\bselect\b', r'\binsert\b', r'\bupdate\b', r'\bdelete\b',
            r'\bcreate table\b', r'\bdrop\b', r'\balter\b', r'\bjoin\b',
            r'\bsql\b', r'\bdb\b', r'\bdatabase\b',
        ],
        "chinese_keywords": ['查询', 'SQL', '数据库', '表', '数据']
    },
    # 跨类型中性词 - 不偏向任何分类，用于增加候选列表完整性
    "NEUTRAL": {
        "keywords": [
            r'\bread\b', r'\bopen\b', r'\bview\b', r'\baccess\b', r'\bprocess\b',
            r'\bcheck\b', r'\bfind\b', r'\bsearch\b', r'\blist\b',
            '读取', '打开', '查看', '访问', '处理', '检查', '查找', '搜索', '列出', '遍历'
        ],
        "chinese_keywords": ['读取', '打开', '查看', '访问', '处理', '检查', '查找', '搜索', '列出', '遍历']
    },
}


def _compute_intent_scores(command: str) -> Dict[ToolCategory, float]:
    """
    CRSS加权评分：按匹配强度计算每个意图的置信度

    评分规则：
    - 中文关键词命中：+2.0/个（明确意图）
    - 英文正则命中：  +1.0/个（中度信号）
    - FILE操作关键词：+0.5/个（宽泛匹配）
    - 危险命令：      +3.0 基础分
    - 归一化： raw_score 经 1 - 2^(-score) 映射到 [0,1)
    - 中性词：       每个分类 +0.3

    Returns:
        Dict[ToolCategory, float] 置信度从高到低排序
    """
    if not command or not command.strip():
        return {}

    command_lower = command.lower().strip()
    raw_scores: Dict[ToolCategory, float] = {}

    # ===== 0. 危险命令 → SHELL 高分 =====
    try:
        from app.services.command_security import DANGEROUS_COMMANDS
        for dangerous in DANGEROUS_COMMANDS:
            if dangerous.lower() in command_lower:
                logger.info(f"[CRSS Score] 危险命令 → SHELL +3.0: '{dangerous}'")
                raw_scores[ToolCategory.SHELL] = raw_scores.get(ToolCategory.SHELL, 0) + 3.0
                break
    except ImportError:
        pass

    # ===== 1. INTENT_KEYWORDS 分类匹配 =====
    category_map = {
        "SHELL": ToolCategory.SHELL,
        "TIME": ToolCategory.TIME,
        "NETWORK": ToolCategory.NETWORK,
        "DESKTOP": ToolCategory.DESKTOP,
        "ENV": ToolCategory.ENV,
        "SYSTEM": ToolCategory.SYSTEM,
        "DATABASE": ToolCategory.DATABASE,
    }

    for cat_name, cat_info in INTENT_KEYWORDS.items():
        # 跳过NEUTRAL分类，特殊处理
        if cat_name == "NEUTRAL":
            continue
            
        cat_enum = category_map[cat_name]

        # 中文关键词：+2.0 每个
        for kw in cat_info.get("chinese_keywords", []):
            if kw in command_lower:
                logger.info(f"[CRSS Score] {cat_name} 中文关键词 +2.0: '{kw}'")
                raw_scores[cat_enum] = raw_scores.get(cat_enum, 0) + 2.0

        # 英文关键词：+1.0 每个（可能多个匹配）
        for pattern in cat_info.get("keywords", []):
            keyword = pattern.replace(r'\b', '')
            if _ascii_word_boundary_match(keyword, command_lower):
                logger.info(f"[CRSS Score] {cat_name} 英文关键词 +1.0: '{keyword}'")
                raw_scores[cat_enum] = raw_scores.get(cat_enum, 0) + 1.0

    # ===== 1.5 跨类型中性词处理 - 不偏向任何分类，增加所有匹配分类 =====
    neutral_info = INTENT_KEYWORDS.get("NEUTRAL", {})
    neutral_score_count = 0
    for kw in neutral_info.get("chinese_keywords", []):
        if kw in command_lower:
            neutral_score_count += 1
    if neutral_score_count > 0:
        # 中性词给所有分类都加少量分数 (+0.3/个)
        for cat_enum in category_map.values():
            raw_scores[cat_enum] = raw_scores.get(cat_enum, 0) + neutral_score_count * 0.3
        logger.info(f"[CRSS Score] NEUTRAL 中性词 +{neutral_score_count * 0.3}: {neutral_score_count}个")

    # ===== 2. FILE 操作关键词 =====
    try:
        from app.services.command_security import OPERATION_WEIGHTS
        file_count = 0
        for op_type, config in OPERATION_WEIGHTS.items():
            for keyword in config.get('keywords', []):
                if keyword.lower() in command_lower:
                    file_count += 1

        if file_count > 0:
            raw_scores[ToolCategory.FILE] = raw_scores.get(ToolCategory.FILE, 0) + file_count * 0.5
            logger.info(f"[CRSS Score] FILE 关键词 +{file_count * 0.5}: {file_count}个匹配")
    except ImportError:
        pass

    # ===== 3. 归一化 =====
    scores = {}
    for cat, raw in raw_scores.items():
        # 1 - 2^(-raw) 将 raw 映射到 [0, 1)
        adjusted = 1.0 - (2.0 ** (-raw))
        scores[cat] = round(adjusted, 4)

    # 按置信度从高到低排序
    return dict(sorted(scores.items(), key=lambda x: -x[1]))


def detect_intent_v2(command: str):
    """
    新版CRSS意图检测（设计文档 v1.5 3.1.2节）

    两阶段策略的阶段1: CRSS规则匹配
    - 使用加权评分计算各意图置信度
    - 返回 ToolCategory 枚举（不再是字符串）
    - 多候选支持

    Args:
        command: 用户输入的命令

    Returns:
        tuple: (primary_intent, candidates, confidence)
            - primary_intent: Optional[ToolCategory] 主意图（None表示无匹配）
            - candidates: List[ToolCategory] 所有候选意图（按置信度排序）
            - confidence: float 主意图置信度
    """
    if not command or not command.strip():
        return None, [], 0.0

    scores = _compute_intent_scores(command)

    if not scores:
        logger.info(f"[CRSS v2] 无匹配关键词 → None，等待LLM兜底")
        return None, [], 0.0

    sorted_items = list(scores.items())
    primary = sorted_items[0][0]
    candidates = [cat for cat, _ in sorted_items]
    confidence = sorted_items[0][1]

    logger.info(
        f"[CRSS v2] 加权评分结果 → primary={primary.value}, "
        f"confidence={confidence:.4f}, all={list(scores.keys())}"
    )
    return primary, candidates, confidence


# 导出供外部使用
__all__ = [
    'INTENT_KEYWORDS',
    '_compute_intent_scores',
    'detect_intent_v2',
    'CRSS_CONFIDENCE_THRESHOLD',
]