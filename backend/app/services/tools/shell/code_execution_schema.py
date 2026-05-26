# -*- coding: utf-8 -*-
"""
Code Execution 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【2026-05-22 小沈】合并 ExecutePythonInput+ExecuteJavascriptInput → ExecuteCodeInput

职责：
定义 code_execution 工具的 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional


class ExecuteCodeInput(BaseModel):
    """execute_code 工具的输入参数 — 小沈 2026-05-22 合并python+javascript"""
    code: str = Field(
        ..., description="要执行的代码（字符串），必填参数"
    )
    language: str = Field(
        default="python", description="语言类型: python 或 javascript，默认python"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间（秒），默认为30秒，最大300秒"
    )
    working_dir: Optional[str] = Field(
        default=None, description="工作目录（可选）。默认为当前工作目录。目录不存在时自动创建"
    )
    safety_check: bool = Field(
        default=True, description="执行前是否进行安全检查，默认True。设为False可跳过安全检查"
    )


__all__ = [
    "ExecuteCodeInput",
]
