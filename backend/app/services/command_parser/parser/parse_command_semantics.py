# -*- coding: utf-8 -*-
"""
parse_command_semantics — 从 parser.py 拷出

拷贝来源: parser.py 第135-137行
"""

from typing import Dict, Any

from app.services.command_parser.parser.get_command_parser import get_command_parser


def parse_command_semantics(command: str) -> Dict[str, Any]:
    """拷贝自 parser.py 第135-137行"""
    parser = get_command_parser()
    return parser.parse(command)
