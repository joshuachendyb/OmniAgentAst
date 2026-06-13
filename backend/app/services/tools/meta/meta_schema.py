# -*- coding: utf-8 -*-
"""
Meta 工具 Schema - Pydantic 输入模型

【2026-06-12 小沈】删除ToolHelpInput/PipelineInput(YAGNI),仅保留ToolSearchInput
"""

from pydantic import BaseModel, Field


class ToolSearchInput(BaseModel):
    query: str = Field(..., description="先用此工具搜索未加载的工具。BM25全文检索，支持中英文混合。例如:'读取Word文档' 'SQL查询 数据库' '生成图表' '搜索文件' '压缩解压'。输入1-3个核心关键词效果最好。")


__all__ = ["ToolSearchInput"]
