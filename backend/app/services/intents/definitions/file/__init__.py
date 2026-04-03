# -*- coding: utf-8 -*-
"""
Intents/Definitions/File 模块 - File Intent 定义和统计

【创建时间】2026-03-21 小沈
【迁移说明】
从 session.py 和架构设计文档迁移而来
- file_stats.py: file 意图特有统计字段
- file_intent.py: file 意图定义对象

Author: 小沈 - 2026-03-21
"""

from app.services.intents.definitions.file.file_stats import (
    FileSessionStats,
)

from app.services.intents.definitions.file.file_intent import (
    FileIntent,
)

__all__ = [
    "FileSessionStats",
    "FileIntent",
]
