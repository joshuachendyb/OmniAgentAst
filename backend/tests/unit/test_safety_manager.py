# -*- coding: utf-8 -*-
"""safety/manager.py 测试 — 小健 2026-05-30"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.safety.manager import SafetyHook, SafetyManager, get_safety_manager


class MockHook(SafetyHook):
    """模拟Hook用于测试"""

    def __init__(self, is_safe=True, risk_score=0.0, message=""):
        self._is_safe = is_safe
        self._risk_score = risk_score
        self._message = message

    def check(self, action, params):
        return {"is_safe": self._is_safe, "risk_score": self._risk_score, "message": self._message}

    def record_operation(self, *args, **kwargs):
        return "mock-op-id"


class TestSafetyHook:
    """SafetyHook 基类测试"""

    def test_check_default(self):
        """正常：默认返回安全"""
        hook = SafetyHook()
        result = hook.check("any", {})
        assert result["is_safe"] is True
        assert result["risk_score"] == 0.0

    @pytest.mark.asyncio
    async def test_on_before_execute_default(self):
        """正常：默认返回None"""
        hook = SafetyHook()
        result = await hook.on_before_execute("any", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_on_after_execute_default(self):
        """正常：默认不报错"""
        hook = SafetyHook()
        await hook.on_after_execute("any", {}, {"ok": True})


class TestSafetyManager:
    """SafetyManager 深度测试"""

    def setup_method(self):
        self.mgr = SafetyManager()

    def test_check_no_hook(self):
        """边界：未注册hook时默认安全"""
        result = self.mgr.check("unknown", "action", {})
        assert result["is_safe"] is True

    def test_check_with_hook(self):
        """正常：注册hook后check返回hook结果"""
        hook = MockHook(is_safe=False, risk_score=0.8)
        self.mgr.register_hook("file", hook)
        result = self.mgr.check("file", "delete", {})
        assert result["is_safe"] is False
        assert result["risk_score"] == 0.8

    def test_register_hook(self):
        """正常：多分类可分别注册"""
        file_hook = MockHook()
        shell_hook = MockHook()
        self.mgr.register_hook("file", file_hook)
        self.mgr.register_hook("shell", shell_hook)
        assert self.mgr.get_hook("file") is file_hook
        assert self.mgr.get_hook("shell") is shell_hook

    def test_get_hook_not_found(self):
        """边界：获取不存在的hook返回None"""
        assert self.mgr.get_hook("nonexistent") is None

    def test_parse_command_no_parser(self):
        """边界：未设置parser时返回默认"""
        result = self.mgr.parse_command("rm -rf /")
        assert result["operation"] is None

    def test_parse_command_with_parser(self):
        """正常：设置parser后解析命令"""
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {"operation": "delete", "direction": "write"}
        self.mgr.set_command_parser(mock_parser)
        result = self.mgr.parse_command("rm -rf /")
        assert result["operation"] == "delete"

    @pytest.mark.asyncio
    async def test_on_before_execute_no_hook(self):
        """边界：未注册hook时返回None"""
        result = await self.mgr.on_before_execute("unknown", "action", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_on_before_execute_intercept(self):
        """正常：hook拦截"""
        hook = MagicMock(spec=SafetyHook)
        hook.on_before_execute = AsyncMock(return_value={"intercepted": True})
        self.mgr.register_hook("test", hook)
        result = await self.mgr.on_before_execute("test", "action", {})
        assert result["intercepted"] is True

    def test_record_operation_no_hook(self):
        """边界：无hook时返回nohook格式id"""
        op_id = self.mgr.record_operation("unknown")
        assert "nohook" in op_id

    def test_record_operation_with_hook(self):
        """正常：委托给hook"""
        hook = MockHook()
        self.mgr.register_hook("file", hook)
        op_id = self.mgr.record_operation("file")
        assert op_id == "mock-op-id"

    def test_record_operation_hook_no_method(self):
        """边界：hook未实现record_operation"""
        hook = SafetyHook()
        self.mgr.register_hook("test", hook)
        op_id = self.mgr.record_operation("test")
        assert "norecord" in op_id

    @pytest.mark.asyncio
    async def test_check_and_execute_safe(self):
        """正常：安全通过→执行→返回结果"""
        self.mgr.register_hook("test", MockHook(is_safe=True))

        def op():
            return "executed"

        result = await self.mgr.check_and_execute("test", "action", {}, op)
        assert result["is_safe"] is True
        assert result["execution_result"] == "executed"

    @pytest.mark.asyncio
    async def test_check_and_execute_unsafe(self):
        """安全拦截：check不通过不执行"""
        self.mgr.register_hook("test", MockHook(is_safe=False, message="blocked"))
        result = await self.mgr.check_and_execute("test", "danger", {}, lambda: "never")
        assert result["is_safe"] is False
        assert result["execution_result"] is None
        assert "blocked" in result["error"]

    def test_execute_with_safety_no_hook(self):
        """边界：无hook时直接执行"""
        result = self.mgr.execute_with_safety("unknown", "op1", lambda: True)
        assert result is True

    def test_execute_with_safety_hook_no_method(self):
        """边界：hook无execute_with_safety时直接执行"""
        hook = SafetyHook()
        self.mgr.register_hook("test", hook)
        result = self.mgr.execute_with_safety("test", "op1", lambda: True)
        assert result is True

    def test_execute_with_safety_via_hook(self):
        """正常：委托给hook.execute_with_safety"""
        class FullHook:
            def execute_with_safety(self, op_id, func, *a, **kw):
                return func(*a, **kw)
        hook = FullHook()
        self.mgr.register_hook("file", hook)
        result = self.mgr.execute_with_safety("file", "op1", lambda: True)
        assert result is True

    def test_execute_with_safety_operation_fails(self):
        """异常：operation抛出异常返回False"""
        result = self.mgr.execute_with_safety("unknown", "op1", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        assert result is False


class TestGetSafetyManager:
    """get_safety_manager 单例测试"""

    def test_singleton(self):
        """正常：多次调用返回相同实例"""
        m1 = get_safety_manager()
        m2 = get_safety_manager()
        assert m1 is m2

    def test_has_command_parser(self):
        """正常：自动加载CommandParser"""
        mgr = get_safety_manager()
        assert mgr._command_parser is not None
