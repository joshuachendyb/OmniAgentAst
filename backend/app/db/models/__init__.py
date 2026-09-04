"""
数据模型包 (Models Package)
统一导出所有数据模型
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正
# 2026-08-22 小欧 归一报告v1.25 6.1: 导出全系统统一 ModelRef 别名

Author: 小沈 - 2026-05-22
"""
from app.db.models.chat_models import (
    Session,
    Message,
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    BatchTitleResponse,
    MessageResponse,
    SessionModelOverride,
    ModelRef,
)
from app.db.models.operation_models import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord, TaskRecord

__all__ = [
    # 聊天模型
    "Session",
    "Message",
    "SessionCreate",
    "SessionResponse",
    "SessionListResponse",
    "BatchTitleResponse",
    "MessageResponse",
    "SessionModelOverride",
    "ModelRef",   # 归一: 全系统模型身份唯一结构别名 — 小欧 2026-08-22
    # 操作枚举
    "OperationType",
    "OperationStatus",
    # 操作模型
    "OperationRecord",
    "TaskRecord",
]
