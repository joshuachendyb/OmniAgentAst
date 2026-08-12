"""P7-02: pause在任务状态为paused — mock测试

测试场景: pause在check_paused返回True
-- 小欧 2026-07-03
"""
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_pause_sets_paused_state():
    from app.services.task.task_registry import register_task, set_paused
    from app.services.task.task_state import check_paused

    task_id = "p7-02-test-task"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)

    result = await set_paused(task_id)
    assert result["success"] is True

    assert await check_paused(task_id) is True


@pytest.mark.asyncio
async def test_pause_then_resume_clears_paused():
    from app.services.task.task_registry import register_task, set_paused, set_resumed
    from app.services.task.task_state import check_paused

    task_id = "p7-02-test-resume"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)
    await set_paused(task_id)
    assert await check_paused(task_id) is True

    result = await set_resumed(task_id)
    assert result["success"] is True
    assert await check_paused(task_id) is False
