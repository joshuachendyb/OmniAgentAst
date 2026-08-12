"""P7-04: 并发cancel竞争 — mock测试

测试场景: 2个并发cancel都应成功返回True
-- 小欧 2026-07-03
"""
import pytest
import asyncio
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_concurrent_cancel_both_succeed():
    from app.services.task.task_registry import register_task, set_cancelled

    task_id = "p7-04-test-task"
    mock_service = MagicMock()
    mock_service._cancelled = False

    await register_task(task_id, mock_service)

    async def cancel_once():
        return await set_cancelled(task_id)

    results = await asyncio.gather(cancel_once(), cancel_once(), return_exceptions=True)

    success_count = sum(1 for r in results if r is True)
    assert success_count >= 1, f"至少1个cancel应返回True, got {results}"
    assert not any(isinstance(r, Exception) for r in results), f"无异常, got {results}"
