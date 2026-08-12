"""P7-01: 状态机非法转换 — mock测试

测试场景: cancel在的任务调用pause应被拒绝
-- 小欧 2026-07-03
"""
import pytest
import asyncio
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_cancelled_task_cannot_pause():
    from app.services.task.task_registry import register_task, set_cancelled, set_paused
    from app.services.task.task_state import is_task_running

    task_id = "p7-01-test-task"
    mock_service = MagicMock()
    mock_service._cancelled = False

    # Step 1: register
    await register_task(task_id, mock_service)
    assert await is_task_running(task_id)

    # Step 2: cancel
    cancel_ok = await set_cancelled(task_id)
    assert cancel_ok is True

    # Step 3: pause on cancelled task — should fail
    result = await set_paused(task_id)
    assert result["success"] is False
    assert "已被中断" in result["message"]
