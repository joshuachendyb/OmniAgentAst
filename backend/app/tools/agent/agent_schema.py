# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question/schedule 输入模型: 扁平 List[Dict[str, Any]], 避免嵌套 BaseModel 生成 $defs/$ref 被严格 provider 拒绝
"""
agent_schema — 智能体交互工具参数模型(question / schedule)

本仓契约: _validate_params 只做顶层校验, 嵌套字段的语义校验在工具函数内手工完成。
"""
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class QuestionInput(BaseModel):
    questions: List[Dict[str, Any]] = Field(
        ..., description="问题数组(1~8项)。每项: {question:完整问题, header:极短标签(≤30字), "
                         "options:[{label:选项文本, description:选项说明}](1~9项), multiple:是否多选(默认false)}"
    )


class ScheduleInput(BaseModel):
    items: List[Dict[str, Any]] = Field(
        ..., description="完整计划清单(整体替换, 传[]即清空)。每项: {content:任务简述, "
                         "status:pending|in_progress|completed|cancelled}"
    )


__all__ = ["QuestionInput", "ScheduleInput"]
