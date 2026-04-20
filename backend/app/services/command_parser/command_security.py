"""
命令语义解析器

功能：
1. 解析命令结构（源路径、目标路径）
2. 识别操作方向（读取、写入）
3. 识别操作数量（单个、批量）

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md 3.4节

创建时间：2026-04-20
编写人：小沈
"""

import re
from typing import Optional, List, Dict, Any


class CommandParser:
    """
    命令语义解析器
    
    功能：
    1. 解析命令结构（源路径、目标路径）
    2. 识别操作方向（读取、写入）
    3. 识别操作数量（单个、批量）
    """
    
    def __init__(self):
        # 操作类型识别模式
        self.operation_patterns = {
            'copy': [r'复制', r'copy(?!\s+-r)', r'\bcp\b'],
            'move': [r'移动', r'\bmv\b'],
            'delete': [r'删除', r'delete', r'\brm\b', r'\bdel\b', r'\brdir\b'],
            'read': [r'读取', r'查看', r'\bcat\b', r'\bread\b', r'\btype\b'],
            'create': [r'创建', r'新建', r'\bmkdir\b', r'\btouch\b'],
            'update': [r'修改', r'编辑', r'\bsed\b', r'\becho\b'],
        }
        
        # 中文命令模式："将A复制到B"、"把A移动到B"
        self.cn_patterns = [
            (r'(?:将|把)\s*(.+?)\s*(?:复制|移动|删除|读取|查看)\s*(?:到|至|)\s*(.+)', 'cn_direct'),
            (r'(.+?)\s*(?:复制|移动|拷贝)\s+(?:到|至)?\s*(.+)', 'cn_verb'),
        ]
        
        # 英文命令模式
        self.en_patterns = [
            (r'(?:\bcp\b|\bcopy\b)\s+(.+?)\s+(?:to|in|\|)\s*(.+)', 'en_copy'),
            (r'(?:\bmv\b|\bmove\b)\s+(.+?)\s+(?:to|)\s*(.+)', 'en_move'),
        ]
    
    def parse(self, command: str) -> Dict[str, Any]:
        """
        解析命令语义
        
        Args:
            command: 待解析的命令
            
        Returns:
            dict: 解析结果
                - operation: 操作类型 (copy/move/delete/read/create/update)
                - sources: 源路径列表
                - targets: 目标路径列表
                - direction: 操作方向 (read/write/delete)
                - quantity: 操作数量 (single/batch)
        """
        if not command or not command.strip():
            return self._empty_result()
        
        result = {
            'operation': None,
            'sources': [],
            'targets': [],
            'direction': None,
            'quantity': 'single'
        }
        
        # 1. 识别操作类型
        result['operation'] = self._parse_operation(command)
        
        # 2. 解析路径（源和目标）
        paths = self._parse_paths(command)
        result['sources'] = paths.get('sources', [])
        result['targets'] = paths.get('targets', [])
        
        # 3. 识别操作方向
        result['direction'] = self._parse_direction(result['operation'])
        
        # 4. 识别操作数量
        result['quantity'] = self._parse_quantity(command)
        
        return result
    
    def _empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'operation': None,
            'sources': [],
            'targets': [],
            'direction': None,
            'quantity': 'single'
        }
    
    def _parse_operation(self, command: str) -> Optional[str]:
        """识别操作类型"""
        command_lower = command.lower()
        
        for op, patterns in self.operation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, command_lower):
                    return op
        
        return None
    
    def _parse_paths(self, command: str) -> Dict[str, List[str]]:
        """解析源路径和目标路径"""
        sources = []
        targets = []
        
        # 尝试中文模式匹配
        for pattern, ptype in self.cn_patterns:
            match = re.search(pattern, command)
            if match:
                src = match.group(1).strip()
                tgt = match.group(2).strip() if match.lastindex >= 2 else ''
                
                if src:
                    sources.append(src)
                if tgt:
                    targets.append(tgt)
                
                return {'sources': sources, 'targets': targets}
        
        # 尝试英文模式匹配
        for pattern, ptype in self.en_patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                src = match.group(1).strip()
                tgt = match.group(2).strip() if match.lastindex >= 2 else ''
                
                if src:
                    sources.append(src)
                if tgt:
                    targets.append(tgt)
                
                return {'sources': sources, 'targets': targets}
        
        # 兜底：尝试简单分割（空格分割）
        parts = command.split()
        if len(parts) >= 2:
            cmd_words = ['cp', 'copy', 'mv', 'move', 'rm', 'del', 'cat', 'mkdir', 'touch', 'echo']
            found_cmd = False
            for part in parts:
                if part.lower() in cmd_words:
                    found_cmd = True
                    continue
                if found_cmd:
                    if not sources:
                        sources.append(part)
                    elif not targets:
                        targets.append(part)
        
        return {'sources': sources, 'targets': targets}
    
    def _parse_direction(self, operation: Optional[str]) -> Optional[str]:
        """识别操作方向"""
        if operation in ['copy', 'move', 'create', 'update']:
            return 'write'
        elif operation == 'delete':
            return 'delete'
        elif operation == 'read':
            return 'read'
        return None
    
    def _parse_quantity(self, command: str) -> str:
        """识别操作数量"""
        batch_keywords = [r'所有', r'全部', r'批量', r'\*', r'-r', r'-rf', r'/s']
        
        for keyword in batch_keywords:
            if re.search(keyword, command):
                return 'batch'
        
        return 'single'


# 全局命令解析器实例
_command_parser: Optional[CommandParser] = None

def get_command_parser() -> CommandParser:
    """获取命令解析器实例（单例）"""
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser


def parse_command_semantics(command: str) -> Dict[str, Any]:
    """
    解析命令语义（便捷函数）
    
    Args:
        command: 待解析的命令
        
    Returns:
        dict: 解析结果
    """
    parser = get_command_parser()
    return parser.parse(command)