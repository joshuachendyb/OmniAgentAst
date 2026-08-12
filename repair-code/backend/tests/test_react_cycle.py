# -*- coding: utf-8 -*-
"""
react_cycle 鍗曞厓娴下瘯 鈥?handle_react_error / _classify_error
鍖椾含鑰侀檲 2026-06-25
鏇存新,氬皬娌?2026-06-30 鈥?閫傞厤 handler yield-only 鍗忚
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.agent.react_cycle import handle_react_error
from app.services.llm.error_classifier import SystemErrorClassifier, SystemErrorCategory
from app.services.agent.steps import ErrorStep
from app.services.agent.status_table import AgentStatus


class TestClassifyError:
    """SystemErrorClassifier 错误创嗙被娴下瘯 鈥?小欧 2026-06-30"""

    def test_fc_format_error(self):
        from app.services.llm.core import LLMResponseError
        result = SystemErrorClassifier.classify_error(LLMResponseError(message="bad fc"))
        assert result == SystemErrorCategory.SERVER

    def test_unknown_error(self):
        result = SystemErrorClassifier.classify_error(ValueError("some value error"))
        assert result == SystemErrorCategory.UNKNOWN

    def test_generic_exception(self):
        result = SystemErrorClassifier.classify_error(RuntimeError("generic"))
        assert result == SystemErrorCategory.UNKNOWN

    def test_server_error(self):
        result = SystemErrorClassifier.classify_error(RuntimeError("status_code: 500"))
        assert result == SystemErrorCategory.SERVER

    def test_end_of_stream(self):
        """anyio.EndOfStream(TLS握手失败) → SERVER(retryable) — 小沈 2026-07-05"""
        # 黑名单默认SERVER，不需逐类枚举httpx→httpcore→anyio异常
        class EndOfStream(Exception):
            pass
        result = SystemErrorClassifier.classify_error(EndOfStream())
        assert result == SystemErrorCategory.SERVER
        assert result.is_retryable is True


class TestHandleReactError:
    """server error"""

    def _make_agent(self):
        agent = MagicMock()
        agent.status = AgentStatus.EXECUTING
        return agent

    def test_fc_format_error_creates_error_step(self):
        from app.services.llm.core import LLMResponseError
        agent = self._make_agent()
        result = handle_react_error(agent, LLMResponseError(message="bad fc"), 1)
        assert isinstance(result, ErrorStep)
        assert result.error_type == "server"
        assert agent.status == AgentStatus.EXECUTING

    def test_network_error_creates_error_step(self):
        import httpx
        agent = self._make_agent()
        result = handle_react_error(agent, httpx.ConnectError("refused"), 2)
        assert result.error_type == "server"
        assert agent.status == AgentStatus.EXECUTING

    def test_unknown_error_creates_error_step(self):
        agent = self._make_agent()
        result = handle_react_error(agent, ValueError("oops"), 3)
        assert result.error_type == "unknown"
        assert result.step == 3
        # 銆怉gent鐘舵一佺鐞嗛噸鏋勩一慶hendyg 2026-06-30: handler 一嶈鐘舵一?
        assert agent.status == AgentStatus.EXECUTING  # 鐘舵一佹湭鏀瑰彉

    def test_returns_error_step_with_correct_step_number(self):
        agent = self._make_agent()
        result = handle_react_error(agent, RuntimeError("err"), 42)
        assert result.step == 42
        # 銆怉gent鐘舵一佺鐞嗛噸鏋勩一慶hendyg 2026-06-30: handler 一嶈鐘舵一?
        assert agent.status == AgentStatus.EXECUTING  # 鐘舵一佹湭鏀瑰彉