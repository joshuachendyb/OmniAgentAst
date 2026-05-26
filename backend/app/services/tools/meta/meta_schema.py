# -*- coding: utf-8 -*-
"""
Meta 工具 Schema - Pydantic 输入模型

【2026-05-17 小沈】新建
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


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


class BatchProcessInput(BaseModel):
    """batch_process 批量文件处理 — 小沈 2026-05-22 （从file移入meta）

    对匹配glob模式的所有文件执行同一操作（rename/delete/copy）。
    """
    source_pattern: str = Field(description='文件匹配模式。如 "*.txt"、"logs/*.log"、"data/**/*.csv"')
    action: Literal["rename", "delete", "copy"] = Field(description='批量操作类型：rename(改名)、delete(删除)、copy(复制)')
    target_pattern: Optional[str] = Field(default=None, description='rename/copy的目标文件模式。如 "*.md"')
    target_dir: Optional[str] = Field(default=None, description='copy的目标目录（绝对路径）')
    dry_run: bool = Field(default=True, description='预览模式。True=只预览不执行（默认），False=实际执行操作')
    max_files: int = Field(default=500, description='处理文件数上限，默认500，最小1，最大10000')
    exist_ok: bool = Field(default=True, description='copy操作时目标目录已存在是否报错。True=不报错，False=报错。默认True')


__all__ = ["ToolHelpInput", "ToolSearchInput", "PipelineInput", "BatchProcessInput"]
