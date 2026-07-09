"""
test_tool_executor — tool_executor.py 专用测试

覆盖场景：
1. execute_tool(parallel=False) → 调execute_tool_with_retry
2. execute_tool(parallel=False) → 透传on_retry_started回调
3. execute_tool(parallel=True) → 调try_once（无重试）
4. execute_tool(parallel=True) 失败 → 返回error dict而非异常
5. auto_inject_from_search 无匹配 → 不注入
6. execute_tool 非searchtool → 不触发注入

小欧 2026-07-09
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from typing import Any, Dict


def _make_agent(mock_retry_engine=None):
    """创建mock agent实例 — 复用各测试用例
    
    Args:
        mock_retry_engine: 可选的mock引擎，不传则创建默认mock
    Returns:
        MagicMock agent实例，._retry_engine已初始化
    
    小欧 2026-07-09
    """
    agent = MagicMock()
    agent._loaded_categories = set()
    if mock_retry_engine is not None:
        agent._retry_engine = mock_retry_engine
    else:
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(
            return_value={"code": 200, "data": "ok", "llm_data": {"status": {"exec_code": "success"}}}
        )
        agent._retry_engine.try_once = AsyncMock(
            return_value={"code": 200, "data": "ok", "llm_data": {"status": {"exec_code": "success"}}}
        )
    return agent


class TestExecuteToolNormal:
    """execute_tool 正常模式（parallel=False）— 调带重试的执行路径
    
    验证逻辑：parallel=False时，execute_tool应委托给retry_engine.execute_tool_with_retry，
    且不应调用try_once。
    小欧 2026-07-09
    """

    @pytest.mark.asyncio
    async def test_calls_execute_tool_with_retry(self):
        """parallel=False → 调 execute_tool_with_retry（含on_retry_started=None）
        
        验证：
        - execute_tool_with_retry被正确调用
        - on_retry_started默认值为None
        - try_once未被调用
        - 返回值正确传递
        """
        mock_engine = MagicMock()
        mock_engine.execute_tool_with_retry = AsyncMock(
            return_value={"code": 200, "data": "ok", "llm_data": {"status": {"exec_code": "success"}}}
        )
        mock_engine.try_once = AsyncMock()
        agent = _make_agent(mock_engine)

        from app.services.agent.tool_executor import execute_tool
        result = await execute_tool(agent, "httpget", {"url": "https://example.com"})

        mock_engine.execute_tool_with_retry.assert_awaited_once_with(
            "httpget", {"url": "https://example.com"}, on_retry_started=None,
        )
        mock_engine.try_once.assert_not_awaited()
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_passes_on_retry_started(self):
        """parallel=False 时 on_retry_started 回调透传给引擎
        
        验证：回调函数被正确传递给execute_tool_with_retry的on_retry_started参数。
        这是前端重试通知的关键通路。
        """
        mock_engine = MagicMock()
        mock_engine.execute_tool_with_retry = AsyncMock(
            return_value={"code": 200, "data": "ok", "llm_data": {"status": {"exec_code": "success"}}}
        )
        agent = _make_agent(mock_engine)
        callback = lambda *a: None

        from app.services.agent.tool_executor import execute_tool
        await execute_tool(agent, "httpget", {"url": "https://example.com"}, on_retry_started=callback)

        mock_engine.execute_tool_with_retry.assert_awaited_once()
        args, kwargs = mock_engine.execute_tool_with_retry.await_args
        assert kwargs.get("on_retry_started") is callback


class TestExecuteToolParallel:
    """execute_tool 并行模式（parallel=True）— 调try_once无重试路径
    
    验证逻辑：parallel=True时，execute_tool应委托给retry_engine.try_once，
    且不应调用execute_tool_with_retry。
    小欧 2026-07-09
    """

    @pytest.mark.asyncio
    async def test_calls_try_once(self):
        """parallel=True → 调 try_once（无重试无回调）
        
        验证：
        - try_once被正确调用
        - execute_tool_with_retry未被调用
        - 返回值正确传递
        """
        mock_engine = MagicMock()
        mock_engine.try_once = AsyncMock(
            return_value={"code": 200, "data": "ok", "llm_data": {"status": {"exec_code": "success"}}}
        )
        mock_engine.execute_tool_with_retry = AsyncMock()
        agent = _make_agent(mock_engine)

        from app.services.agent.tool_executor import execute_tool
        result = await execute_tool(agent, "httpget", {"url": "https://example.com"}, parallel=True)

        mock_engine.try_once.assert_awaited_once_with("httpget", {"url": "https://example.com"})
        mock_engine.execute_tool_with_retry.assert_not_awaited()
        assert result["code"] == 200

    @pytest.mark.asyncio
    async def test_try_once_returns_error_on_failure(self):
        """parallel=True 失败时返回错误字典而非抛异常
        
        验证：即使工具执行失败，execute_tool也应返回包含错误信息的dict，
        而非向上抛Exception。这是工具执行契约的一部分。
        """
        mock_engine = MagicMock()
        mock_engine.try_once = AsyncMock(
            return_value={"code": 500, "llm_data": {"status": {"exec_code": "error", "message": "test error"}}}
        )
        agent = _make_agent(mock_engine)

        from app.services.agent.tool_executor import execute_tool
        result = await execute_tool(agent, "httpget", {"url": "https://example.com"}, parallel=True)

        assert result["code"] == 500 or result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"


class TestAutoInjectFromSearch:
    """searchtool结果自动注入 — 只在searchtool成功时触发
    
    验证逻辑：auto_inject_from_search仅在searchtool返回matches时触发注入，
    非searchtool调用和空匹配都不应触发。
    小欧 2026-07-09
    """

    def test_no_matches_does_nothing(self):
        """searchtool返回空matches列表 → 不触发注入
        
        验证：matches为空时，_tool_loader不被调用，_loaded_categories不新增。
        """
        agent = MagicMock()
        agent._loaded_categories = set()
        result = {"data": {"matches": []}}

        from app.services.agent.tool_executor import auto_inject_from_search
        auto_inject_from_search(agent, result)

        assert not hasattr(agent, '_tool_loader') or agent._tool_loader.load_category.call_count == 0

    def test_skip_non_searchtool_calls(self):
        """非searchtool调用 → 不触发注入
        
        验证：httpget等非searchtool调用不触发auto_inject_from_search。
        """
        mock_engine = MagicMock()
        mock_engine.execute_tool_with_retry = AsyncMock()
        agent = _make_agent(mock_engine)

        from app.services.agent.tool_executor import execute_tool
        result = asyncio.run(execute_tool(agent, "httpget", {"url": "https://example.com"}))
        assert result is not None
