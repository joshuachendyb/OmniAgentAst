"""
CommandParser — 命令语义解析器

包含:
- CommandParser: 命令语义解析器（方案4）
- get_command_parser: 获取单例解析器
- parse_command_semantics: 解析命令语义
- generate_risk_suggestions: 建议生成（方案5）

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md

创建时间：2026-04-20
编写人：小沈
"""

import re
from typing import Optional, List, Dict, Any


# =============================================================================
# CommandParser — 原 command_security.py 内联（小欧 2026-05-27）
# =============================================================================

class CommandParser:
    """
    命令语义解析器

    功能：
    1. 解析命令结构（源路径、目标路径）
    2. 识别操作方向（读取、写入）
    3. 识别操作数量（单个、批量）
    """

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
            return self._empty_result()
        result = {
            'operation': None, 'sources': [], 'targets': [],
            'direction': None, 'quantity': 'single'
        }
        result['operation'] = self._parse_operation(command)
        paths = self._parse_paths(command)
        result['sources'] = paths.get('sources', [])
        result['targets'] = paths.get('targets', [])
        result['direction'] = self._parse_direction(result['operation'])
        result['quantity'] = self._parse_quantity(command)
        return result

    def _empty_result(self) -> Dict[str, Any]:
        return {'operation': None, 'sources': [], 'targets': [], 'direction': None, 'quantity': 'single'}

    def _parse_operation(self, command: str) -> Optional[str]:
        command_lower = command.lower()
        for op, patterns in self.operation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return op
        return None

    def _parse_paths(self, command: str) -> Dict[str, List[str]]:
        sources, targets = [], []
        for pattern, ptype in self.cn_patterns:
            match = re.search(pattern, command)
            if match:
                src = match.group(1).strip()
                tgt = match.group(2).strip() if match.lastindex >= 2 else ''
                if src: sources.append(src)
                if tgt: targets.append(tgt)
                return {'sources': sources, 'targets': targets}
        for pattern, ptype in self.en_patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                src = match.group(1).strip()
                tgt = match.group(2).strip() if match.lastindex >= 2 else ''
                if src: sources.append(src)
                if tgt: targets.append(tgt)
                return {'sources': sources, 'targets': targets}
        parts = command.split()
        if len(parts) >= 2:
            cmd_words = ['cp', 'copy', 'mv', 'move', 'rm', 'del', 'cat', 'mkdir', 'touch', 'echo']
            found_cmd = False
            for part in parts:
                if part.lower() in cmd_words:
                    found_cmd = True; continue
                if found_cmd:
                    if not sources: sources.append(part)
                    elif not targets: targets.append(part)
        return {'sources': sources, 'targets': targets}

    def _parse_direction(self, operation: Optional[str]) -> Optional[str]:
        if operation in ['copy', 'move', 'create', 'update']:
            return 'write'
        elif operation == 'delete':
            return 'delete'
        elif operation == 'read':
            return 'read'
        return None

    def _parse_quantity(self, command: str) -> str:
        batch_keywords = [r'所有', r'全部', r'批量', r'\*', r'-r', r'-rf', r'/s']
        for keyword in batch_keywords:
            if re.search(keyword, command):
                return 'batch'
        return 'single'


_command_parser: Optional[CommandParser] = None


def get_command_parser() -> CommandParser:
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser


def parse_command_semantics(command: str) -> Dict[str, Any]:
    parser = get_command_parser()
    return parser.parse(command)


def generate_risk_suggestions(score: int, op_type: str, op_target: str, scope: str) -> List[str]:
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
