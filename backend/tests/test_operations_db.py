"""
测试operations数据库模块
验证 db/database.py 和 db/models/operation_* 的正确性
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正

Author: 小沈 - 2026-05-22
"""
import sqlite3
import pytest
from pathlib import Path
from app.db import db
from app.db.models.operation_enums import OperationType, OperationStatus
from app.db.models.operation_models import OperationRecord, TaskRecord


def test_operations_db_path():
    """测试操作数据库文件路径"""
    assert db._db_paths["operations"].name == "operations.db"
    assert ".omniagent" in str(db._db_paths["operations"])


def test_operations_get_connection():
    """测试获取操作数据库连接"""
    with db.get_conn("operations") as conn:
        assert isinstance(conn, sqlite3.Connection)
        
        # 验证WAL模式
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"


def test_operations_init_database():
    """测试操作数据库初始化"""
    db.init()
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        
        # 检查 file_operations 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'")
        assert cursor.fetchone() is not None
        
        # 检查 task_operations 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_operations'")
        assert cursor.fetchone() is not None


def test_operation_type_enum():
    """测试OperationType枚举"""
    assert OperationType.CREATE.value == "create"
    assert OperationType.DELETE.value == "delete"
    assert OperationType.MOVE.value == "move"
    assert OperationType.COPY.value == "copy"
    assert OperationType.RENAME.value == "rename"


def test_operation_status_enum():
    """测试OperationStatus枚举"""
    assert OperationStatus.PENDING.value == "pending"
    assert OperationStatus.EXECUTING.value == "executing"
    assert OperationStatus.SUCCESS.value == "success"
    assert OperationStatus.FAILED.value == "failed"
    assert OperationStatus.ROLLBACK.value == "rollback"


def test_operation_record_model():
    """测试OperationRecord模型"""
    record = OperationRecord(
        operation_id="op-test-123",
        task_id="task-test-456",
        operation_type=OperationType.MOVE,
        status=OperationStatus.SUCCESS,
        source_path="/source/file.txt",
        destination_path="/dest/file.txt",
        file_size=1024
    )
    assert record.operation_id == "op-test-123"
    assert record.task_id == "task-test-456"
    assert record.operation_type == OperationType.MOVE
    assert record.status == OperationStatus.SUCCESS
    assert record.file_size == 1024


def test_task_record_model():
    """测试TaskRecord模型"""
    record = TaskRecord(
        task_id="task-test-789",
        agent_id="file-agent",
        task_description="Move files",
        status=OperationStatus.SUCCESS,
        total_operations=5,
        success_count=5
    )
    assert record.task_id == "task-test-789"
    assert record.agent_id == "file-agent"
    assert record.task_description == "Move files"
    assert record.total_operations == 5
    assert record.success_count == 5


def test_operation_record_serialization():
    """测试OperationRecord枚举序列化"""
    record = OperationRecord(
        operation_id="op-test",
        task_id="task-test",
        operation_type=OperationType.DELETE,
        status=OperationStatus.FAILED
    )
    
    # 枚举应该序列化为字符串
    assert record.operation_type.value == "delete"
    assert record.status.value == "failed"
    
    # 可以转换为dict
    record_dict = record.model_dump()
    assert record_dict["operation_type"] == "delete"
    assert record_dict["status"] == "failed"
