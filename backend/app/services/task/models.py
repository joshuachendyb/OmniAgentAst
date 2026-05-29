# -*- coding: utf-8 -*-
"""Task 系统数据模型

TaskStatus 枚举 + TaskRecord/OperationRecord Pydantic 模型。
操作状态枚举 OperationStatus 复用 app.db.models.operation_enums。

Author: 小沈 - 2026-05-29
"""

from enum import Enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from app.db.models.operation_enums import OperationStatus  # 复用已有枚举


class TaskStatus(str, Enum):
    """任务生命周期状态 — 新增，已有枚举无此定义"""
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIALLY_ROLLED_BACK = "partially_rolled_back"
    ROLLED_BACK = "rolled_back"


class TaskRecord(BaseModel):
    """任务记录 — 对应 tasks 表"""
    task_id: str = Field(..., description="任务执行ID (UUID)")
    intent: str = Field(..., description="意图标识")
    agent_id: str = Field(..., description="执行者 ID")
    task_description: str = Field(..., description="任务描述")
    status: TaskStatus = Field(default=TaskStatus.EXECUTING, description="任务状态")
    total_operations: int = Field(default=0, description="总操作数")
    success_count: int = Field(default=0, description="成功操作数")
    failed_count: int = Field(default=0, description="失败操作数")
    rolled_back_count: int = Field(default=0, description="已回滚操作数")
    report_generated: bool = Field(default=False, description="是否已生成报告")
    report_path: Optional[str] = Field(default=None, description="报告文件路径")
    created_at: datetime = Field(default_factory=datetime.now, description="任务创建时间")
    completed_at: Optional[datetime] = Field(default=None, description="任务完成时间")


class OperationRecord(BaseModel):
    """操作记录 — 对应 operations 表"""
    operation_id: str = Field(..., description="唯一操作标识符 (UUID)")
    task_id: str = Field(..., description="所属任务ID")
    intent: str = Field(default="", description="执行此操作的意图标识")
    operation_type: str = Field(..., description="操作类型")
    status: OperationStatus = Field(default=OperationStatus.PENDING, description="操作状态")
    source_path: Optional[str] = Field(default=None, description="来源路径")
    destination_path: Optional[str] = Field(default=None, description="目标路径")
    backup_path: Optional[str] = Field(default=None, description="备份路径")
    file_size: int = Field(default=0, description="文件大小（字节）")
    file_hash: Optional[str] = Field(default=None, description="文件哈希")
    sequence_number: int = Field(default=0, description="操作顺序号")
    details: Optional[str] = Field(default=None, description="JSON 扩展字段")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="操作创建时间")
