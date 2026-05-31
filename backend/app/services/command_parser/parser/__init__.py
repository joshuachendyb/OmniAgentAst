# -*- coding: utf-8 -*-
"""
parser — 从 parser.py 拆出的职责

- parse_operation: 命令解析
- parse_paths: 命令解析
- parse_direction: 命令解析
- parse_quantity: 命令解析
- get_command_parser: 工厂单例
- parse_command_semantics: 对外接口
- generate_risk_suggestions: 风险建议
"""

from app.services.command_parser.parser.parse_operation import parse_operation
from app.services.command_parser.parser.parse_paths import parse_paths
from app.services.command_parser.parser.parse_direction import parse_direction
from app.services.command_parser.parser.parse_quantity import parse_quantity
from app.services.command_parser.parser.get_command_parser import get_command_parser
from app.services.command_parser.parser.parse_command_semantics import parse_command_semantics
from app.services.command_parser.parser.generate_risk_suggestions import generate_risk_suggestions
from app.services.command_parser.parser.parser_core import CommandParser

__all__ = [
    "CommandParser",
    "parse_operation", "parse_paths", "parse_direction", "parse_quantity",
    "get_command_parser", "parse_command_semantics", "generate_risk_suggestions",
]
