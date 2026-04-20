"""
方案3：操作类型解析 parse_operation_type_v2

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md 3.3节

创建时间：2026-04-20
编写人：小沈
"""

import re
from typing import Tuple, List, Dict, Any
from app.services.command_parser.command_security import OPERATION_WEIGHTS


def parse_operation_type(command: str) -> str:
    """
    解析操作类型（原版v1）
    """
    return parse_operation_type_v2(command)[0]


def parse_operation_type_v2(command: str) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    改进的操作类型解析 v2.0
    
    设计文档3.3节 414-469行，添加中文支持
    改进：
    1. 使用词边界匹配（英文）+ 子串匹配（中文）
    2. 添加否定词检查
    3. 返回置信度
    """
    command_lower = command.lower().strip()
    matches = []
    
    # 定义优先级顺序
    priority_order = ['DELETE', 'EXEC', 'UPDATE', 'COPY', 'MOVE', 'CREATE', 'READ']
    
    # 定义否定词（如果命令中包含这些词，不应该匹配为该操作）
    negation_words = {
        'DELETE': ['复制', '移动', '查看', '读取'],
        'COPY': ['删除', '移动', '查看', '读取'],
        'MOVE': ['复制', '删除', '查看', '读取'],
        'EXEC': ['查看', '读取', '复制'],
        'UPDATE': ['查看', '读取', '复制', '删除'],
        'CREATE': ['删除', '修改', '查看', '读取'],
    }
    
    for op_type in priority_order:
        config = OPERATION_WEIGHTS[op_type]
        for keyword in config['keywords']:
            # 检查是否为中文关键词
            is_chinese = any('\u4e00' <= c <= '\u9fff' for c in keyword)
            
            if is_chinese:
                # 中文：使用子串匹配
                if keyword in command_lower:
                    match_start = command_lower.find(keyword)
                    match = type('obj', (), {'group': lambda: keyword, 'start': lambda: match_start, 'end': lambda: match_start + len(keyword)})()
                    
                    # 检查否定词
                    has_negation = False
                    if op_type in negation_words:
                        for neg_word in negation_words[op_type]:
                            if neg_word in command_lower:
                                has_negation = True
                                break
                    
                    if not has_negation:
                        confidence = 0.9
                        matches.append({
                            'type': op_type,
                            'keyword': keyword,
                            'confidence': confidence
                        })
            else:
                # 英文：使用词边界匹配
                pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                match = re.search(pattern, command_lower)
                
                if match:
                    # 检查否定词
                    has_negation = False
                    if op_type in negation_words:
                        for neg_word in negation_words[op_type]:
                            if neg_word in command_lower:
                                has_negation = True
                                break
                    
                    if not has_negation:
                        confidence = 1.0 if match.group() == keyword.lower() else 0.8
                        matches.append({
                            'type': op_type,
                            'keyword': keyword,
                            'confidence': confidence
                        })
    
    # 如果没有匹配，返回默认值
    if not matches:
        return 'READ', 0.5, []
    
    # 选择置信度最高的匹配
    best_match = max(matches, key=lambda x: x['confidence'])
    
    return best_match['type'], best_match['confidence'], matches