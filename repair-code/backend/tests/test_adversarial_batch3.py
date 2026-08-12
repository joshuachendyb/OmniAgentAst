"""test"""
import pytest
from typing import Dict, Any, Optional


class TestParseObservations:
    """test"""

    def test_happy_path(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation(
            {"content": "ok"},
            {"action": {"tool": "read"}, "status": {"exec_code": "success"}, "summary": "done", "duration_ms": 10},
        )
        assert len(result) > 10

    def test_output_none(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation(
            None,
            {"action": {"tool": "read"}, "status": {"exec_code": "success"}, "summary": "done", "duration_ms": 10},
        )
        assert result is not None

    def test_output_empty(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation(
            "",
            {"action": {"tool": "read"}, "status": {"exec_code": "success"}, "summary": "", "duration_ms": 0},
        )
        assert result is not None

    def test_output_dict(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation(
            {"key": "val"},
            {"action": {"tool": "read"}, "status": {"exec_code": "success"}, "summary": "dict", "duration_ms": 5},
        )
        assert result is not None

    def test_status_various(self):
        from app.services.agent.observation_formatter import format_llm_observation
        for code in ["success", "error", "warning", "timeout", "cancelled"]:
            result = format_llm_observation(
                "data",
                {"action": {"tool": "x"}, "status": {"exec_code": code}, "summary": "s", "duration_ms": 1},
            )
            assert result is not None, f"failed for exec_code={code}"

    def test_missing_action(self):
        from app.services.agent.observation_formatter import format_llm_observation
        result = format_llm_observation("data", {})
        assert result is not None









