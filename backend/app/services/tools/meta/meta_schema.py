# -*- coding: utf-8 -*-
"""
Meta 工具 Schema - Pydantic 输入模型

【2026-06-12 小沈】删除ToolHelpInput/PipelineInput(YAGNI),仅保留ToolSearchInput
"""

from pydantic import BaseModel, Field


class ToolSearchInput(BaseModel):
    query: str = Field(..., description="关键词搜索。按工具名/description分词匹配,支持中英文。如 '查找重复文件' '读取Excel数据'")


__all__ = ["ToolSearchInput"]
