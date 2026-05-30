"""
影响范围解析 parse_impact_scope

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md

创建时间：2026-04-20
编写人：小沈
"""

import re

# 常量已迁移到 constants.py — 北京老陈 2026-05-30
from app.constants import SCOPE_MULTIPLIERS, SCOPE_PATTERNS


def parse_impact_scope(command: str) -> str:
    """
    解析影响范围
    
    Args:
        command: 待解析的命令
        
    Returns:
        str: 范围类型 (SINGLE_FILE/DIRECTORY/CROSS_DIR/SYSTEM)
    """
    if not command:
        return 'SINGLE_FILE'
    
    command_lower = command.lower().strip()
    
    # 检查系统级（最危险）
    for pattern in SCOPE_PATTERNS['SYSTEM']:
        if re.search(pattern, command_lower):
            return 'SYSTEM'
    
    # 检查跨目录
    for pattern in SCOPE_PATTERNS['CROSS_DIR']:
        if re.search(pattern, command_lower):
            return 'CROSS_DIR'
    
    # 检查目录
    for pattern in SCOPE_PATTERNS['DIRECTORY']:
        if re.search(pattern, command_lower):
            return 'DIRECTORY'
    
    # 默认单文件
    return 'SINGLE_FILE'


def get_scope_multiplier(scope: str) -> float:
    """
    获取影响范围系数
    """
    return SCOPE_MULTIPLIERS.get(scope, 1.0)