"""
命令解析器模块

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md

创建时间：2026-04-20
编写人：小沈
"""

from app.services.command_parser.parse_operation import (
    parse_operation_type,
    parse_operation_type_v2,
    OPERATION_WEIGHTS,
)

from app.services.command_parser.parse_target import (
    parse_operation_target,
    parse_operation_target_v2,
    calculate_pattern_confidence,
    TARGET_WEIGHTS,
)

from app.services.command_parser.parse_scope import (
    parse_impact_scope,
    get_scope_multiplier,
    SCOPE_MULTIPLIERS,
)

from app.services.command_parser.parser import (
    CommandParser,
    get_command_parser,
    parse_command_semantics,
    generate_risk_suggestions,
)


__all__ = [
    'CommandParser',
    'get_command_parser',
    'parse_command_semantics',
    'parse_operation_type',
    'parse_operation_type_v2',
    'parse_operation_target',
    'parse_operation_target_v2',
    'calculate_pattern_confidence',
    'parse_impact_scope',
    'get_scope_multiplier',
    'generate_risk_suggestions',
    'OPERATION_WEIGHTS',
    'TARGET_WEIGHTS',
    'SCOPE_MULTIPLIERS',
]
