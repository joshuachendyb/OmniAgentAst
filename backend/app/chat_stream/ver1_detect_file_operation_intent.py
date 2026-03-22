# -*- coding: utf-8 -*-
"""
ver1_detect_file_operation_intent.py

文件操作意图检测 - 版本1

从 chat2.py 抽取的原始意图检测函数。

Author: 小沈 - 2026-03-22
"""

import re
from typing import Optional, Tuple


def detect_file_operation_intent(message: str) -> Tuple[bool, str, float]:
    """
    检测用户消息是否包含文件操作意图（优化版）
    
    【重写】修复问题：
    1. 子串匹配 → 完整词匹配
    2. 关键词太宽泛 → 只保留明确操作词
    3. 去掉加分项
    4. 降低阈值到0.2（提高检测灵敏度）
    
    Args:
        message: 用户输入消息
        
    Returns:
        (是否文件操作, 操作类型, 置信度0-1)
    """
    message_lower = message.lower().strip()
    
    intent_patterns = {
        "read": {
            "keywords": [
                '读取文件', '查看文件内容', '打开文件内容', '读文件内容', '显示文件内容',
                '读取', '查看文件', '打开文件', '读文件', '看文件',
                '看看文件', '看一下文件', '文件内容是什么', '查看一下文件',
                'read file', 'view file content', 'open file', 'show file content',
                'read the file', 'cat file',
            ],
        },
        "write": {
            "keywords": [
                '写入文件', '创建文件', '保存文件到', '写文件内容', '修改文件内容',
                '创建', '保存到', '写入', '新建文件', '新建文',
                '帮我写', '帮我创建', '新建一个文件', '创建一个文件',
                'write file', 'create file', 'save file', 'write to file', 'create a file',
            ],
        },
        "list": {
            "keywords": [
                '列出目录内容', '查看目录', '显示文件列表', '文件列表', '目录内容',
                '列出', '目录列表', '查看有哪些文件', '列出文件',
                '查看桌面', '桌面有什么', '桌面有哪些', '桌面目录',
                '看看桌面', '看一下桌面', '查看D盘', 'D盘有什么',
                '看看有什么', '有哪些文件', '有什么文件', '目录里有什么',
                '查看一下目录', '查看文件夹', '文件夹里有什么', '看看文件夹',
                'list directory', 'list files', 'show file list', 'ls -',
                'list all files', 'show files in', 'show desktop', 'what is on desktop',
            ],
        },
        "delete": {
            "keywords": [
                '删除文件', '删除这个文件', '删除指定文件', '移除文件', '删掉文件',
                '删除', '移除', '删掉', '清空', '删除目录',
                '帮我删除', '帮我删掉', '把文件删掉', '删掉这个',
                'delete file', 'remove file', 'delete this file', 'rm file',
                'delete the file', 'erase file',
            ],
        },
        "move": {
            "keywords": [
                '移动文件', '移动到', '重命名文件', '改名文件', '转移文件',
                '复制文件', '剪切文件',
                '移动', '重命名', '转移', '复制', '改名',
                '帮我移动', '帮我复制', '帮我重命名', '移到', '复制到',
                'move file', 'rename file', 'move to', 'copy file', 'mv file',
            ],
        },
        "search": {
            "keywords": [
                '搜索文件', '查找文件内容', '全文搜索', '搜索内容', '查找文件',
                '搜索', '查找', '搜文件', '搜索文件内容',
                '帮我搜索', '帮我查找', '找一下文件', '找找文件',
                'search file', 'search content', 'find file', 'grep file',
                'search in file', 'find content',
            ],
        }
    }
    
    best_intent = None
    best_score = 0.0
    
    for intent, config in intent_patterns.items():
        score = 0.0
        matched_keywords = []
        
        for keyword in config["keywords"]:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                score += 1.0
                matched_keywords.append(keyword)
        
        weight = 1.0
        score *= weight
        
        if score > best_score:
            best_score = score
            best_intent = intent
    
    CONFIDENCE_THRESHOLD = 0.2
    
    if best_score >= CONFIDENCE_THRESHOLD and best_intent is not None:
        return True, best_intent, min(best_score, 1.0)
    
    return False, "", 0.0


def extract_file_path(message: str) -> Optional[str]:
    """
    从消息中提取文件路径
    
    简单的路径提取逻辑，支持常见格式
    """
    path_patterns = [
        r'["\']([a-zA-Z]:[/\\][^"\']+)["\']',
        r'["\']([/\\][^"\']+)["\']',
        r'["\'](\.[/\\][^"\']+)["\']',
        r'(?:文件|file)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
        r'(?:路径|path)["\']?\s*[:=]\s*["\']?([^"\'\s]+)',
    ]
    
    for pattern in path_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    
    words = message.split()
    for word in words:
        word = word.strip('"\'，,.;:')
        if ('/' in word or '\\' in word) and len(word) > 2:
            return word
    
    return None


__all__ = [
    "detect_file_operation_intent",
    "extract_file_path",
]
