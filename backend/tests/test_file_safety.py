"""
FileSafety 测试 - 小沈

测试文件操作安全服务的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.safety.file.file_safety import FileSafetyConfig, FileOperationSafety
from app.models.file_operations import OperationType


class TestFileSafetyConfig:
    """测试FileSafetyConfig配置"""
    
    def test_config_has_recycle_bin_path(self):
        """测试有RECYCLE_BIN_PATH属性"""
        assert hasattr(FileSafetyConfig, 'RECYCLE_BIN_PATH')
        assert isinstance(FileSafetyConfig.RECYCLE_BIN_PATH, Path)
    
    def test_config_has_db_path(self):
        """测试有DB_PATH属性"""
        assert hasattr(FileSafetyConfig, 'DB_PATH')
        assert isinstance(FileSafetyConfig.DB_PATH, Path)
    
    def test_config_has_report_path(self):
        """测试有REPORT_PATH属性"""
        assert hasattr(FileSafetyConfig, 'REPORT_PATH')
        assert isinstance(FileSafetyConfig.REPORT_PATH, Path)
    
    def test_config_has_backup_retention_days(self):
        """测试有BACKUP_RETENTION_DAYS属性"""
        assert hasattr(FileSafetyConfig, 'BACKUP_RETENTION_DAYS')
        assert FileSafetyConfig.BACKUP_RETENTION_DAYS == 30
    
    def test_config_ensure_directories(self):
        """测试ensure_directories方法"""
        assert hasattr(FileSafetyConfig, 'ensure_directories')
        assert callable(FileSafetyConfig.ensure_directories)


class TestFileOperationSafety:
    """测试FileOperationSafety服务"""
    
    def test_safety_has_init(self):
        """测试有__init__方法"""
        assert hasattr(FileOperationSafety, '__init__')
    
    def test_safety_has_close(self):
        """测试有close方法"""
        assert hasattr(FileOperationSafety, 'close')
    
    def test_safety_has_config(self):
        """测试有config属性"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                assert hasattr(safety, 'config')
                assert isinstance(safety.config, FileSafetyConfig)
    
    def test_safety_has_record_operation(self):
        """测试有record_operation方法"""
        assert hasattr(FileOperationSafety, 'record_operation')
        assert callable(FileOperationSafety.record_operation)
    
    def test_safety_has_execute_with_safety(self):
        """测试有execute_with_safety方法"""
        assert hasattr(FileOperationSafety, 'execute_with_safety')
        assert callable(FileOperationSafety.execute_with_safety)
    
    def test_safety_has_rollback_operation(self):
        """测试有rollback_operation方法"""
        assert hasattr(FileOperationSafety, 'rollback_operation')
        assert callable(FileOperationSafety.rollback_operation)
    
    def test_safety_has_rollback_session(self):
        """测试有rollback_session方法"""
        assert hasattr(FileOperationSafety, 'rollback_session')
        assert callable(FileOperationSafety.rollback_session)
    
    def test_safety_has_get_session_operations(self):
        """测试有get_session_operations方法"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                assert hasattr(safety, 'get_session_operations')
                assert callable(safety.get_session_operations)
    
    def test_safety_has_get_operation_session_id(self):
        """测试有get_operation_session_id方法"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                assert hasattr(safety, 'get_operation_session_id')
                assert callable(safety.get_operation_session_id)


class TestFileOperationSafetyMethods:
    """测试FileOperationSafety方法"""
    
    def test_record_operation_returns_operation_id(self):
        """测试record_operation返回操作ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                
                operation_id = safety.record_operation(
                    session_id="test-session",
                    operation_type=OperationType.CREATE,
                    source_path=Path("/tmp/test.txt")
                )
                
                assert operation_id is not None
                assert operation_id.startswith("op-")
    
    def test_get_session_operations_returns_list(self):
        """测试get_session_operations返回列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                
                operations = safety.get_session_operations("test-session")
                
                assert isinstance(operations, list)
    
    def test_get_operation_returns_dict_or_none(self):
        """测试get_operation返回字典或None"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                
                operation = safety.get_operation("nonexistent")
                
                assert operation is None or isinstance(operation, dict)


class TestFileOperationSafetyDatabase:
    """测试FileOperationSafety数据库"""
    
    def test_init_database_creates_tables(self):
        """测试_init_database创建表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                
                # 检查数据库文件存在
                assert safety.config.DB_PATH.exists()
    
    def test_get_connection_returns_connection(self):
        """测试_get_connection返回连接"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            with patch.object(FileSafetyConfig, 'DB_PATH', db_path):
                safety = FileOperationSafety()
                
                conn = safety._get_connection()
                
                assert conn is not None
                conn.close()
