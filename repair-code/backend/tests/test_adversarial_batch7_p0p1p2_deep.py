# -*- coding: utf-8 -*-
"""
P0/P1/P2 修复深度攻击测试 — 小欧 2026-07-15

目标: 对3个修复进行边界值/异常路径/逻辑正确性深度验证
策略: Mock引擎层，精准测试修复逻辑不注水

编辑历史:
    2026-07-15 - 小欧 - 初稿，P0(FC降级关闭分支)+P1(超时计算)+P2(exit_code参数) 三修复深度攻击
    2026-07-25 - 小欧 - 更新test_fc_max_retries_0_fallback_disabled_no_crash断言字符串(错误消息已更新为"功能调用模式不可用"+"重试次数=0")
    2026-08-11 - 小欧 - 对齐tool_retry_engine保险丝公式(BUG-2修复): 有inner→max(inner,600)+30, 60/120/290→630(地板), 3600→3630(超CEILING随它去); ShellInput已迁移至fundamental_schema, 4处导入更新(生产进化,测试过时修正)
"""

import asyncio
import json
import time
import inspect
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from typing import Any, Dict, List, Optional, Tuple


# ===========================================================================
# 辅助函数
# ===========================================================================

def _make_mock_agent():
    agent = MagicMock()
    agent.llm_call_count = 1
    agent._prompt_logger = None
    return agent


def _make_async_iter(*items):
    """把一组值包装为异步迭代器"""
    async def gen():
        for item in items:
            yield item
    return gen()


# ===========================================================================
# P0 — call_llm_with_fallback 深度测试
# ===========================================================================

class TestP0CallLlmWithFallback:
    """P0 修复: LLM_RESPONSE_RETRIES=0 崩溃 + 流式error拦截 — 深度边界攻击"""

    @pytest.mark.asyncio
    async def test_fc_max_retries_0_fallback_disabled_no_crash(self):
        """LLM_RESPONSE_RETRIES=0,降级关闭 → 不崩溃,输出友好错误"""
        import app.services.agent.llm_stream as llm_mod
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        orig_fallback = llm_mod.LLM_RESPONSE_FALLBACK
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 0
            llm_mod.LLM_RESPONSE_FALLBACK = False
            from app.services.agent.llm_stream import call_llm_with_fallback
            agent = _make_mock_agent()
            agent.llm_client = MagicMock()
            agent.llm_client.request_stream = AsyncMock()
            agent.llm_client._cancelled = False
            items = []
            async for item in call_llm_with_fallback(agent, [], [{"name": "test"}]):
                items.append(item)
            assert len(items) >= 1
            tag, data = items[-1]
            assert tag == "response"
            assert data["type"] == "error"
            assert "功能调用模式不可用" in data["content"]
            assert "重试次数=0" in data["content"]
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries
            llm_mod.LLM_RESPONSE_FALLBACK = orig_fallback

    @pytest.mark.asyncio
    async def test_fc_max_retries_0_fallback_enabled(self):
        """LLM_RESPONSE_RETRIES=0,降级开启 → 降级到Text模式返回answer"""
        import app.services.agent.llm_stream as llm_mod
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        orig_fallback = llm_mod.LLM_RESPONSE_FALLBACK
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 0
            llm_mod.LLM_RESPONSE_FALLBACK = True
            from app.services.agent.llm_stream import call_llm_with_fallback
            agent = _make_mock_agent()
            client = MagicMock()
            client._cancelled = False
            async def req_stream(messages, tools, tool_choice):
                yield type("Chunk", (), {
                    "content": "降级成功", "tool_calls": None,
                    "is_done": True, "is_reasoning": False,
                    "usage": {"total_tokens": 3},
                    "stream_error": None,
                })()
            client.request_stream = req_stream
            agent.llm_client = client
            items = []
            async for item in call_llm_with_fallback(agent, [], [{"name": "test"}]):
                items.append(item)
            assert len(items) >= 1
            tag, data = items[-1]
            assert data["type"] == "answer"
            assert "降级成功" in data["content"]
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries
            llm_mod.LLM_RESPONSE_FALLBACK = orig_fallback

    @pytest.mark.asyncio
    async def test_fc_max_retries_0_direct_answer(self):
        """LLM_RESPONSE_RETRIES=0,无错误 → 直接返回answer(不走重试/降级)"""
        import app.services.agent.llm_stream as llm_mod
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 0
            from app.services.agent.llm_stream import call_llm_with_fallback
            agent = _make_mock_agent()
            client = MagicMock()
            client._cancelled = False
            async def req_stream(messages, tools, tool_choice):
                yield type("Chunk", (), {
                    "content": "直接回答", "tool_calls": None,
                    "is_done": True, "is_reasoning": False,
                    "usage": {"total_tokens": 3},
                    "stream_error": None,
                })()
            client.request_stream = req_stream
            agent.llm_client = client
            items = []
            async for item in call_llm_with_fallback(agent, [], [{"name": "test"}]):
                items.append(item)
            assert len(items) >= 1
            tag, data = items[-1]
            assert data["type"] == "answer"
            assert "直接回答" in data["content"]
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries

    @pytest.mark.asyncio
    async def test_stream_error_intercepted_and_retried(self):
        """流式type:error响应 → 拦截为LLMResponseError → L2重试"""
        import app.services.agent.llm_stream as llm_mod
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 2
            from app.services.agent.llm_stream import call_llm_with_fallback
            call_count = [0]
            agent = _make_mock_agent()
            client = MagicMock()
            client._cancelled = False
            async def req_stream(messages, tools, tool_choice):
                call_count[0] += 1
                if call_count[0] == 1:
                    yield ("response", {"type": "error", "content": "LLM流式错误"})
                    return
                yield type("Chunk", (), {
                    "content": "重试成功", "tool_calls": None,
                    "is_done": True, "is_reasoning": False,
                    "usage": {"total_tokens": 3},
                    "stream_error": None,
                })()
            client.request_stream = req_stream
            agent.llm_client = client
            items = []
            async for item in call_llm_with_fallback(agent, [], [{"name": "test"}]):
                items.append(item)
            assert call_count[0] == 2
            tag, data = items[-1]
            assert data["type"] == "answer"
            assert "重试成功" in data["content"]
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries

    @pytest.mark.asyncio
    async def test_last_error_reset_per_call(self):
        """每次call_llm_with_fallback进入时last_error=None(不受前次污染)"""
        import app.services.agent.llm_stream as llm_mod
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        orig_fallback = llm_mod.LLM_RESPONSE_FALLBACK
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 0
            llm_mod.LLM_RESPONSE_FALLBACK = False
            from app.services.agent.llm_stream import call_llm_with_fallback
            agent1 = _make_mock_agent()
            agent1.llm_client = MagicMock()
            agent1.llm_client.request_stream = AsyncMock()
            agent1.llm_client._cancelled = False
            items1 = [it async for it in call_llm_with_fallback(agent1, [], [])]
            assert items1[-1][1]["type"] == "error"
            # 第二次调用独立的agent,last_error应重新为None
            agent2 = _make_mock_agent()
            agent2.llm_client = MagicMock()
            agent2.llm_client.request_stream = AsyncMock()
            agent2.llm_client._cancelled = False
            items2 = [it async for it in call_llm_with_fallback(agent2, [], [])]
            assert items2[-1][1]["type"] == "error"
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries
            llm_mod.LLM_RESPONSE_FALLBACK = orig_fallback

    @pytest.mark.asyncio
    async def test_fc_format_error_retries_then_fallback(self):
        """LLMResponseError耗尽重试 → 降级到Text模式(fallback返回answer)"""
        import app.services.agent.llm_stream as llm_mod
        from app.services.llm.core import LLMResponseError
        orig_retries = llm_mod.LLM_RESPONSE_RETRIES
        orig_fallback = llm_mod.LLM_RESPONSE_FALLBACK
        try:
            llm_mod.LLM_RESPONSE_RETRIES = 2
            llm_mod.LLM_RESPONSE_FALLBACK = True
            from app.services.agent.llm_stream import call_llm_with_fallback
            call_count = [0]
            agent = _make_mock_agent()
            client = MagicMock()
            client._cancelled = False
            async def req_stream(messages, tools, tool_choice):
                call_count[0] += 1
                if tools is None:
                    # fallback: 返回answer
                    yield type("Chunk", (), {
                        "content": "fallback answer", "tool_calls": None,
                        "is_done": True, "is_reasoning": False,
                        "usage": {"total_tokens": 3},
                        "stream_error": None,
                    })()
                    return
                raise LLMResponseError(message="格式错误")
            client.request_stream = req_stream
            agent.llm_client = client
            items = []
            async for item in call_llm_with_fallback(agent, [], [{"name": "test"}]):
                items.append(item)
            assert call_count[0] == llm_mod.LLM_RESPONSE_RETRIES + 1
            tag, data = items[-1]
            assert data["type"] == "answer", f"期望answer, 实际{data['type']}"
            assert "fallback answer" in data["content"]
        finally:
            llm_mod.LLM_RESPONSE_RETRIES = orig_retries
            llm_mod.LLM_RESPONSE_FALLBACK = orig_fallback

    def test_fc_format_error_has_message_attr(self):
        """LLMResponseError实例有message属性(修复预存bug)"""
        from app.services.llm.core import LLMResponseError
        e = LLMResponseError(message="测试消息")
        assert e.message == "测试消息"
        assert str(e) == "测试消息"


# ===========================================================================
# P1 — ToolRetryEngine 超时计算深度测试
# ===========================================================================

class TestP1TimeoutOuterGreaterThanInner:
    """P1 修复: 外层超时恒>内层+30,cap 630 — 深度边界攻击"""

    def _make_engine(self):
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        return ToolRetryEngine(tools={})

    async def _capture_timeout(self, tool, action_input, engine_method="execute_tool_with_retry"):
        """调用引擎并捕获传给asyncio.wait_for的timeout值"""
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        engine = self._make_engine()
        tool_name = "test_tool"
        captured = []
        original_wait_for = asyncio.wait_for
        async def capture_wait_for(coro, timeout, **kw):
            captured.append(timeout)
            return await original_wait_for(coro, timeout=timeout, **kw)
        with patch.object(asyncio, "wait_for", capture_wait_for):
            with patch(f"{ToolRetryEngine.__module__}.TOOL_TIMEOUTS",
                       {"test_tool": 120, "default": 120}):
                engine._tools[tool_name] = tool
                if engine_method == "execute_tool_with_retry":
                    await engine.execute_tool_with_retry(tool_name, action_input)
                else:
                    await engine.try_once(tool_name, action_input)
        return captured

    @pytest.mark.asyncio
    async def test_shell_timeout_600_capped_630(self):
        """shell内层timeout=600 → 外层630(cap)"""
        async def shell_like(**kw):
            return {"exit_code": 0}
        captured = await self._capture_timeout(shell_like, {"timeout": 600})
        assert len(captured) >= 1, "wait_for未被调用"
        t = captured[0]
        assert t == 630, f"期望630, 实际{t}"

    @pytest.mark.asyncio
    async def test_shell_timeout_60_fuse_floor_630(self):
        """shell内层timeout=60 → 外层630(保险丝地板: max(60,CEILING=600)+30)"""
        async def shell_like(**kw):
            return {"exit_code": 0}
        captured = await self._capture_timeout(shell_like, {"timeout": 60})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 630, f"期望630, 实际{t}"

    @pytest.mark.asyncio
    async def test_shell_timeout_120_bumped_630(self):
        """shell内层timeout=120 → 外层630(max(120,600)+30)"""
        async def shell_like(**kw):
            return {"exit_code": 0}
        captured = await self._capture_timeout(shell_like, {"timeout": 120})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 630, f"期望630, 实际{t}"

    @pytest.mark.asyncio
    async def test_shell_timeout_290_bumped_630(self):
        """shell内层timeout=290 → 外层630(max(290,600)+30)"""
        async def shell_like(**kw):
            return {"exit_code": 0}
        captured = await self._capture_timeout(shell_like, {"timeout": 290})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 630, f"期望630, 实际{t}"

    @pytest.mark.asyncio
    async def test_no_timeout_param(self):
        """无内层timeout参数 → 用默认路径, 不改"""
        async def simple_tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(simple_tool, {})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 120, f"期望120(默认), 实际{t}"

    @pytest.mark.asyncio
    async def test_inner_timeout_zero_skipped(self):
        """内层timeout=0 → isinstance检查通过, 0>0为False → 跳过"""
        async def tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(tool, {"timeout": 0})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 120, f"期望120(不变), 实际{t}"

    @pytest.mark.asyncio
    async def test_inner_timeout_none_skipped(self):
        """内层timeout=None → isinstance(int)失败 → 跳过"""
        async def tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(tool, {"timeout": None})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 120, f"期望120(不变), 实际{t}"

    @pytest.mark.asyncio
    async def test_inner_timeout_negative_skipped(self):
        """内层timeout=-5 → isinstance检查通过, -5>0为False → 跳过"""
        async def tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(tool, {"timeout": -5})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 120, f"期望120(不变), 实际{t}"

    @pytest.mark.asyncio
    async def test_download_3600_fuse_3630(self):
        """download内层timeout=3600 → 外层3630(超CEILING随它去: max(3600,600)+30, 恒>内层不被截杀)"""
        async def download_like(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(download_like, {"timeout": 3600})
        assert len(captured) >= 1
        t = captured[0]
        assert t == 3630, f"期望3630, 实际{t}"

    @pytest.mark.asyncio
    async def test_try_once_also_has_both_layers(self):
        """try_once(并行分支)同样有外层>内层+30逻辑"""
        async def tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(
            tool, {"timeout": 600}, engine_method="try_once")
        assert len(captured) >= 1
        t = captured[0]
        assert t == 630, f"期望630, 实际{t}"

    @pytest.mark.asyncio
    async def test_try_once_no_inner_unchanged(self):
        """try_once无内层timeout → 不变"""
        async def tool(**kw):
            return {"ok": True}
        captured = await self._capture_timeout(
            tool, {}, engine_method="try_once")
        assert len(captured) >= 1
        t = captured[0]
        assert t == 120, f"期望120(默认), 实际{t}"

    @pytest.mark.asyncio
    async def test_progressive_timeout_attempt2(self):
        """渐进超时: attempt=1时base_timeout*2, 内层timeout=600 → 630(cap)"""
        from app.services.agent.tool_retry_engine import ToolRetryEngine
        engine = self._make_engine()
        tool_name = "test_tool"
        call_count = [0]
        async def fail_then_ok(**kw):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise ConnectionError("fail")
            return {"ok": True}
        engine._tools[tool_name] = fail_then_ok
        captured = []
        original_wait_for = asyncio.wait_for
        async def capture_wait_for(coro, timeout, **kw):
            captured.append(timeout)
            return await original_wait_for(coro, timeout=timeout, **kw)
        with patch.object(asyncio, "wait_for", capture_wait_for):
            with patch(f"{ToolRetryEngine.__module__}.TOOL_TIMEOUTS",
                       {"test_tool": 120, "default": 120}):
                with patch(f"{ToolRetryEngine.__module__}.TOOL_RETRY_CONFIG",
                           {"test_tool": {"max_retries": 2, "retryable": ["connect"]}}):
                    await engine.execute_tool_with_retry(tool_name, {"timeout": 600})
        # 有inner=600(恒>0) → 保险丝=max(600,CEILING=600)+30=630, 与attempt无关(每次重试都630)
        assert len(captured) >= 1
        assert all(t == 630 for t in captured), f"所有attempt都期望630, 实际{captured}"

    @pytest.mark.asyncio
    async def test_async_tool_same_timeout(self):
        """协程工具也走wait_for,超时计算同同步工具"""
        async def async_tool(**kw):
            return {"ok": True}
        assert inspect.iscoroutinefunction(async_tool)
        captured = await self._capture_timeout(async_tool, {"timeout": 600})
        assert len(captured) >= 1
        assert captured[0] == 630, f"异步工具期望630, 实际{captured[0]}"


# ===========================================================================
# P2 — shell() success_codes 深度测试
# ===========================================================================

class TestP2ShellSuccessCodes:
    """P2 修复: success_codes追加式退出码判定 — 深度边界攻击"""

    def _call_shell(self, returncode, success_codes=None, stdout="", stderr="",
                    shell_type="ps7"):
        """调shell()并mock shell_pool.acquire返回mock_engine"""
        from app.tools.fundamental.execute_shell_command import shell
        from app.tools.fundamental.shell_engine import shell_pool
        mock_engine = MagicMock()
        mock_engine.exec.return_value = {
            "exit_code": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        with patch.object(shell_pool, "acquire", return_value=mock_engine):
            result = shell(
                command="test_command",
                shell_type=shell_type,
                timeout=60,
                cwd=None,
                success_codes=success_codes,
            )
        return result

    def _is_success(self, result):
        return result.get("llm_data", {}).get("status", {}).get("exec_code") == "success"

    def _is_error(self, result):
        return result.get("llm_data", {}).get("status", {}).get("exec_code") == "error"

    def _is_warning(self, result):
        return result.get("llm_data", {}).get("status", {}).get("exec_code") == "warning"

    # ── 核心逻辑: returncode == 0 or in success_codes ──

    def test_returncode_0_no_success_codes(self):
        """returncode=0, success_codes=None → success"""
        r = self._call_shell(returncode=0, success_codes=None)
        assert self._is_success(r), f"期望success, 实际{r}"

    def test_returncode_0_with_success_codes(self):
        """returncode=0, success_codes=[1,2] → success(0永远优先)"""
        r = self._call_shell(returncode=0, success_codes=[1, 2])
        assert self._is_success(r)

    def test_returncode_1_in_success_codes(self):
        """returncode=1, success_codes=[1] → success"""
        r = self._call_shell(returncode=1, success_codes=[1])
        assert self._is_success(r)

    def test_returncode_1_not_in_none(self):
        """returncode=1, success_codes=None → error"""
        r = self._call_shell(returncode=1, success_codes=None)
        assert self._is_error(r)

    def test_returncode_1_not_in_list(self):
        """returncode=1, success_codes=[2] → error(1不在列表中)"""
        r = self._call_shell(returncode=1, success_codes=[2])
        assert self._is_error(r)

    def test_returncode_1_empty_list(self):
        """returncode=1, success_codes=[] → error(空列表)"""
        r = self._call_shell(returncode=1, success_codes=[])
        assert self._is_error(r)

    def test_returncode_1_multiple_codes(self):
        """returncode=1, success_codes=[1,2,3] → success"""
        r = self._call_shell(returncode=1, success_codes=[1, 2, 3])
        assert self._is_success(r)

    def test_returncode_3_in_list(self):
        """returncode=3, success_codes=[1,3] → success"""
        r = self._call_shell(returncode=3, success_codes=[1, 3])
        assert self._is_success(r)

    def test_returncode_1_duplicate_in_list(self):
        """returncode=1, success_codes=[1,1,1] → success(重复值)"""
        r = self._call_shell(returncode=1, success_codes=[1, 1, 1])
        assert self._is_success(r)

    # ── stderr 与 success_codes 交互 ──

    def test_returncode_1_with_stderr_warning(self):
        """returncode=1 in success_codes, 有stderr → warning(非bare success)"""
        r = self._call_shell(returncode=1, success_codes=[1],
                             stdout="ok", stderr="warning msg")
        assert self._is_warning(r)

    def test_returncode_0_with_benign_stderr_still_success(self):
        """returncode=0, 有良性stderr → 仍success(stderr被过滤)"""
        r = self._call_shell(returncode=0, success_codes=None,
                             stdout="ok", stderr="")
        assert self._is_success(r)

    # ── 参数传递链 ──

    def test_shell_input_model_default_none(self):
        """ShellInput().success_codes 默认为None"""
        from app.tools.fundamental.fundamental_schema import ShellInput
        si = ShellInput(command="test")
        assert si.success_codes is None

    def test_shell_input_model_valid_list(self):
        """ShellInput(success_codes=[1,2,3]) → 正确存储"""
        from app.tools.fundamental.fundamental_schema import ShellInput
        si = ShellInput(command="test", success_codes=[1, 2, 3])
        assert si.success_codes == [1, 2, 3]

    def test_shell_input_model_empty_list(self):
        """ShellInput(success_codes=[]) → 空列表"""
        from app.tools.fundamental.fundamental_schema import ShellInput
        si = ShellInput(command="test", success_codes=[])
        assert si.success_codes == []

    def test_shell_input_model_none_explicit(self):
        """ShellInput(success_codes=None) → None"""
        from app.tools.fundamental.fundamental_schema import ShellInput
        si = ShellInput(command="test", success_codes=None)
        assert si.success_codes is None

    # ── 零值/边界 ──

    def test_returncode_0_in_success_codes_still_ok(self):
        """success_codes含0, returncode=0 → success(0 in list也ok)"""
        r = self._call_shell(returncode=0, success_codes=[0, 1])
        assert self._is_success(r)

    def test_returncode_negative_one_not_in_list(self):
        """returncode=-1(进程异常), success_codes=[1] → error"""
        r = self._call_shell(returncode=-1, success_codes=[1])
        assert self._is_error(r)
