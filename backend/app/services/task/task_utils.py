# -*- coding: utf-8 -*-
"""
task_utils — task模块公共函数

小欧 2026-06-18 创建，提取_build_step_dict消除重复
"""
from typing import Optional
from app.utils.time_utils import create_timestamp


def build_step_dict(step: Optional[int], step_type: str, message: str) -> dict:
    """构建step字典 — 替代MetaStep.to_dict()，消除对agent/steps的依赖 — 小健 2026-06-17"""
    return {"type": step_type, "step": step, "timestamp": create_timestamp(), "content": message}
