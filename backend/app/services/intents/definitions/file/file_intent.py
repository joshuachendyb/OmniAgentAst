# -*- coding: utf-8 -*-
"""
File Intent 意图定义模块 (File Intent Definition)

【创建时间】2026-03-21 小沈
【迁移说明】
根据架构设计文档 4.1 节，创建 file 意图定义对象
迁移到 intents/definitions/file/

意图定义包含：
- name: 意图名称 ("file")
- description: 意图描述
- keywords: 关键词列表（用于分类）
- tools: 关联的工具名称列表
- safety_checker: 安全检查器名称

Author: 小沈 - 2026-03-21
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FileIntent(BaseModel):
    """
    file 意图定义
    
    定义文件操作意图的元数据，包括：
    - 意图名称和描述
    - 用于意图分类的关键词
    - 关联的文件操作工具
    - 安全检查器配置
    """
    name: str = Field(
        default="file",
        description="意图名称"
    )
    description: str = Field(
        default="文件读写、目录管理、文件搜索等文件操作",
        description="意图描述"
    )
    keywords: List[str] = Field(
        default_factory=lambda: [
            "文件", "读取", "写入", "删除", "移动", "复制",
            "目录", "文件夹", "搜索", "查找",
            "file", "read", "write", "delete", "move", "copy",
            "path", "directory", "folder", "search", "find",
            "open", "save", "create", "edit"
        ],
        description="意图分类关键词列表"
    )
    tools: List[str] = Field(
        default_factory=lambda: [
            "read_file",
            "write_file",
            "list_directory",
            "delete_file",
            "move_file",
            "search_files",
            "search_file_content",
            "generate_report"
        ],
        description="关联的文件操作工具名称列表"
    )
    safety_checker: str = Field(
        default="file_safety",
        description="安全检查器名称"
    )
    prompt_template: Optional[str] = Field(
        default=None,
        description="可选的 Prompt 模板路径"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "file",
                "description": "文件读写、目录管理、文件搜索等文件操作",
                "keywords": ["文件", "读取", "写入", "删除", "移动", "搜索"],
                "tools": ["read_file", "write_file", "list_directory", "delete_file", "move_file", "search_files", "search_file_content", "generate_report"],
                "safety_checker": "file_safety"
            }
        }


__all__ = [
    "FileIntent",
]
