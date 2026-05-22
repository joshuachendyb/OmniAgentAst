"""
命令安全解析器

包含：
1. CommandParser: 命令语义解析器（方案4）
2. parse_operation_type_v2: 操作类型解析（方案3）
3. parse_operation_target_v2: 操作对象解析（方案2）
4. calculate_pattern_confidence: 置信度计算（方案2）
5. parse_impact_scope: 影响范围解析
6. generate_risk_suggestions: 建议生成（方案5）

设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md

创建时间：2026-04-20
编写人：小沈
"""

import re
import math
from typing import Optional, List, Dict, Any, Tuple


# =============================================================================
# CRSS评分权重配置（供v2函数使用）
# =============================================================================

OPERATION_WEIGHTS = {
    'READ': {'min': 0, 'max': 2, 'default': 1, 'keywords': ['cat', 'ls', 'grep', '查看', '读取', 'type', 'dir', '运行']},
    'CREATE': {'min': 2, 'max': 4, 'default': 3, 'keywords': ['mkdir', 'touch', '创建', '新建', 'md']},
    'UPDATE': {'min': 4, 'max': 7, 'default': 5, 'keywords': ['edit', 'sed', '修改', '编辑', '更新', 'echo', 'write']},
    'DELETE': {'min': 6, 'max': 10, 'default': 8, 'keywords': ['rm', 'del', 'delete', '删除', 'remove', '清除', 'rmdir', 'rd']},
    'COPY': {'min': 2, 'max': 5, 'default': 3, 'keywords': ['copy', 'cp', '复制', '拷贝']},
    'MOVE': {'min': 2, 'max': 5, 'default': 3, 'keywords': ['move', 'mv', '移动']},
    'EXEC': {'min': 5, 'max': 10, 'default': 7, 'keywords': ['sudo', 'run', 'exec', '执行', 'start']},
}

TARGET_WEIGHTS = {
    'TEMP': {'min': 0, 'max': 4, 'default': 3, 'patterns': [r'\.tmp$', r'\.cache', r'^temp[/\\]', r'temp[/\\]', r'\.log$', r'log[/\\]', r'\*.tmp']},
    'USER': {'min': 3, 'max': 5, 'default': 4, 'patterns': [r'~/', r'/home/', r'文档[/\\]', r'用户', r'documents', r'users?[/\\]']},
    'PROJECT': {'min': 3, 'max': 6, 'default': 3, 'patterns': [r'src[/\\]', r'app[/\\]', r'backend[/\\]', r'frontend[/\\]', r'\.py', r'\.js', r'\.ts', r'tests[/\\]', r'config[/\\]', r'\.git']},
    'SYSTEM': {'min': 8, 'max': 10, 'default': 9, 'patterns': [r'C:\\Windows', r'/bin', r'/etc', r'/sbin', r'/usr', r'系统', r'windows[/\\]system32', r'registry', r'密码', r'shadow', r'passwd', r'SAM', r'配置', r'注册表']},
}

SCOPE_MULTIPLIERS = {
    'SINGLE_FILE': 1.1,
    'DIRECTORY': 1.45,
    'CROSS_DIR': 1.5,
    'SYSTEM': 3.0,
}

SCOPE_PATTERNS = {
    'SINGLE_FILE': [r'^[^*?]+\.[a-zA-Z0-9]+$', r'^[^*?/]+$'],
    'DIRECTORY': [r'[/\\]$', r'\$'],
    'CROSS_DIR': [r'\*', r'\?'],
    'SYSTEM': [r'^-rf$', r'^/s$', r'^/q$', r'^C:\\$', r'^/$'],
}


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
            'move': [r'移动', r'\bmv\b', r'\bmove\b'],
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


# =============================================================================
# 方案5：评分可解释性 - 建议生成
# =============================================================================

def generate_risk_suggestions(score: int, op_type: str, op_target: str, scope: str) -> List[str]:
    """
    根据评分生成建议
    
    设计文档：CRSS评分系统深度分析与改进方案-2026-04-20.md 3.5节
    
    Args:
        score: 风险分数
        op_type: 操作类型
        op_target: 操作对象
        scope: 影响范围
        
    Returns:
        List[str]: 建议列表
    """
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