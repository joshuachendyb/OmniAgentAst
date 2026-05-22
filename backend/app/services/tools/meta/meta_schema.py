# -*- coding: utf-8 -*-
"""
Meta 工具 Schema - Pydantic 输入模型

【2026-05-17 小沈】新建
"""

from pydantic import BaseModel, Field
from typing import Optional


class ToolHelpInput(BaseModel):
    """tool_help 工具的输入参数 - 小沈 2026-05-17"""
    tool_name: str = Field(..., description="要查询的工具名称。如 read_csv, search_files, get_time")


class ToolSearchInput(BaseModel):
    """tool_search 工具的输入参数 - 小沈 2026-05-17"""
    query: str = Field(..., description="自然语言描述需求。如 '查找重复文件' '读取Excel数据'")


class PipelineInput(BaseModel):
    """pipeline 工具的输入参数 - 小沈 2026-05-17, 2026-05-22 新增timeout_per_step"""
    steps: str = Field(..., description='JSON格式工具步骤数组。每个元素: {"tool":"工具名"(必填), "params":{参数字典}(可选)}。前一步输出data自动注入后一步params。如 [{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]')
    stop_on_error: bool = Field(default=True, description="某步失败时是否停止管道")
    timeout_per_step: int = Field(default=60, description="每步执行超时时间（秒），超时则报错停止管道。默认60秒")


__all__ = ["ToolHelpInput", "ToolSearchInput", "PipelineInput"]
