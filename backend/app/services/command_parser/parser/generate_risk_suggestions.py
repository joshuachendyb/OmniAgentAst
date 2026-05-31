# -*- coding: utf-8 -*-
"""
generate_risk_suggestions — 从 parser.py 拷出

拷贝来源: parser.py 第140-159行
"""

from typing import List


def generate_risk_suggestions(score: int, op_type: str, op_target: str, scope: str) -> List[str]:
    """拷贝自 parser.py 第140-159行"""
    suggestions = []
    if score <= 3:
        suggestions.append("操作安全，可继续执行")
    elif score <= 6:
        op_type_upper = op_type.upper() if op_type else ''
        if op_type_upper in ['DELETE', 'EXEC', 'COPY', 'MOVE']:
            suggestions.append("建议备份重要数据后再执行")
        if op_target and op_target.upper() == 'SYSTEM':
            suggestions.append("系统文件操作，请谨慎")
    elif score <= 8:
        suggestions.append("高风险操作，请确认目标路径")
        if scope and scope.upper() == 'SYSTEM':
            suggestions.append("避免系统级操作")
    else:
        suggestions.append("建议取消此操作")
        op_type_upper = op_type.upper() if op_type else ''
        if op_type_upper == 'DELETE':
            suggestions.append("删除操作过于危险，已被拦截")
    return suggestions
