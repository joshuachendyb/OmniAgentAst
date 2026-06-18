# -*- coding: utf-8 -*-
"""TaskTracker 业务逻辑深度测试

作者: 小健 日期: 2026-06-09
覆盖: 任务创建/完成/标记失败/操作管理/回滚/报告生成/单例/边界/全链路场景。策略: patch TaskTracker 内部 db 引用替换为指向临时目录的 DatabaseManager
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.services.task.task_tracker import TaskTracker, get_tracker
from app.services.task.models import TaskStatus
from app.db.models.operation_enums import OperationStatus


# ===================================================================
# 辅助工具
# ===================================================================

def _build_tracker_db(temp_dir):
    """创建临时数据库，每次调用独立目录"""
    from app.db.database import DatabaseManager
    from app.db.db_initializer import init_task_tracker_db
    dm = DatabaseManager()
    # 直接重定向实例的 db_dir ?db_paths
    dm._db_dir = Path(temp_dir)
    dm._db_paths = {
        "chat": Path(temp_dir) / "chat_history.db",
        "operations": Path(temp_dir) / "operations.db",
        "observer": Path(temp_dir) / "tool_observer.db",
        "task_tracker": Path(temp_dir) / "task_tracker.db",
    }
    init_task_tracker_db(dm.get_conn)
    return dm


def _patch_tracker_db(dm):
    """替换 task_tracker 模块内部的 db 引用为 dm 实例    返回 patch context manager    """
    return patch("app.services.task.task_tracker.db", dm)


def _insert_task(conn, task_id, intent="file", agent_id="agent-001",
                  description="test task", status="executing"):
    conn.execute(
        "INSERT INTO tasks (task_id, intent, agent_id, task_description, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (task_id, intent, agent_id, description, status),
    )


def _insert_operation(conn, task_id, operation_id=None, seq=1,
                      operation_type="create", status="success"):
    if operation_id is None:
        operation_id = f"op-{uuid4().hex}"
    conn.execute(
        "INSERT INTO operations "
        "(operation_id, task_id, operation_type, status, sequence_number) "
        "VALUES (?, ?, ?, ?, ?)",
        (operation_id, task_id, operation_type, status, seq),
    )
    # 同步更新 total_operations（与 add_operation 行为一致）
    conn.execute(
        "UPDATE tasks SET total_operations = total_operations + 1 WHERE task_id = ?",
        (task_id,),
    )
    return operation_id


# ===================================================================
# Fixture: 为每个测试准备独立的临时 DB + patch
# ===================================================================

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def tracker(temp_dir):
    """返回 (tracker, dm) 对，tracker 已绑定到 temp_dir 的 DB"""
    dm = _build_tracker_db(temp_dir)
    with _patch_tracker_db(dm):
        t = TaskTracker()
        yield t, dm


# ===================================================================
# 第一层：create_task ?任务创建
# ===================================================================

class TestCreateTask:
    """测试 TaskTracker.create_task()"""

    def test_create_task_returns_id(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "创建文件")
        assert task_id.startswith("task-")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT task_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row is not None

    def test_create_task_stores_correct_status(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "执行命令")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.EXECUTING.value

    def test_create_task_stores_empty_intent(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "文档任务")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT intent FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == ""

    def test_create_task_stores_agent_id(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "描述")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT agent_id FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == "agent-001"

    def test_create_task_stores_description(self, tracker):
        t, dm = tracker
        desc = "这是一段很长的任务描述内容"
        task_id = t.create_task("agent-001", desc)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT task_description FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == desc

    def test_create_task_unique_id(self, tracker):
        t, dm = tracker
        ids = set()
        for _ in range(10):
            task_id = t.create_task("agent-001", "重复创建")
            ids.add(task_id)
        assert len(ids) == 10

    def test_create_task_default_counter_zero(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "初始检查")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT total_operations FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 0


# ===================================================================
# 第二层：complete_task ?任务完成
# ===================================================================

class TestCompleteTask:
    """测试 TaskTracker.complete_task()"""

    def test_complete_task_success(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "完成任务")
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status, completed_at, success_count FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == TaskStatus.SUCCESS.value
            assert row[1] is not None
            assert row[2] == 0

    def test_complete_task_failed(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "失败任务")
        t.complete_task(task_id, success=False)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.FAILED.value

    def test_complete_task_with_success_operations(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "有操作的任务")
        with dm.get_conn("task_tracker") as conn:
            _insert_operation(conn, task_id, status="success")
            _insert_operation(conn, task_id, status="success")
            _insert_operation(conn, task_id, status="failed")
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT success_count FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 2

    def test_complete_task_nonexistent(self, tracker):
        t, dm = tracker
        t.complete_task("task-nonexistent", success=True)

    def test_complete_task_updates_timestamp(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT completed_at FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] is not None


# ===================================================================
# 第三层：mark_failed ?操作失败标记
# ===================================================================

class TestMarkFailed:
    """测试 TaskTracker.add_operation() 的失败状态(替代已删除的mark_failed)"""

    def test_add_operation_with_failed_status(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "失败状态测试")
        t.add_operation(task_id, "test_tool", status=OperationStatus.FAILED.value, error="模拟错误")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status, error FROM operations WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == OperationStatus.FAILED.value
            assert row[1] == "模拟错误"

    def test_failed_operation_increments_task_failed_count(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "失败计数测试")
        t.add_operation(task_id, "tool_a", status=OperationStatus.SUCCESS.value)
        t.add_operation(task_id, "tool_b", status=OperationStatus.FAILED.value)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT failed_count, total_operations FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == 1, f"期望 failed_count=1, 实际={row[0]}"
            assert row[1] == 2, f"期望 total_operations=2, 实际={row[1]}"


# ===================================================================
# 第四层：add_operation ?操作记录
# ===================================================================

class TestAddOperation:
    """测试 TaskTracker.add_operation()"""

    def test_add_operation_inserts_record(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "操作测试")
        op_id = t.add_operation(
            task_id, "create",
            source_path="src/file.txt",
            destination_path="dst/file.txt",
            file_size=1024,
        )
        assert op_id.startswith("op-")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT source_path, destination_path, file_size FROM operations "
                "WHERE operation_id = ?", (op_id,),
            ).fetchone()
            assert row[0] == "src/file.txt"
            assert row[1] == "dst/file.txt"
            assert row[2] == 1024

    def test_add_operation_increments_sequence(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "序列测试")
        op1 = t.add_operation(task_id, "create")
        op2 = t.add_operation(task_id, "modify")
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT sequence_number FROM operations WHERE task_id = ? "
                "ORDER BY sequence_number", (task_id,),
            ).fetchall()
            assert rows[0][0] == 1
            assert rows[1][0] == 2

    def test_add_operation_increments_task_total(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "总数测试")
        t.add_operation(task_id, "create")
        t.add_operation(task_id, "modify")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT total_operations FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 2

    def test_add_operation_not_found_task(self, tracker):
        t, dm = tracker
        with pytest.raises(ValueError, match="not found"):
            t.add_operation("task-does-not-exist", "create")

    def test_add_operation_stores_details_json(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "详情测试")
        details = {"key1": "value1", "key2": 42}
        op_id = t.add_operation(task_id, "modify", details=details)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT details FROM operations WHERE operation_id = ?", (op_id,),
            ).fetchone()
            stored = json.loads(row[0])
            assert stored == details

    def test_add_operation_with_all_params(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        op_id = t.add_operation(
            task_id, "copy",
            source_path="/src/a",
            destination_path="/dst/a",
            backup_path="/bak/a",
            file_size=2048,
            file_hash="abc123",
            details={"extra": "info"},
        )
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT source_path, destination_path, backup_path, "
                "file_size, file_hash FROM operations WHERE operation_id = ?",
                (op_id,),
            ).fetchone()
            assert (row[0] == "/src/a" and row[1] == "/dst/a"
                    and row[2] == "/bak/a" and row[3] == 2048
                    and row[4] == "abc123")


# ===================================================================
# 第五层：mark_rolled_back ?回滚标记
# ===================================================================

class TestMarkRolledBack:
    """测试 TaskTracker.mark_rolled_back()"""

    def test_mark_rolled_back_specific_ops(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "回滚测试")
        with dm.get_conn("task_tracker") as conn:
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id, [op1])
        with dm.get_conn("task_tracker") as conn:
            row1 = conn.execute(
                "SELECT status FROM operations WHERE operation_id = ?", (op1,),
            ).fetchone()
            row2 = conn.execute(
                "SELECT status FROM operations WHERE operation_id = ?", (op2,),
            ).fetchone()
            assert row1[0] == OperationStatus.ROLLBACK.value
            assert row2[0] == "success"

    def test_mark_rolled_back_all_ops(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        with dm.get_conn("task_tracker") as conn:
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id, [op1, op2])
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.ROLLED_BACK.value

    def test_mark_rolled_back_partial(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "部分回滚测试")
        with dm.get_conn("task_tracker") as conn:
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")
            op3 = _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id, [op1, op2])
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.PARTIALLY_ROLLED_BACK.value

    def test_mark_rolled_back_no_op_ids_all(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "全量回滚测试")
        with dm.get_conn("task_tracker") as conn:
            _insert_operation(conn, task_id, status="success")
            _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id)
        with dm.get_conn("task_tracker") as conn:
            ops = conn.execute(
                "SELECT status FROM operations WHERE task_id = ?", (task_id,)
            ).fetchall()
            for row in ops:
                assert row[0] == OperationStatus.ROLLBACK.value

    def test_mark_rolled_back_updates_rolled_back_count(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "计数回滚测试")
        with dm.get_conn("task_tracker") as conn:
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id, [op1])
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT rolled_back_count FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 1


# ===================================================================
# 第六层：mark_report_generated ?报告生成标记
# ===================================================================

class TestMarkReportGenerated:
    """测试 TaskTracker.mark_report_generated()"""

    def test_report_generated_sets_path(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "报告测试")
        t.mark_report_generated(task_id, "/path/to/report.pdf")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT report_generated, report_path FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == 1
            assert row[1] == "/path/to/report.pdf"

    def test_report_generated_sets_flag(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "报告标记测试")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT report_generated FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 0
        t.mark_report_generated(task_id, "/path/to/report.pdf")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT report_generated FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 1


# ===================================================================
# 第七层：get_task ?任务查询
# ===================================================================

class TestGetTask:
    """测试 TaskTracker 任务查询能力"""

    def test_task_stored_and_retrievable(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "可查任务")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT task_id, intent, agent_id, status FROM tasks "
                "WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row is not None
            assert row[0] == task_id
            assert row[1] == ""
            assert row[2] == "agent-001"
            assert row[3] == TaskStatus.EXECUTING.value

    def test_nonexistent_task_not_found(self, tracker):
        t, dm = tracker
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?", ("task-never-created",)
            ).fetchone()
            assert row is None

    def test_task_after_status_change(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.SUCCESS.value


# ===================================================================
# 第八层：list_tasks ?任务列表查询
# ===================================================================

class TestListTasks:
    """测试 TaskTracker 任务列表能力"""

    def test_list_all_tasks(self, tracker):
        t, dm = tracker
        t.create_task("agent-001", "任务A")
        t.create_task("agent-001", "任务B")
        t.create_task("agent-001", "任务C")
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute("SELECT task_id FROM tasks").fetchall()
            assert len(rows) == 3

    def test_list_filtered_by_empty_intent(self, tracker):
        t, dm = tracker
        t.create_task("agent-001", "文件任务1")
        t.create_task("agent-001", "Shell任务")
        t.create_task("agent-001", "文件任务2")
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute(
                "SELECT task_id FROM tasks WHERE intent = ?", ("",)
            ).fetchall()
            assert len(rows) == 3

    def test_list_limited_results(self, tracker):
        t, dm = tracker
        for i in range(5):
            t.create_task("agent-001", f"任务{i}")
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute("SELECT task_id FROM tasks LIMIT 3").fetchall()
            assert len(rows) == 3

    def test_list_no_tasks_returns_empty(self, tracker):
        t, dm = tracker
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute("SELECT task_id FROM tasks").fetchall()
            assert len(rows) == 0

    def test_list_mixed_statuses(self, tracker):
        t, dm = tracker
        task1 = t.create_task("agent-001", "fixed")
        task2 = t.create_task("agent-001", "fixed")
        t.complete_task(task2, success=True)
        with dm.get_conn("task_tracker") as conn:
            rows = conn.execute("SELECT task_id FROM tasks").fetchall()
            assert len(rows) == 2
            ids = {r[0] for r in rows}
            assert task1 in ids
            assert task2 in ids


# ===================================================================
# 第九层：get_tracker ?单例工厂
# ===================================================================

class TestGetTrackerSingleton:
    """测试 TaskTracker 单例工厂"""

    def test_get_tracker_returns_instance(self):
        import app.services.task.task_tracker as tt_mod
        original = tt_mod._tracker
        try:
            tt_mod._tracker = None
            tracker = get_tracker()
            assert isinstance(tracker, TaskTracker)
        finally:
            tt_mod._tracker = original

    def test_get_tracker_is_singleton(self):
        import app.services.task.task_tracker as tt_mod
        original = tt_mod._tracker
        try:
            tt_mod._tracker = None
            t1 = get_tracker()
            t2 = get_tracker()
            assert t1 is t2
        finally:
            tt_mod._tracker = original


# ===================================================================
# 第十层：边界与异常场景# ===================================================================

class TestEdgeCases:
    """边界情况和异常处理"""

    def test_add_operation_with_none_params(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "None参数测试")
        op_id = t.add_operation(task_id, "create")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT source_path, file_hash FROM operations "
                "WHERE operation_id = ?", (op_id,)
            ).fetchone()
            assert row[0] is None
            assert row[1] is None

    def test_add_operation_failed_on_nonexistent_task(self, tracker):
        t, dm = tracker
        import pytest
        with pytest.raises(ValueError, match="not found"):
            t.add_operation("task-never-created", "tool_x", status=OperationStatus.FAILED.value)

    def test_complete_task_twice(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "重复完成测试")
        t.complete_task(task_id, success=True)
        t.complete_task(task_id, success=False)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.FAILED.value

    def test_add_operation_with_empty_details(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        op_id = t.add_operation(task_id, "create", details=None)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT details FROM operations WHERE operation_id = ?", (op_id,)
            ).fetchone()
            assert row[0] is None

    def test_operations_per_task_isolation(self, tracker):
        t, dm = tracker
        task1 = t.create_task("agent-001", "任务1")
        task2 = t.create_task("agent-001", "任务2")
        t.add_operation(task1, "create")
        t.add_operation(task1, "modify")
        t.add_operation(task2, "delete")
        with dm.get_conn("task_tracker") as conn:
            count1 = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE task_id = ?", (task1,)
            ).fetchone()[0]
            count2 = conn.execute(
                "SELECT COUNT(*) FROM operations WHERE task_id = ?", (task2,)
            ).fetchone()[0]
            assert count1 == 2
            assert count2 == 1

    def test_mark_rolled_back_no_ops_for_task(self, tracker):
        t, dm = tracker
        t.create_task("agent-001", "fixed")
        t.mark_rolled_back("task-" + uuid4().hex)


# ===================================================================
# 第十一层：完整业务流程集成测试# ===================================================================

class TestFullBusinessFlows:
    """完整业务流程端到端测试"""

    def test_full_task_lifecycle(self, tracker):
        """创建 操作 失败 回滚 报告 全链路测试"""
        t, dm = tracker

        task_id = t.create_task("agent-001", "完整流程测试")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.EXECUTING.value
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")

        # 使用add_operation的FAILED状态替代已删除的mark_failed
        op3 = t.add_operation(task_id, "delete_file", status=OperationStatus.FAILED.value, error="文件不存在")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT failed_count FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == 1

        t.mark_rolled_back(task_id, [op1, op2, op3])
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.ROLLED_BACK.value

        t.mark_report_generated(task_id, "/reports/test.pdf")
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT report_generated, report_path FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == 1
            assert row[1] == "/reports/test.pdf"

    def test_task_with_partial_rollback_then_complete(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "fixed")
        with dm.get_conn("task_tracker") as conn:
            op1 = _insert_operation(conn, task_id, status="success")
            op2 = _insert_operation(conn, task_id, status="success")
        t.mark_rolled_back(task_id, [op1])
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.PARTIALLY_ROLLED_BACK.value
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            assert row[0] == TaskStatus.SUCCESS.value

    def test_multiple_tasks_independent_state(self, tracker):
        t, dm = tracker
        task1 = t.create_task("agent-001", "独立任务1")
        task2 = t.create_task("agent-001", "独立任务2")
        t.complete_task(task1, success=True)
        with dm.get_conn("task_tracker") as conn:
            row1 = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task1,)
            ).fetchone()
            row2 = conn.execute(
                "SELECT status FROM tasks WHERE task_id = ?", (task2,)
            ).fetchone()
            assert row1[0] == TaskStatus.SUCCESS.value
            assert row2[0] == TaskStatus.EXECUTING.value

    def test_add_operation_and_complete_with_count(self, tracker):
        t, dm = tracker
        task_id = t.create_task("agent-001", "计数完成测试")
        with dm.get_conn("task_tracker") as conn:
            _insert_operation(conn, task_id, status="success")
            _insert_operation(conn, task_id, status="success")
            _insert_operation(conn, task_id, status="success")
        t.complete_task(task_id, success=True)
        with dm.get_conn("task_tracker") as conn:
            row = conn.execute(
                "SELECT success_count, total_operations FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            assert row[0] == 3
            assert row[1] == 3


# ===================================================================
# 第十二层：并发与线程安全（单例层面）
# ===================================================================

class TestThreadSafety:
    """线程安全性测试"""

    def test_get_tracker_thread_safe(self):
        import threading
        import app.services.task.task_tracker as tt_mod
        original = tt_mod._tracker
        results = []

        def acquire_tracker():
            t = get_tracker()
            results.append(id(t))

        try:
            tt_mod._tracker = None
            threads = [threading.Thread(target=acquire_tracker) for _ in range(5)]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
            assert len(set(results)) == 1
        finally:
            tt_mod._tracker = original
