# -*- coding: utf-8 -*-
"""TaskTracker 单元测试

测试 TaskTracker 所有方法：create/complete/add/mark_failed/mark_rolled_back。
使用临时数据库，不影响生产数据。
Author: 小沈 - 2026-05-29
"""

from task_test_base import _setup_test_db, _cleanup, _patch_db, _restore_db, tt_module
from app.services.task.task_tracker import TaskTracker


def test_create_task():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "agent-1", "测试任务")
        assert task_id.startswith("task-")
        with test_db.get_conn("task_tracker") as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert row is not None
            assert row["status"] == "executing"
            assert row["intent"] == "file"
        print("✅ test_create_task passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_create_task_invalid_intent():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        try:
            tracker.create_task("invalid_intent", "a", "d")
            assert False, "should raise"
        except ValueError as e:
            assert "Invalid intent" in str(e)
        print("✅ test_create_task_invalid_intent passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_complete_task_success():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("shell", "a", "d")
        tracker.complete_task(task_id, success=True)
        with test_db.get_conn("task_tracker") as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert row["status"] == "success"
            assert row["completed_at"] is not None
        print("✅ test_complete_task_success passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_complete_task_failed():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("shell", "a", "d")
        tracker.complete_task(task_id, success=False)
        with test_db.get_conn("task_tracker") as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert row["status"] == "failed"
        print("✅ test_complete_task_failed passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_add_operation():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        op_id = tracker.add_operation(
            task_id, "create",
            source_path="/tmp/a.txt",
            destination_path="/tmp/b.txt",
            details={"size": 100},
        )
        assert op_id.startswith("op-")
        with test_db.get_conn("task_tracker") as conn:
            task_row = conn.execute("SELECT total_operations FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert task_row["total_operations"] == 1
            op_row = conn.execute("SELECT * FROM operations WHERE operation_id=?", (op_id,)).fetchone()
            assert op_row is not None
            assert op_row["source_path"] == "/tmp/a.txt"
        print("✅ test_add_operation passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_add_operation_task_not_found():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        try:
            tracker.add_operation("task-notexist", "create")
            assert False, "should raise"
        except ValueError as e:
            assert "not found" in str(e)
        print("✅ test_add_operation_task_not_found passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_mark_failed():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        op_id = tracker.add_operation(task_id, "create")
        tracker.mark_failed(task_id, op_id, "磁盘空间不足")
        with test_db.get_conn("task_tracker") as conn:
            op_row = conn.execute("SELECT status, error FROM operations WHERE operation_id=?", (op_id,)).fetchone()
            assert op_row["status"] == "failed"
            assert op_row["error"] == "磁盘空间不足"
            task_row = conn.execute("SELECT failed_count FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert task_row["failed_count"] == 1
        print("✅ test_mark_failed passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_mark_rolled_back_all():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        op1 = tracker.add_operation(task_id, "create")
        op2 = tracker.add_operation(task_id, "move")
        tracker.mark_rolled_back(task_id)
        with test_db.get_conn("task_tracker") as conn:
            ops = conn.execute("SELECT status FROM operations WHERE task_id=?", (task_id,)).fetchall()
            assert all(r["status"] == "rollback" for r in ops)
            task_row = conn.execute("SELECT status, rolled_back_count FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert task_row["status"] == "rolled_back"
            assert task_row["rolled_back_count"] == 2
        print("✅ test_mark_rolled_back_all passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_mark_rolled_back_partial():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        op1 = tracker.add_operation(task_id, "create")
        op2 = tracker.add_operation(task_id, "move")
        tracker.mark_rolled_back(task_id, op_ids=[op1])
        with test_db.get_conn("task_tracker") as conn:
            op1_row = conn.execute("SELECT status FROM operations WHERE operation_id=?", (op1,)).fetchone()
            op2_row = conn.execute("SELECT status FROM operations WHERE operation_id=?", (op2,)).fetchone()
            assert op1_row["status"] == "rollback"
            assert op2_row["status"] == "success"
            task_row = conn.execute("SELECT status, rolled_back_count FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert task_row["status"] == "partially_rolled_back"
            assert task_row["rolled_back_count"] == 1
        print("✅ test_mark_rolled_back_partial passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_mark_report_generated():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        tracker.mark_report_generated(task_id, "/tmp/report.json")
        with test_db.get_conn("task_tracker") as conn:
            row = conn.execute("SELECT report_generated, report_path FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            assert row["report_generated"] == 1
            assert row["report_path"] == "/tmp/report.json"
        print("✅ test_mark_report_generated passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_sequence_number_auto_increment():
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        tracker = TaskTracker()
        task_id = tracker.create_task("file", "a", "d")
        tracker.add_operation(task_id, "create")
        tracker.add_operation(task_id, "move")
        tracker.add_operation(task_id, "copy")
        with test_db.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT operation_id, sequence_number FROM operations WHERE task_id=? ORDER BY sequence_number",
                (task_id,),
            ).fetchall()
            assert len(rows) == 3
            assert rows[0]["sequence_number"] == 1
            assert rows[1]["sequence_number"] == 2
            assert rows[2]["sequence_number"] == 3
        print("✅ test_sequence_number_auto_increment passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_get_tracker_singleton():
    old = tt_module._tracker
    try:
        tt_module._tracker = None
        t1 = tt_module.get_tracker()
        t2 = tt_module.get_tracker()
        assert t1 is t2
        print("✅ test_get_tracker_singleton passed")
    finally:
        tt_module._tracker = old


if __name__ == "__main__":
    test_create_task()
    test_create_task_invalid_intent()
    test_complete_task_success()
    test_complete_task_failed()
    test_add_operation()
    test_add_operation_task_not_found()
    test_mark_failed()
    test_mark_rolled_back_all()
    test_mark_rolled_back_partial()
    test_mark_report_generated()
    test_sequence_number_auto_increment()
    test_get_tracker_singleton()
    print("\n🎉 All TaskTracker tests passed!")
