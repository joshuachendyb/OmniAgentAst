# -*- coding: utf-8 -*-
"""
File Intent 统计数据模块 (File Intent Statistics)

【创建时间】2026-03-21 小沈
【迁移说明】
从 session.py 和 models/file_operations/__init__.py 提取 file 意图特有的统计字段
迁移到 intents/definitions/file/

file 意图特有统计字段：
- rolled_back_count: 已回滚操作数
- report_generated: 是否已生成可视化报告
- report_path: 报告文件路径

Author: 小沈 - 2026-03-21
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FileSessionStats(BaseModel):
    """
    file 意图特有统计
    
    记录 file 意图会话特有的统计信息。
    通用统计字段（如 total_operations, success_count, failed_count）
    放在 SessionRecord 中，此处只放 file 特有的字段。
    """
    rolled_back_count: int = Field(
        default=0, 
        description="已回滚操作数"
    )
    report_generated: bool = Field(
        default=False, 
        description="是否已生成可视化报告"
    )
    report_path: Optional[str] = Field(
        default=None, 
        description="报告文件路径"
    )
    report_type: Optional[str] = Field(
        default=None,
        description="报告类型: text/json/html/mermaid"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "rolled_back_count": 2,
                "report_generated": True,
                "report_path": "C:/Users/test/.omniagent/reports/sess-abc123.html",
                "report_type": "html"
            }
        }


__all__ = [
    "FileSessionStats",
]
