# -*- coding: utf-8 -*-
"""
Shell 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 shell 工具的 Pydantic 模型。

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional


class ExecuteCommandInput(BaseModel):
    """execute_command 工具的输入参数"""
    command: str = Field(
        ..., description="要执行的Shell命令（字符串），必填参数"
    )
    cwd: Optional[str] = Field(
        default=None, description="工作目录（可选）。如果为None则使用当前工作目录"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间（秒），默认为30秒，最大300秒"
    )


class ListDirectoryInput(BaseModel):
    """list_directory 工具的输入参数"""
    path: str = Field(
        default=".", description="目录路径，默认为当前目录"
    )


class GetWorkingDirectoryInput(BaseModel):
    """get_working_directory 工具的输入参数（无参数）"""
    pass


class ChangeDirectoryInput(BaseModel):
    """change_directory 工具的输入参数"""
    path: str = Field(
        ..., description="要切换到的目录路径。必填参数"
    )


class CheckPathExistsInput(BaseModel):
    """check_path_exists 工具的输入参数"""
    path: str = Field(
        ..., description="要检查的文件或目录路径。必填参数"
    )


__all__ = [
    "ExecuteCommandInput",
    "ListDirectoryInput",
    "GetWorkingDirectoryInput",
    "ChangeDirectoryInput",
    "CheckPathExistsInput",
]
