"""
消息意图分类器

用于识别用户消息的意图类型：问答类 or 动作类
"""

from enum import Enum
from typing import Tuple, Optional
import re


class IntentType(Enum):
    """意图类型枚举"""
    QUERY = "query"  # 问答类
    ACTION = "action"  # 动作类


class ActionType(Enum):
    """动作类型枚举"""
    FILE_OPERATION = "file_operation"  # 文件操作
    DATABASE_OPERATION = "database_operation"  # 数据库操作（预留）
    API_CALL = "api_call"  # API 调用（预留）
    SYSTEM_COMMAND = "system_command"  # 系统命令（预留）
    UNKNOWN = "unknown"  # 未知动作


class IntentClassifier:
    """
    意图分类器
    
    分类逻辑：
    1. 问答类：询问知识、概念、解释，不需要执行操作
    2. 动作类：需要执行具体操作，会改变系统状态
    """
    
    # 动作类关键词模式
    ACTION_PATTERNS = {
        ActionType.FILE_OPERATION: {
            "keywords": [
                # 文件读取
                '读取文件', '查看文件', '打开文件', '读文件', '看文件内容', '显示文件内容',
                'read file', 'view file', 'open file', 'show file', 'display file',
                # 文件写入
                '写入文件', '创建文件', '保存文件', '写文件', '修改文件', '更新文件',
                'write file', 'create file', 'save file', 'update file', 'edit file',
                # 文件管理
                '删除文件', '复制文件', '移动文件', '重命名文件', '列出文件',
                'delete file', 'copy file', 'move file', 'rename file', 'list files',
                # 通用动词
                '写入', '创建', '保存', '写', '修改', '更新', '编辑', '删除', '复制', '移动', '重命名', '列出',
                'write', 'create', 'save', 'edit', 'update', 'delete', 'copy', 'move', 'rename', 'list',
                # 【新增】通用文件操作相关词
                '查看', '浏览', '搜索', '找文件', '看目录', '看文件夹',
                '桌面', '文件夹', '目录', '文件列表', '有什么文件', '类型', '整理',
                # 【新增】口语化表达
                '看看有啥', '都有啥', '有啥', '帮我看看', '帮我找找',
                '里面有什么', '看看都有啥', '看看有什么', '分析分析',
                # 【新增】分析整理类
                '分析', '分析一下', '文件类型', '按类型整理', '分类整理', '整理文件', '帮我整理', '按类型分', '都有什么类型',
                # 【新增】目录操作
                '打开目录', '进入目录', '遍历目录', '切换目录',
                # 【新增】文件传输
                '压缩', '解压', '导出', '导入', '上传', '下载',
                # 【新增】盘符关键词（通用匹配，自动与动作词组合）【小强添加 2026-03-19】
                'A盘', 'B盘', 'C盘', 'D盘', 'E盘', 'F盘', 'G盘', 'H盘', 'I盘', 'J盘',
                'a盘', 'b盘', 'c盘', 'd盘', 'e盘', 'f盘', 'g盘', 'h盘', 'i盘', 'j盘',
                # 【新增】通用文件相关词（与动作词自动组合）
                '文件有哪些', '有哪些文件', '文件有什么', '有什么文件', '文件列表', '查看文件', '列出文件', '查看文件夹',
                # 【新增】"文件"关键词（非常通用，自动与其他词组合）
                '文件',
                # 【新增】通用"有什么"系列（自动与盘符/目录组合）
                '看看有什么', '有什么', '有什么东西', '东西有什么',
            ],
            "file_extensions": ['.txt', '.md', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.xml', '.csv'],
        },
        # 预留其他动作类型的模式
        ActionType.DATABASE_OPERATION: {
            "keywords": [
                '查询数据库', '插入数据', '更新数据', '删除数据',
                'query database', 'insert data', 'update data', 'delete data',
            ],
        },
        ActionType.API_CALL: {
            "keywords": [
                '调用 API', '发送请求', 'HTTP 请求',
                'call api', 'send request', 'http request',
            ],
        },
        ActionType.SYSTEM_COMMAND: {
            "keywords": [
                '执行命令', '运行命令', '命令行', '终端',
                'execute command', 'run command', 'command line', 'terminal',
            ],
        },
    }
    
    # 问答类关键词（用于排除）
    QUERY_KEYWORDS = [
        '是什么', '为什么', '怎么做', '如何', '什么', '怎么', '为什么',
        'what', 'why', 'how', 'explain', 'describe', 'tell me',
        '请解释', '请说明', '告诉我', '介绍一下',
    ]
    
    @classmethod
    def classify(cls, message: str) -> Tuple[IntentType, Optional[ActionType], float]:
        """
        分类用户消息
        
        Args:
            message: 用户输入消息
            
        Returns:
            (意图类型，动作类型，置信度)
            - 如果是问答类：(IntentType.QUERY, None, confidence)
            - 如果是动作类：(IntentType.ACTION, ActionType.XXX, confidence)
        """
        message_lower = message.lower().strip()
        
        # 检查是否是动作类
        action_type, action_confidence = cls._detect_action_intent(message_lower)
        
        if action_type and action_confidence > 0.4:
            # 是动作类
            return IntentType.ACTION, action_type, action_confidence
        else:
            # 是问答类
            query_confidence = cls._detect_query_intent(message_lower)
            return IntentType.QUERY, None, query_confidence
    
    @classmethod
    def _detect_action_intent(cls, message: str) -> Tuple[Optional[ActionType], float]:
        """
        检测动作类意图
        
        Returns:
            (动作类型，置信度)
        """
        best_action_type = None
        best_confidence = 0.0
        
        for action_type, patterns in cls.ACTION_PATTERNS.items():
            confidence = cls._match_action_pattern(message, patterns)
            if confidence > best_confidence:
                best_confidence = confidence
                best_action_type = action_type
        
        return best_action_type, best_confidence
    
    @classmethod
    def _match_action_pattern(cls, message: str, patterns: dict) -> float:
        """
        匹配动作模式，返回置信度 (0-1)
        """
        score = 0.0
        
        # 关键词匹配
        keywords = patterns.get("keywords", [])
        for keyword in keywords:
            if keyword in message:
                score += 0.3
        
        # 文件扩展名匹配（仅文件操作）
        if "file_extensions" in patterns:
            for ext in patterns["file_extensions"]:
                if ext in message:
                    score += 0.2
        
        # 正则匹配：动词 + 文件名模式
        verb_file_pattern = r'(创建 | 打开 | 读取 | 写入 | 删除 | 修改)\s*(文件 | 文件.)?'
        if re.search(verb_file_pattern, message):
            score += 0.5
        
        # 归一化到 0-1
        return min(1.0, score)
    
    @classmethod
    def _detect_query_intent(cls, message: str) -> float:
        """
        检测问答类意图，返回置信度 (0-1)
        """
        score = 0.0
        
        # 疑问词匹配
        for keyword in cls.QUERY_KEYWORDS:
            if keyword in message:
                score += 0.3
        
        # 问号匹配
        if '?' in message or '？' in message:
            score += 0.2
        
        # 句式匹配：请 XX、帮我 XX
        if message.startswith(('请', '帮我', 'please', 'help me')):
            score += 0.1
        
        return min(1.0, score)


# 便捷函数
def classify_intent(message: str) -> Tuple[IntentType, Optional[ActionType], float]:
    """
    分类用户消息意图
    
    Args:
        message: 用户输入消息
        
    Returns:
        (意图类型，动作类型，置信度)
    """
    return IntentClassifier.classify(message)


def detect_file_operation_intent(message: str) -> Tuple[bool, str, float]:
    """
    检测用户消息是否包含文件操作意图
    
    引用 classify_intent 函数，使用子串匹配逻辑
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型, 置信度0-1)
    """
    from app.utils.logger import logger
    
    intent_type, action_type, confidence = classify_intent(message)
    
    # 【小沈添加日志 2026-03-22】记录输入输出
    logger.info(
        f"[IntentClassifier] detect_file_operation_intent - "
        f"input: '{message}' -> "
        f"intent_type: '{intent_type}', action_type: '{action_type}', confidence: {confidence:.4f}"
    )
    
    if intent_type == IntentType.ACTION and action_type == ActionType.FILE_OPERATION:
        return True, "file", confidence
    
    return False, "", 0.0
