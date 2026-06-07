# -*- coding: utf-8 -*-
"""safety/file/file_safety.py 测试 — 小健 2026-05-30"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from app.services.safety.file.file_safety import (
    FileSafetyConfig,
    FileOperationSafety,
    get_file_safety_service,
    compute_file_hash,
    collect_file_info,
    backup_to_recycle_bin,
    get_operation_task_id,
    get_operation,
    get_session_operations,
    rollback_session,
    rollback_operation,
    cleanup_expired_backups,
    execute_with_safety,
    record_operation,
)


class TestFileSafetyConfig:
    """FileSafetyConfig 配置默认值测试"""

    def test_recycle_bin_default(self):
        """正常：回收站路径默认值"""
        config = FileSafetyConfig()
        assert ".omniagent" in str(config.RECYCLE_BIN_PATH)
        assert "recycle_bin" in str(config.RECYCLE_BIN_PATH)

    def test_backup_retention_days(self):
        """正常：备份保留天数"""
        config = FileSafetyConfig()
        assert config.BACKUP_RETENTION_DAYS == 30

    def test_ensure_directories(self):
        """正常：创建目录不报错"""
        config = FileSafetyConfig()
        config.ensure_directories()
        assert config.RECYCLE_BIN_PATH.exists()
        assert config.REPORT_PATH.exists()

    def test_project_root(self):
        """正常：PROJECT_ROOT可访问且有效"""
        config = FileSafetyConfig()
        assert config.PROJECT_ROOT.exists()


class TestFileOperationSafety:
    """FileOperationSafety 深度测试 — 依赖DB需要mock"""

    def test_init(self):
        """正常：初始化不报错"""
        svc = FileOperationSafety()
        assert svc.config is not None
        svc.close()

    def test_close(self):
        """正常：关闭不报错"""
        svc = FileOperationSafety()
        svc.close()

    def test_compute_file_hash(self, tmp_path):
        """正常：计算文件hash"""
        svc = FileOperationSafety()
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h = compute_file_hash(f)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256

    def test_compute_file_hash_nonexistent(self):
        """边界：不存在的文件返回空字符串"""
        svc = FileOperationSafety()
        h = compute_file_hash(Path("/nonexistent_file_xyz"))
        assert h == ""

    def test_collect_file_info(self, tmp_path):
        """正常：收集文件信息"""
        svc = FileOperationSafety()
        f = tmp_path / "test.txt"
        f.write_text("hello")
        info = collect_file_info(f)
        assert info["size"] == 5
        assert info["is_directory"] is False
        assert info["hash"] is not None
        assert info["extension"] == ".txt"

    def test_collect_file_info_directory(self, tmp_path):
        """正常：目录信息"""
        svc = FileOperationSafety()
        info = collect_file_info(tmp_path)
        assert info["is_directory"] is True
        assert info["hash"] is None

    def test_collect_file_info_nonexistent(self):
        """边界：不存在的路径"""
        svc = FileOperationSafety()
        info = collect_file_info(Path("/nonexistent"))
        assert info["size"] is None
        assert info["is_directory"] is False

    def test_collect_file_info_none(self):
        """边界：None路径"""
        svc = FileOperationSafety()
        info = collect_file_info(None)
        assert info["size"] is None

    def test_backup_to_recycle_bin(self, tmp_path):
        """正常：备份文件到回收站"""
        svc = FileOperationSafety()
        src = tmp_path / "test.txt"
        src.write_text("backup content")
        backup = backup_to_recycle_bin(src)
        assert backup is not None
        assert backup.exists()
        assert backup.read_text() == "backup content"

    def test_backup_to_recycle_bin_nonexistent(self):
        """边界：备份不存在的文件"""
        svc = FileOperationSafety()
        result = backup_to_recycle_bin(Path("/nonexistent_xyz"))
        assert result is None

    def test_backup_to_recycle_bin_directory(self, tmp_path):
        """正常：备份目录"""
        svc = FileOperationSafety()
        src = tmp_path / "subdir"
        src.mkdir()
        (src / "file1.txt").write_text("a")
        (src / "file2.txt").write_text("b")
        backup = backup_to_recycle_bin(src)
        assert backup is not None
        assert backup.exists()
        assert (backup / "file1.txt").exists()

    def test_get_operation_task_id_not_found(self):
        """边界：操作不存在返回None"""
        svc = FileOperationSafety()
        result = get_operation_task_id("nonexistent-op-id")
        assert result is None

    def test_get_operation_not_found(self):
        """边界：获取不存在的操作返回None"""
        svc = FileOperationSafety()
        result = get_operation("nonexistent-op-id")
        assert result is None

    def test_get_session_operations_not_found(self):
        """边界：获取不存在session的操作列表"""
        svc = FileOperationSafety()
        result = get_session_operations("nonexistent-task-id")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_rollback_session_not_found(self):
        """边界：回滚不存在session"""
        svc = FileOperationSafety()
        result = rollback_session("nonexistent-task-id")
        assert result["total"] == 0
        assert result["success"] == 0

    def test_rollback_operation_not_found(self):
        """边界：回滚不存在操作"""
        svc = FileOperationSafety()
        result = rollback_operation("nonexistent-op-id")
        assert result is False

    def test_cleanup_expired_backups_empty(self):
        """边界：无过期备份时返回0"""
        svc = FileOperationSafety()
        count = cleanup_expired_backups()
        assert count >= 0

    def test_execute_with_safety_op_not_found(self):
        """边界：操作ID不存在返回False"""
        svc = FileOperationSafety()
        result = execute_with_safety("nonexistent", lambda: True)
        assert result is False

    def test_record_operation_with_mock_db(self, monkeypatch):
        """正常：记录操作返回operation_id"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        def mock_get_conn(name):
            return mock_conn

        monkeypatch.setattr("app.db.db.get_conn", mock_get_conn)

        svc = FileOperationSafety()
        from app.db.models.operation_enums import OperationType
        op_id = record_operation(
            task_id="test-task",
            operation_type=OperationType.CREATE,
            source_path=Path("/tmp/test.txt"),
            file_size=100,
        )
        assert op_id.startswith("op-")
        assert mock_cursor.execute.called

    def test_get_file_safety_service_singleton(self):
        """正常：单例模式"""
        s1 = get_file_safety_service()
        s2 = get_file_safety_service()
        assert s1 is s2
        s1.close()
