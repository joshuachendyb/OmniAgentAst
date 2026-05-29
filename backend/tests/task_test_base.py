# -*- coding: utf-8 -*-
"""Task 测试共用工具函数

共享 _setup_test_db / _patch_db / _restore_db / _cleanup，
消除3个测试文件间的代码重复。

Author: 小沈 - 2026-05-29
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import app.db.database as db_module
import app.services.task.task_tracker as tt_module
import app.services.task.task_queries as tq_module

ALL_TABLES_SQL = """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        intent TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        task_description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'executing',
        total_operations INTEGER DEFAULT 0,
        success_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        rolled_back_count INTEGER DEFAULT 0,
        report_generated INTEGER DEFAULT 0,
        report_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS operations (
        operation_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        intent TEXT NOT NULL DEFAULT '',
        operation_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        source_path TEXT,
        destination_path TEXT,
        backup_path TEXT,
        file_size INTEGER DEFAULT 0,
        file_hash TEXT,
        sequence_number INTEGER NOT NULL DEFAULT 0,
        details TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""


def _setup_test_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    test_db_path = tmp.name
    test_db = db_module.DatabaseManager.__new__(db_module.DatabaseManager)
    test_db._db_dir = os.path.dirname(test_db_path)
    test_db._db_paths = {
        "chat": test_db_path,
        "operations": test_db_path,
        "observer": test_db_path,
        "task_tracker": test_db_path,
    }
    with test_db.get_conn("task_tracker") as conn:
        conn.executescript(ALL_TABLES_SQL)
    return test_db, test_db_path


def _cleanup(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _patch_db(test_db):
    _orig_db = db_module.db
    _orig_tt_db = tt_module.db
    _orig_tq_db = tq_module.db
    db_module.db = test_db
    tt_module.db = test_db
    tq_module.db = test_db
    return _orig_db, _orig_tt_db, _orig_tq_db


def _restore_db(orig):
    db_module.db, tt_module.db, tq_module.db = orig
