"""
方案2：操作对象解析 parse_operation_target_v2 + 置信度计算

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md 3.2节

创建时间：2026-04-20
编写人：小沈
"""

import re
from typing import Tuple, List, Dict, Any
from app.services.command_parser.command_security import TARGET_WEIGHTS


def parse_operation_target(command: str) -> str:
    """
    解析操作对象类型（原版v1）
    """
    return parse_operation_target_v2(command)[0]


def parse_operation_target_v2(command: str) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    改进的操作对象解析 v2.0
    
    设计文档3.2节 330-368行
    改进：
    1. 使用优先级队列而不是字典遍历
    2. 添加上下文理解
    3. 返回所有匹配结果和置信度
    """
    if not command:
        return 'USER', 1.0, []
    
    command_lower = command.lower().strip()
    matches = []
    
    # 1. 定义优先级顺序（从高到低）
    priority_order = ['SYSTEM', 'PROJECT', 'USER', 'TEMP']
    
    # 2. 按优先级检查所有模式
    for target_type in priority_order:
        config = TARGET_WEIGHTS[target_type]
        for pattern in config['patterns']:
            match = re.search(pattern, command_lower, re.IGNORECASE)
            if match:
                # 计算匹配置信度
                confidence = calculate_pattern_confidence(pattern, match, command_lower)
                matches.append({
                    'type': target_type,
                    'pattern': pattern,
                    'match': match.group(),
                    'confidence': confidence
                })
    
    # 3. 如果没有匹配，返回默认值
    if not matches:
        return 'USER', 1.0, []
    
    # 4. 选择置信度最高的匹配
    best_match = max(matches, key=lambda x: x['confidence'])
    
    return best_match['type'], best_match['confidence'], matches


def calculate_pattern_confidence(pattern: str, match, command: str) -> float:
    """
    计算模式匹配置信度
    
    设计文档3.2节 369-405行
    考虑因素：
    1. 匹配长度占命令长度的比例
    2. 匹配位置（开头、中间、结尾）
    3. 模式的特异性（正则表达式的复杂度）
    """
    match_length = len(match.group())
    command_length = len(command)
    
    # 匹配长度比例
    length_ratio = match_length / command_length
    
    # 匹配位置权重（开头和结尾更重要）
    match_start = match.start()
    position_weight = 1.0
    if match_start == 0:  # 开头匹配
        position_weight = 1.2
    elif match.end() == command_length:  # 结尾匹配
        position_weight = 1.1
    
    # 模式特异性（正则表达式越复杂，置信度越高）
    specificity = 1.0
    if '\\' in pattern:  # 包含转义字符
        specificity = 1.1
    if '[' in pattern or '(' in pattern:  # 包含字符集或分组
        specificity = 1.2
    if pattern.count('\\') > 2:  # 多个转义字符
        specificity = 1.3
    
    # 综合置信度
    confidence = min(1.0, length_ratio * position_weight * specificity)
    
    return confidence