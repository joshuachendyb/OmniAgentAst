# -*- coding: utf-8 -*-
"""Task 数据模型单元测试

测试 TaskStatus 枚举、TaskRecord/OperationRecord 构造。
Author: 小沈 - 2026-05-29
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app.services.task.models import TaskStatus, TaskRecord, OperationRecord
from app.db.models.operation_enums import OperationStatus


def test_task_status_values():
    """TaskStatus 枚举值正确"""
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.EXECUTING.value == "executing"
    assert TaskStatus.SUCCESS.value == "success"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.PARTIALLY_ROLLED_BACK.value == "partially_rolled_back"
    assert TaskStatus.ROLLED_BACK.value == "rolled_back"


def test_operation_status_reuse():
    """OperationStatus 复用已有枚举"""
    assert OperationStatus.PENDING.value == "pending"
    assert OperationStatus.SUCCESS.value == "success"
    assert OperationStatus.ROLLBACK.value == "rollback"


def test_task_record_construction():
    """TaskRecord 能正常构造"""
    rec = TaskRecord(
        task_id="task-abc123",
        intent="file",
        agent_id="agent-1",
        task_description="测试任务",
    )
    assert rec.task_id == "task-abc123"
    assert rec.intent == "file"
    assert rec.status == TaskStatus.EXECUTING
    assert rec.total_operations == 0
    assert rec.success_count == 0
    assert rec.failed_count == 0
    assert rec.rolled_back_count == 0
    assert rec.report_generated is False
    assert rec.report_path is None
    assert rec.created_at is not None
    assert rec.completed_at is None


def test_operation_record_construction():
    """OperationRecord 能正常构造"""
    rec = OperationRecord(
        operation_id="op-xyz789",
        task_id="task-abc123",
        operation_type="create",
    )
    assert rec.operation_id == "op-xyz789"
    assert rec.task_id == "task-abc123"
    assert rec.operation_type == "create"
    assert rec.status == OperationStatus.PENDING
    assert rec.source_path is None
    assert rec.details is None
    assert rec.error is None


def test_task_record_with_optional_fields():
    """TaskRecord 可选字段填充"""
    rec = TaskRecord(
        task_id="task-opt",
        intent="shell",
        agent_id="a",
        task_description="d",
        status=TaskStatus.SUCCESS,
        total_operations=5,
        success_count=3,
        failed_count=2,
        report_generated=True,
        report_path="/tmp/report.json",
    )
    assert rec.status == TaskStatus.SUCCESS
    assert rec.total_operations == 5
    assert rec.report_path == "/tmp/report.json"


def test_operation_record_with_details():
    """OperationRecord details 字段为字符串"""
    rec = OperationRecord(
        operation_id="op-d",
        task_id="task-d",
        operation_type="run",
        details='{"command": "ls", "exit_code": 0}',
    )
    assert rec.details == '{"command": "ls", "exit_code": 0}'


if __name__ == "__main__":
    test_task_status_values()
    test_operation_status_reuse()
    test_task_record_construction()
    test_operation_record_construction()
    test_task_record_with_optional_fields()
    test_operation_record_with_details()
    print("All model tests passed")
