"""P7-05: 状态变更一致性 — mock测试

测试场景: pause/resume等状态转换符合预期
-- 小欧 2026-07-03
"""
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_full_state_transition_cycle():
    from app.services.task.task_registry import register_task, set_paused, set_resumed, set_cancelled
    from app.services.task.task_state import check_paused, get_task_status

    task_id = "p7-05-test-task"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)
    assert await get_task_status(task_id) == "running"

    await set_paused(task_id)
    assert await get_task_status(task_id) == "paused"
    assert await check_paused(task_id) is True

    await set_resumed(task_id)
    assert await get_task_status(task_id) == "running"
    assert await check_paused(task_id) is False

    await set_cancelled(task_id)
    assert await get_task_status(task_id) == "cancelled"
    assert await get_task_status(task_id) != "running"


@pytest.mark.asyncio
async def test_resume_not_paused_fails():
    from app.services.task.task_registry import register_task, set_resumed

    task_id = "p7-05-test-resume-fail"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)

    result = await set_resumed(task_id)
    assert result["success"] is False
    assert "未暂停" in result["message"]
