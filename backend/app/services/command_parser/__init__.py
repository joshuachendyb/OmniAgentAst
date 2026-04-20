"""
命令解析器模块

包含:
- CommandParser: 命令语义解析器（方案4）
- parse_operation_type_v2: 操作类型解析（方案3）
- parse_operation_target_v2: 操作对象解析（方案2）
- calculate_pattern_confidence: 置信度计算
- parse_impact_scope: 影响范围解析
- generate_risk_suggestions: 建议生成（方案5）
- CRSS评分权重配置

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md

创建时间：2026-04-20
编写人：小沈
"""

from app.services.command_parser.command_security import (
    CommandParser,
    get_command_parser,
    parse_command_semantics,
    generate_risk_suggestions,
    OPERATION_WEIGHTS,
    TARGET_WEIGHTS,
    SCOPE_MULTIPLIERS,
)

from app.services.command_parser.parse_operation import (
    parse_operation_type,
    parse_operation_type_v2,
)

from app.services.command_parser.parse_target import (
    parse_operation_target,
    parse_operation_target_v2,
    calculate_pattern_confidence,
)

from app.services.command_parser.parse_scope import (
    parse_impact_scope,
    get_scope_multiplier,
)

__all__ = [
    # CommandParser
    'CommandParser',
    'get_command_parser',
    'parse_command_semantics',
    # 操作类型
    'parse_operation_type',
    'parse_operation_type_v2',
    # 操作对象
    'parse_operation_target',
    'parse_operation_target_v2',
    'calculate_pattern_confidence',
    # 影响范围
    'parse_impact_scope',
    'get_scope_multiplier',
    # 建议生成
    'generate_risk_suggestions',
    # CRSS配置
    'OPERATION_WEIGHTS',
    'TARGET_WEIGHTS',
    'SCOPE_MULTIPLIERS',
]