# -*- coding: utf-8 -*-
"""Task 系统数据模型

TaskStatus 枚举。
TaskRecord/OperationRecord 已删除 — 死代码(从未被import,实际使用 db.models.operation_models)。
操作状态枚举 OperationStatus 复用 app.db.models.operation_enums。

Author: 小沈 - 2026-05-29
"""

from enum import Enum


class TaskStatus(str, Enum):
    """任务生命周期状态 — 新增,已有枚举无此定义"""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIALLY_ROLLED_BACK = "partially_rolled_back"
    ROLLED_BACK = "rolled_back"
