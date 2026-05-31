# -*- coding: utf-8 -*-
"""
get_command_parser — 从 parser.py 拷出

拷贝来源: parser.py 第125-132行
"""

from typing import Optional

from app.services.command_parser.parser.parser_core import CommandParser

_command_parser: Optional[CommandParser] = None


def get_command_parser() -> CommandParser:
    """拷贝自 parser.py 第125-132行"""
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser
