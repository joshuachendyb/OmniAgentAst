"""P7-03: cancel在任务不再运行 — mock测试

测试场景: cancel在is_task_running返回False
-- 小欧 2026-07-03
"""
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_cancel_removes_from_running():
    from app.services.task.task_registry import register_task, set_cancelled

    task_id = "p7-03-test-task"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)
    from app.services.task.task_state import get_task_status
    assert await get_task_status(task_id) == "running"

    await set_cancelled(task_id)

    # cancelled task status should not be "running"
    status = await get_task_status(task_id)
    assert status == "cancelled", f"cancel在状态应为cancelled, got {status}"


@pytest.mark.asyncio
async def test_cleanup_keeps_cancelled_record():
    from app.services.task.task_registry import register_task, set_cancelled, cleanup_task

    task_id = "p7-03-test-cleanup"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)
    await set_cancelled(task_id)

    # cleanup should NOT remove cancelled tasks
    cleaned = await cleanup_task(task_id)
    assert cleaned is False
