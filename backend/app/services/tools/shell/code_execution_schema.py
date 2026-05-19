# -*- coding: utf-8 -*-
"""
Code Execution 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 code_execution 工具的 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional


class ExecutePythonInput(BaseModel):
    """execute_python 工具的输入参数"""
    code: str = Field(
        ..., description="要执行的Python代码（字符串），必填参数"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间（秒），默认为30秒，最大300秒"
    )
    working_dir: Optional[str] = Field(
        default=None, description="工作目录（可选）。默认为当前工作目录。目录不存在时自动创建"
    )
    safety_check: bool = Field(
        default=True, description="执行前是否进行安全检查（检测os.system/subprocess等危险模式），默认True。设为False可跳过安全检查"
    )


class ExecuteJavascriptInput(BaseModel):
    """execute_javascript 工具的输入参数 — 小健 2026-05-19 增加safety_check"""
    code: str = Field(
        ..., description="要执行的JavaScript代码（字符串），必填参数"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间（秒），默认为30秒，最大300秒"
    )
    working_dir: Optional[str] = Field(
        default=None, description="工作目录（可选）。默认为当前工作目录。目录不存在时自动创建"
    )
    safety_check: bool = Field(
        default=True, description="执行前是否进行安全检查（检测require('child_process')/eval等危险模式），默认True。设为False可跳过安全检查"
    )


__all__ = [
    "ExecutePythonInput",
    "ExecuteJavascriptInput",
]
