"""
测试file_safety.py的数据库引用更新
验证迁移后的代码能够正常工作

Author: 小沈 - 2026-05-22
"""
import pytest
from pathlib import Path
from app.services.safety.file.file_safety import FileSafetyConfig, FileOperationSafety
from app.db import db


def test_file_safety_config():
    """测试FileSafetyConfig配置"""
    config = FileSafetyConfig()
    
    assert "omniagent" in str(config.RECYCLE_BIN_PATH).lower()
    assert "recycle_bin" in str(config.RECYCLE_BIN_PATH).lower()
    assert config.BACKUP_RETENTION_DAYS == 30


def test_file_safety_config_ensure_directories():
    """测试FileSafetyConfig确保目录存在"""
    FileSafetyConfig.ensure_directories()
    
    assert FileSafetyConfig.RECYCLE_BIN_PATH.exists()
    assert FileSafetyConfig.REPORT_PATH.exists()


def test_file_operation_safety_init():
    """测试FileOperationSafety初始化"""
    safety = FileOperationSafety()
    assert safety.config is not None
    assert isinstance(safety.config, FileSafetyConfig)


def test_file_operation_safety_close():
    """测试FileOperationSafety关闭"""
    safety = FileOperationSafety()
    safety.close()


def test_file_safety_uses_new_db_module():
    """测试file_safety使用新的数据库模块"""
    
    safety = FileOperationSafety()
    
    with db.get_conn("operations") as conn:
        assert conn is not None
        import sqlite3
        assert isinstance(conn, sqlite3.Connection)


def test_file_safety_tables_exist():
    """测试file_safety的数据库表已创建"""
    
    with db.get_conn("operations") as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_operations'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_operation_sessions'")
        assert cursor.fetchone() is not None
