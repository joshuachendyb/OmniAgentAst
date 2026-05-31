"""
CommandParser — 命令语义解析器 — 核心类

从 parser.py 拆出，遵循 SRP：
- parse_operation / parse_paths / parse_direction / parse_quantity → 独立文件
- 本文件只保留 CommandParser 类骨架

Author: 小沈 - 2026-04-20
"""

from typing import Optional, List, Dict, Any

from app.services.command_parser.parser.parse_operation import parse_operation
from app.services.command_parser.parser.parse_paths import parse_paths
from app.services.command_parser.parser.parse_direction import parse_direction
from app.services.command_parser.parser.parse_quantity import parse_quantity


class CommandParser:
    """命令语义解析器 — 只保留骨架"""

    def __init__(self):
        self.operation_patterns = {
            'copy': [r'复制', r'copy(?!\s+-r)', r'\bcp\b'],
            'move': [r'移动', r'\bmv\b', r'\bmove\b'],
            'delete': [r'删除', r'delete', r'\brm\b', r'\bdel\b', r'\brdir\b'],
            'read': [r'读取', r'查看', r'\bcat\b', r'\bread\b', r'\btype\b'],
            'create': [r'创建', r'新建', r'\bmkdir\b', r'\btouch\b'],
            'update': [r'修改', r'编辑', r'\bsed\b', r'\becho\b'],
        }
        self.cn_patterns = [
            (r'(?:将|把)\s*(.+?)\s*(?:复制|移动|删除|读取|查看)\s*(?:到|至|)\s*(.+)', 'cn_direct'),
            (r'(.+?)\s*(?:复制|移动|拷贝)\s+(?:到|至)?\s*(.+)', 'cn_verb'),
        ]
        self.en_patterns = [
            (r'(?:\bcp\b|\bcopy\b)\s+(.+?)\s+(?:to|in|\|)\s*(.+)', 'en_copy'),
            (r'(?:\bmv\b|\bmove\b)\s+(.+?)\s+(?:to|)\s*(.+)', 'en_move'),
        ]

    def parse(self, command: str) -> Dict[str, Any]:
        if not command or not command.strip():
            return {'operation': None, 'sources': [], 'targets': [], 'direction': None, 'quantity': 'single'}
        result = {
            'operation': None, 'sources': [], 'targets': [],
            'direction': None, 'quantity': 'single'
        }
        result['operation'] = parse_operation(command, self.operation_patterns)
        paths = parse_paths(command, self.cn_patterns, self.en_patterns)
        result['sources'] = paths.get('sources', [])
        result['targets'] = paths.get('targets', [])
        result['direction'] = parse_direction(result['operation'])
        result['quantity'] = parse_quantity(command)
        return result
