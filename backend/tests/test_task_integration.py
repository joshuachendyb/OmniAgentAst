# -*- coding: utf-8 -*-
"""Task 集成测试

测试 Agent → Tracker 完整链路：创建任务 → 记录操作 → 完成任务。
使用临时数据库。
Author: 小沈 - 2026-05-29
"""

from task_test_base import _setup_test_db, _cleanup, _patch_db, _restore_db


def test_full_lifecycle():
    """完整生命周期：创建 → 添加操作 → 标记失败 → 完成 → 查询"""
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        from app.services.task.task_tracker import TaskTracker
        from app.services.task.task_queries import TaskQueries

        tracker = TaskTracker()
        queries = TaskQueries()

        # 1. 创建任务
        task_id = tracker.create_task("file", "agent-test", "移动文件 test.txt 到 backup/")
        assert task_id.startswith("task-")

        # 2. 记录操作
        op1 = tracker.add_operation(
            task_id, "move",
            source_path="/tmp/test.txt",
            destination_path="/tmp/backup/test.txt",
            file_size=1024,
        )
        op2 = tracker.add_operation(
            task_id, "copy",
            source_path="/tmp/backup/test.txt",
            destination_path="/tmp/test.txt.bak",
        )

        # 3. 标记第二个操作失败
        tracker.mark_failed(task_id, op2, "磁盘空间不足")

        # 4. 完成任务（失败）
        tracker.complete_task(task_id, success=False)

        # 5. 查询验证
        task = queries.get_task(task_id)
        assert task is not None
        assert task["status"] == "failed"
        assert task["total_operations"] == 2
        assert task["failed_count"] == 1
        assert task["success_count"] == 1  # op1 仍是 success 状态

        ops = queries.get_operations(task_id)
        assert len(ops) == 2
        # op2 失败
        failed_ops = [o for o in ops if o["status"] == "failed"]
        assert len(failed_ops) == 1

        print("✅ test_full_lifecycle passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_multi_intent():
    """多意图并行：不同意图各自独立"""
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        from app.services.task.task_tracker import TaskTracker
        from app.services.task.task_queries import TaskQueries

        tracker = TaskTracker()
        queries = TaskQueries()

        t1 = tracker.create_task("file", "a", "文件任务")
        t2 = tracker.create_task("shell", "b", "Shell任务")
        t3 = tracker.create_task("document", "c", "文档任务")

        tracker.add_operation(t1, "create")
        tracker.add_operation(t2, "run", details={"command": "ls"})
        tracker.add_operation(t3, "write")

        tracker.complete_task(t1, success=True)
        tracker.complete_task(t2, success=True)
        tracker.complete_task(t3, success=False)

        file_tasks = queries.get_recent_tasks(intent="file")
        assert len(file_tasks) == 1
        assert file_tasks[0]["task_id"] == t1

        shell_tasks = queries.get_recent_tasks(intent="shell")
        assert len(shell_tasks) == 1

        doc_tasks = queries.get_recent_tasks(intent="document")
        assert len(doc_tasks) == 1
        assert doc_tasks[0]["status"] == "failed"

        print("✅ test_multi_intent passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


def test_rollback_flow():
    """回滚流程：创建 → 操作 → 全量回滚"""
    test_db, path = _setup_test_db()
    orig = _patch_db(test_db)
    try:
        from app.services.task.task_tracker import TaskTracker
        from app.services.task.task_queries import TaskQueries

        tracker = TaskTracker()
        queries = TaskQueries()

        task_id = tracker.create_task("file", "a", "回滚测试")
        op1 = tracker.add_operation(task_id, "create", source_path="/tmp/new.txt")
        op2 = tracker.add_operation(task_id, "delete", source_path="/tmp/old.txt")

        tracker.mark_rolled_back(task_id)

        task = queries.get_task(task_id)
        assert task["status"] == "rolled_back"
        assert task["rolled_back_count"] == 2

        ops = queries.get_operations(task_id)
        assert all(o["status"] == "rollback" for o in ops)

        print("✅ test_rollback_flow passed")
    finally:
        _restore_db(orig)
        _cleanup(path)


if __name__ == "__main__":
    test_full_lifecycle()
    test_multi_intent()
    test_rollback_flow()
    print("\n🎉 All integration tests passed!")
