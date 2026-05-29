# -*- coding: utf-8 -*-
"""TaskQueries 单元测试

测试查询方法：get_task / get_recent_tasks / get_operations。
使用临时数据库。
Author: 小沈 - 2026-05-29
"""

from task_test_base import _setup_test_db, _cleanup, _patch_db, _restore_db
from app.services.task.task_queries import TaskQueries


def _seed_data(test_db):
    with test_db.get_conn("task_tracker") as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, intent, agent_id, task_description, status) VALUES (?, ?, ?, ?, ?)",
            ("task-1", "file", "agent-1", "任务1", "success"),
        )
        conn.execute(
            "INSERT INTO tasks (task_id, intent, agent_id, task_description, status) VALUES (?, ?, ?, ?, ?)",
            ("task-2", "shell", "agent-2", "任务2", "executing"),
        )
        conn.execute(
            "INSERT INTO tasks (task_id, intent, agent_id, task_description, status) VALUES (?, ?, ?, ?, ?)",
            ("task-3", "file", "agent-3", "任务3", "failed"),
        )
        conn.execute(
            "INSERT INTO operations "
            "(operation_id, task_id, intent, operation_type, status, source_path, sequence_number, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("op-1", "task-1", "file", "create", "success", "/a.txt", 1, '{"size":100}'),
        )
        conn.execute(
            "INSERT INTO operations "
            "(operation_id, task_id, intent, operation_type, status, source_path, sequence_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("op-2", "task-1", "file", "move", "success", "/b.txt", 2),
        )


def test_get_task():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        _seed_data(test_db)
        q = TaskQueries()
        result = q.get_task("task-1")
        assert result is not None
        assert result["task_id"] == "task-1"
        assert result["intent"] == "file"
        assert result["status"] == "success"
        assert q.get_task("task-notexist") is None
        print("✅ test_get_task passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_get_recent_tasks():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        _seed_data(test_db)
        q = TaskQueries()
        assert len(q.get_recent_tasks(limit=10)) == 3
        assert len(q.get_recent_tasks(limit=2)) == 2
        file_tasks = q.get_recent_tasks(intent="file")
        assert len(file_tasks) == 2
        assert all(t["intent"] == "file" for t in file_tasks)
        assert len(q.get_recent_tasks(intent="shell")) == 1
        print("✅ test_get_recent_tasks passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_get_operations():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        _seed_data(test_db)
        q = TaskQueries()
        ops = q.get_operations("task-1")
        assert len(ops) == 2
        assert ops[0]["sequence_number"] == 2
        assert ops[1]["sequence_number"] == 1
        assert ops[1]["details"] == {"size": 100}
        assert ops[0]["details"] is None
        print("✅ test_get_operations passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


if __name__ == "__main__":
    test_get_task()
    test_get_recent_tasks()
    test_get_operations()
    print("\n🎉 All TaskQueries tests passed!")
