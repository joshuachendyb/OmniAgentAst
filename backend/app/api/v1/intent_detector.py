"""
意图检测模块

从 chat_stream.py 和 chat_non_stream.py 提取出来的文件操作意图检测功能

【小沈重构 2026-05-25】
- 提取 FILE_INTENT_PATTERNS 为顶层常量
- 提取 _score_intent 辅助函数消除6次循环体重复
- 删除 YAGNI：weight = 1.0 死代码、matched_keywords 未使用列表
"""

from typing import Tuple, List

FILE_INTENT_PATTERNS = {
    "read": {
        "keywords": [
            '读取文件', '查看文件内容', '打开文件内容', '读文件内容', '显示文件内容',
            '读取', '查看文件', '打开文件', '读文件', '看文件',
            '看看文件', '看一下文件', '文件内容是什么', '查看一下文件',
            'read file', 'view file content', 'open file', 'show file content',
            'read the file', 'cat file',
        ]
    },
    "write": {
        "keywords": [
            '写入文件', '创建文件', '保存文件到', '写文件内容', '修改文件内容',
            '创建', '保存到', '写入', '新建文件', '新建文',
            '帮我写', '帮我创建', '新建一个文件', '创建一个文件',
            'write file', 'create file', 'save file', 'write to file', 'create a file',
        ]
    },
    "list": {
        "keywords": [
            '列出目录内容', '查看目录', '显示文件列表', '文件列表', '目录内容',
            '列出', '目录列表', '查看有哪些文件', '列出文件',
            '查看桌面', '桌面有什么', '桌面有哪些', '桌面目录',
            '看看桌面', '看一下桌面',
            '查看D盘', 'D盘有什么', 'D盘有哪些', '查看E盘', 'E盘有什么', 'E盘有哪些',
            '查看C盘', 'C盘有什么', 'C盘有哪些', '查看F盘', 'F盘有什么', 'F盘有哪些',
            '查看G盘', 'G盘有什么', 'G盘有哪些',
            '看看有什么', '有哪些文件', '有什么文件', '目录里有什么',
            '查看一下目录', '查看文件夹', '文件夹里有什么', '看看文件夹',
            'list directory', 'list files', 'show file list', 'ls -',
            'list all files', 'show files in', 'show desktop', 'what is on desktop',
        ]
    },
    "delete": {
        "keywords": [
            '删除文件', '删除这个文件', '删除指定文件', '移除文件', '删掉文件',
            '删除', '移除', '删掉', '清空', '删除目录',
            '帮我删除', '帮我删掉', '把文件删掉', '删掉这个',
            'delete file', 'remove file', 'delete this file', 'rm file',
            'delete the file', 'erase file',
        ]
    },
    "move": {
        "keywords": [
            '移动文件', '移动到', '重命名文件', '改名文件', '转移文件',
            '复制文件', '剪切文件',
            '移动', '重命名', '转移', '复制', '改名',
            '帮我移动', '帮我复制', '帮我重命名', '移到', '复制到',
            'move file', 'rename file', 'move to', 'copy file', 'mv file',
        ]
    },
    "search": {
        "keywords": [
            '搜索文件', '查找文件内容', '全文搜索', '搜索内容', '查找文件',
            '搜索', '查找', '搜文件', '搜索文件内容',
            '帮我搜索', '帮我查找', '找一下文件', '找找文件',
            'search file', 'search content', 'find file', 'grep file',
            'search in file', 'find content',
        ]
    }
}

CONFIDENCE_THRESHOLD = 0.2


def _score_intent(message: str, message_lower: str, keywords: List[str]) -> float:
    """对单个意图的所有关键词打分，返回累计分数
    
    小沈 2026-05-25 重构拆分
    """
    score = 0.0
    for keyword in keywords:
        if keyword.isascii():
            if keyword.lower() in message_lower:
                score += 1.0
        else:
            if keyword in message:
                score += 1.0
    return score


def detect_file_operation_intent(message: str) -> Tuple[bool, str, float]:
    """
    检测用户消息是否包含文件操作意图
    
    【重写】修复问题：
    1. 子串匹配 → 完整词匹配
    2. 关键词太宽泛 → 只保留明确操作词
    3. 去掉加分项
    4. 降低阈值到0.2（提高检测灵敏度）
    
    【小沈重构 2026-05-25】
    - 重构拆分：提取 FILE_INTENT_PATTERNS 常量 + _score_intent 辅助函数
    - 删除 YAGNI：weight = 1.0 死代码、matched_keywords 未使用列表
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型, 置信度0-1)
    """
    message_lower = message.lower().strip()
    
    best_intent = None
    best_score = 0.0
    
    for intent, config in FILE_INTENT_PATTERNS.items():
        score = _score_intent(message, message_lower, config["keywords"])
        if score > best_score:
            best_score = score
            best_intent = intent
    
    if best_score >= CONFIDENCE_THRESHOLD and best_intent is not None:
        return True, best_intent, min(best_score, 1.0)
    
    return False, "", 0.0
