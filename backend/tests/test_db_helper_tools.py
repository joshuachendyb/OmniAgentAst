# -*- coding: utf-8 -*-
"""
数据库辅助工具测试模块

【创建时间】2026-05-02 小沈

Author: 小沈 - 2026-05-02
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tools.db_helper.db_helper_tools import (
    check_db_exists,
    get_table_schema,
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    check_network_connectivity,
    validate_url,
)


class TestCheckDbExists:
    """check_db_exists 测试 - 小沈 2026-05-02"""

    def test_db_not_exists(self):
        result = check_db_exists(db_path="D:/nonexistent/app.db")
        assert result["data"]["exists"] is False

    def test_db_exists(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            import sqlite3
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()
            conn.close()

            result = check_db_exists(db_path=path)
            assert result["data"]["exists"] is True
            assert result["data"]["db_type"] == "sqlite"
        finally:
            os.unlink(path)


class TestGetTableSchema:
    """get_table_schema 测试 - 小沈 2026-05-02"""

    def test_table_schema(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            import sqlite3
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER DEFAULT 0)")
            conn.commit()
            conn.close()

            result = get_table_schema(db_path=path, table_name="users")
            assert result["code"] == "SUCCESS"
            assert result["data"]["column_count"] == 3
            assert result["data"]["primary_key"] == "id"
        finally:
            os.unlink(path)

    def test_table_not_found(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            result = get_table_schema(db_path=path, table_name="nonexistent")
            assert result["code"] == "ERR_TABLE_NOT_FOUND"
        finally:
            os.unlink(path)


class TestTransaction:
    """事务操作测试 - 小沈 2026-05-02"""

    def test_begin_transaction(self):
        result = begin_transaction()
        assert result["code"] == "SUCCESS"
        assert "transaction_id" in result["data"]

    def test_commit_transaction(self):
        result = commit_transaction(transaction_id="test123")
        assert result["code"] == "SUCCESS"

    def test_rollback_transaction(self):
        result = rollback_transaction(transaction_id="test123")
        assert result["code"] == "SUCCESS"


class TestCheckNetworkConnectivity:
    """check_network_connectivity 测试 - 小沈 2026-05-02"""

    def test_network_check(self):
        result = check_network_connectivity()
        assert result["code"] == "SUCCESS"
        assert "connected" in result["data"]


class TestValidateUrl:
    """validate_url 测试 - 小沈 2026-05-02"""

    def test_valid_https(self):
        result = validate_url(url="https://example.com")
        assert result["data"]["valid"] is True

    def test_valid_http(self):
        result = validate_url(url="http://localhost:8080/api")
        assert result["data"]["valid"] is True

    def test_invalid_url(self):
        result = validate_url(url="not-a-url")
        assert result["data"]["valid"] is False

    def test_invalid_scheme(self):
        result = validate_url(url="ftp2://example.com")
        assert result["data"]["valid"] is False
