"""test"""
import asyncio
import inspect
import pytest
from typing import Any, Dict


# =============================================================================
# _build_retry_error 鈥?输照晫输撳入
# =============================================================================

class TestBuildRetryError:
    def _engine(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools={})

    def test_empty_message(self):
        eng = self._engine()
        result = eng._build_retry_error("ERR_TEST", "", 0, error_type="test")
        assert isinstance(result, dict)
        assert result["llm_data"]["status"]["detail"] == ""

    def test_long_message_truncated(self):
        eng = self._engine()
        long_msg = "x" * 500
        result = eng._build_retry_error("ERR_TEST", long_msg, 5, error_type="test")
        assert len(result["llm_data"]["summary"]) <= 200

    def test_negative_retry_count(self):
        eng = self._engine()
        result = eng._build_retry_error("ERR", "msg", -1, error_type="test")
        assert result["other_data"]["retry_count"] == -1

    def test_no_error_type_defaults_to_unknown(self):
        eng = self._engine()
        result = eng._build_retry_error("ERR", "msg", 0)
        assert result.get("error_type") == "unknown"


# =============================================================================
# _get_retry_config 鈥?未煡action
# =============================================================================

class TestGetRetryConfig:
    def _engine(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools={})

    def test_unknown_action_uses_default(self):
        eng = self._engine()
        max_r, backoff, errors, timeout = eng._get_retry_config("nonexistent_tool_xyz")
        assert isinstance(max_r, int)
        assert max_r >= 0


# =============================================================================
# _validate_params 鈥?输照晫输撳入
# =============================================================================

class TestValidateParams:
    def _engine(self, tools=None):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools=tools or {})

    def test_empty_input(self):
        eng = self._engine()
        tool = lambda **kw: None
        result = eng._validate_params("test", {}, tool)
        assert result == {}

    def test_input_with_extra_params(self):
        eng = self._engine()
        tool = lambda **kw: None
        result = eng._validate_params("test", {"x": 1}, tool)
        assert result == {"x": 1}

    # #17: 非法参数错误消息含合法参数名+类型
    def test_invalid_params_message_contains_valid_params(self):
        from unittest.mock import patch, MagicMock
        eng = self._engine()
        tool = lambda **kw: None
        with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
            meta = MagicMock()
            meta.input_schema = {
                "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
                "required": [],
            }
            mock_gt.return_value = meta
            result = eng._validate_params("readtext", {"bad_param": 1}, tool)
            assert isinstance(result, dict)
            detail = result.get("llm_data", {}).get("status", {}).get("detail", "")
            assert "合法参数" in detail
            assert "path: string" in detail
            assert "limit: integer" in detail

    # #17: 类型错误消息指出具体参数名+期望类型+实际类型
    def test_type_error_message_contains_param_type_mismatch(self):
        from unittest.mock import patch, MagicMock
        eng = self._engine()
        tool = lambda **kw: None
        with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
            meta = MagicMock()
            meta.input_schema = {
                "properties": {"limit": {"type": "integer"}},
                "required": [],
            }
            mock_gt.return_value = meta
            result = eng._validate_params("readtext", {"limit": "not_an_int"}, tool)
            assert isinstance(result, dict)
            detail = result.get("llm_data", {}).get("status", {}).get("detail", "")
            assert "期望类型为" in detail
            assert "integer" in detail


# =============================================================================
# _execute_tool_once 鈥?sync/async宸ュ叿输照晫
# =============================================================================

class TestExecuteToolOnce:
    def _engine(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools={})

    @pytest.mark.asyncio
    async def test_sync_tool(self):
        eng = self._engine()
        def sync_tool(**kw):
            return {"result": kw.get("x", 0) * 2}
        result = await eng._execute_tool_once(sync_tool, {"x": 21}, timeout=5)
        assert result == {"result": 42}

    @pytest.mark.asyncio
    async def test_sync_tool_with_exception(self):
        eng = self._engine()
        def sync_tool(**kw):
            raise ValueError(f"bad {kw}")
        with pytest.raises(ValueError, match="bad"):
            await eng._execute_tool_once(sync_tool, {"x": 1}, timeout=5)

    @pytest.mark.asyncio
    async def test_async_tool(self):
        eng = self._engine()
        async def async_tool(**kw):
            await asyncio.sleep(0.001)
            return {"result": kw.get("x")}
        result = await eng._execute_tool_once(async_tool, {"x": 99}, timeout=5)
        assert result == {"result": 99}

    @pytest.mark.asyncio
    async def test_sync_tool_returns_coroutine(self):
        eng = self._engine()
        async def inner():
            return "coro_result"
        def sync_wrapper(**kw):
            return inner()
        result = await eng._execute_tool_once(sync_wrapper, {}, timeout=5)
        assert result == "coro_result"

    @pytest.mark.asyncio
    async def test_timeout(self):
        eng = self._engine()
        async def slow_tool(**kw):
            await asyncio.sleep(10)
            return kw
        with pytest.raises(asyncio.TimeoutError):
            await eng._execute_tool_once(slow_tool, {}, timeout=0.01)


# =============================================================================
# execute_tool_with_retry 鈥?完整娴佺▼


# =============================================================================
# execute_tool_with_retry 鈥?完整娴佺▼
# =============================================================================

class TestExecuteToolWithRetry:
    def _engine(self, tools=None):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools=tools or {})

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        eng = self._engine()
        result = await eng.execute_tool_with_retry("nonexistent", {})
        assert result.get("error_type") == "tool_not_found"

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        async def my_tool(**kw):
            return {"result": kw.get("x", 0) * 2}
        eng = self._engine(tools={"my_tool": my_tool})
        result = await eng.execute_tool_with_retry("my_tool", {"x": 21})
        assert result["result"] == 42

    @pytest.mark.asyncio
    async def test_non_dict_result_not_crashing_downstream(self):
        async def str_tool(**kw):
            return "just a string"
        eng = self._engine(tools={"str_tool": str_tool})
        result = await eng.execute_tool_with_retry("str_tool", {})
        assert result == "just a string"

    @pytest.mark.asyncio
    async def test_retries_exhausted(self):
        call_count = [0]
        async def always_fail(**kw):
            call_count[0] += 1
            raise ConnectionError("always fail")
        eng = self._engine(tools={"always_fail": always_fail})
        result = await eng.execute_tool_with_retry("always_fail", {})
        assert isinstance(result, dict)
        assert result.get("error_type") is not None


# =============================================================================
# _execute_tool_once 鈥?宸ュ叿名有暟中篘one,圔ug 9鍊欓查夛級
# =============================================================================

class TestExecuteToolWithRetryEdgeInputs:
    """input with extra params"""
    @pytest.mark.asyncio
    async def test_edge_params(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        async def my_tool(**kw):
            return {"result": kw}
        eng = ToolRetryEngine(tools={"my_tool": my_tool})
        with pytest.raises((AttributeError, TypeError)):
            await eng.execute_tool_with_retry("my_tool", None)
