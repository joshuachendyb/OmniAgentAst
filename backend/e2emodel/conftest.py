"""共享测试fixtures：临时DB、Mock LLM、测试配置、隔离的ToolRegistry"""

import pytest
import tempfile
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import List, Dict, Any, Optional



# ─── 临时数据库 ───────────────────────────────────────────────

@pytest.fixture
def temp_db_dir():
    """每个测试用例独立的临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_db(temp_db_dir, monkeypatch):
    """重定向DatabaseManager到临时目录"""
    monkeypatch.setattr(
        "app.db.database.DatabaseManager._db_dir",
        temp_db_dir,
    )
    from app.db.database import DatabaseManager
    db = DatabaseManager()
    db.init()
    return db


# ─── 隔离的ToolRegistry ──────────────────────────────────────

@pytest.fixture
def fresh_registry():
    """每个测试用例独立的ToolRegistry实例，不污染全局"""
    from app.services.tools.registry import ToolRegistry
    return ToolRegistry()


# ─── Mock LLM客户端 ──────────────────────────────────────────

class MockLLMClient:
    """预设响应队列的Mock LLM客户端"""

    def __init__(self, responses: Optional[List[str]] = None):
        self._responses = list(responses or [])
        self._call_count = 0
        self.model = "test-model"
        self.provider = "test-provider"

    async def _call_llm(self) -> str:
        if self._call_count >= len(self._responses):
            raise RuntimeError(f"MockLLM: no more responses (called {self._call_count} times)")
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp

    def add_response(self, response: str):
        self._responses.append(response)


@pytest.fixture
def mock_llm_client():
    """工厂fixture：可配置响应序列"""
    def _factory(responses: Optional[List[str]] = None):
        return MockLLMClient(responses)
    return _factory


# ─── Mock Agent ──────────────────────────────────────────────

@pytest.fixture
def mock_agent():
    """用于ReAct循环测试的最小Mock Agent"""
    agent = MagicMock()
    agent.status = MagicMock()
    agent.status.value = "idle"
    agent._cancelled = False
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock()
    agent._step_emitter.exit_with_error = MagicMock()
    agent.message_builder = MagicMock()
    agent.message_builder.add_observation = MagicMock()
    agent.llm_call_count = 0
    agent._call_llm = AsyncMock()
    agent._execute_tool = AsyncMock(return_value={"code": 0, "data": "ok", "message": "success"})
    agent._create_cancelled_chunk = MagicMock(return_value=MagicMock())
    agent._on_after_loop = MagicMock()
    agent._complete_tracked_task = MagicMock()
    agent._initialize_run_state = MagicMock(return_value=(MagicMock(), None))
    return agent


# ─── 测试用Step工厂 ─────────────────────────────────────────

@pytest.fixture
def step_factory():
    """快速创建测试用Step对象"""
    from app.services.agent.steps import (
        MetaStep, ThoughtStep, ActionStep, ObservationStep,
        FinalStep, ErrorStep, ChunkStep,
    )

    def _start(step=1, **kwargs):
        defaults = dict(
            step=step, type="start", message="hello",
            display_name="test", provider="test",
            model="test", task_id="t-001",
            security_check={"is_safe": True, "risk_level": "low"},
        )
        defaults.update(kwargs)
        return MetaStep(**defaults)

    def _thought(step=1, content="thinking...", **kwargs):
        defaults = dict(step=step, content=content)
        defaults.update(kwargs)
        return ThoughtStep(**defaults)

    def _action(step=1, tool_name="read_file", tool_params=None, **kwargs):
        defaults = dict(step=step, tool_name=tool_name, tool_params=tool_params or {"path": "x"})
        defaults.update(kwargs)
        return ActionStep(**defaults)

    def _observation(step=1, llm_data=None, tool_result=None, other_data=None, **kwargs):
        defaults = dict(step=step, llm_data=llm_data or {}, tool_result=tool_result, other_data=other_data or {})
        defaults.update(kwargs)
        return ObservationStep(**defaults)

    def _final(step=1, response="done", **kwargs):
        defaults = dict(step=step, response=response)
        defaults.update(kwargs)
        return FinalStep(**defaults)

    def _error(step=1, error_type="runtime_error", error_message="oops", **kwargs):
        defaults = dict(step=step, error_type=error_type, error_message=error_message)
        defaults.update(kwargs)
        return ErrorStep(**defaults)

    def _chunk(step=1, content="chunk text", **kwargs):
        defaults = dict(step=step, content=content)
        defaults.update(kwargs)
        return ChunkStep(**defaults)

    return type("StepFactory", (), {
        "start": _start,
        "thought": _thought,
        "action": _action,
        "observation": _observation,
        "final": _final,
        "error": _error,
        "chunk": _chunk,
    })()


# ─── 自动保存测试报告 ─────────────────────────────────────────

@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """测试结束后自动保存结果摘要到 reports/ 目录"""
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"pytest_report_{timestamp}.log"

    stats = terminalreporter.stats
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    errors = len(stats.get("errors", []))
    skipped = len(stats.get("skipped", []))
    total = passed + failed + errors + skipped

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"Test Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n")
        f.write(f"Total: {total}, Passed: {passed}, Failed: {failed}, Errors: {errors}, Skipped: {skipped}\n")
        if failed > 0:
            f.write(f"\n--- Failures ---\n")
            for fail in stats.get("failed", []):
                f.write(f"  FAIL: {fail.nodeid}\n")
                if fail.longrepr:
                    f.write(f"    {fail.longrepr}\n")
        if errors > 0:
            f.write(f"\n--- Errors ---\n")
            for err in stats.get("errors", []):
                f.write(f"  ERROR: {err.nodeid}\n")
                if err.longrepr:
                    f.write(f"    {err.longrepr}\n")
        f.write(f"{'='*60}\n")
        f.write(f"Exit code: {exitstatus}\n")
