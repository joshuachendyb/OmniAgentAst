# tests/test_tool_retry_fuse.py
# 小欧 2026-08-05 — 针对 BUG-2(保险丝三路取值)/BUG-2.5(compress timeout ge/le) 的定向单测
#
# 设计背景（北京老陈 2026-08-05 澄清）：
#   本保险丝是 toolretry 引擎的外部超时(asyncio.wait_for 掐整个工具调用)，不是工具自身内部超时。
#   保险丝必须恒 ≥ 工具内部超时，故有 inner 时 = max(inner, CEILING)+BUFFER。
#   4 条原则：
#     [原则1] 无 timeout 参数工具 → 渐进 base*(attempt+1) cap PROGRESSIVE_MAX
#     [原则2] LLM 显式传 timeout → inner = LLM 给的值
#     [原则3] LLM 未传但工具有 timeout → inner = schema 默认值(tool 值优先)
#     [原则4] 有 inner → 保险丝 = max(inner, CEILING)+BUFFER (inner 超 CEILING 随它去)
#
# 为隔离测试，注入 _get_schema_timeout_default 返回各工具 schema 的 timeout 默认值
# （与真实 schema 一致：compress=300/shell=60/httpget=30/download=60/fetchpage=30/ping_port=5）。
"""test"""

import pytest
from unittest.mock import patch, MagicMock
from app.services.agent.tool_retry_engine import (
    ToolRetryEngine,
    INSURANCE_CEILING,
    INSURANCE_BUFFER,
    PROGRESSIVE_MAX,
)


# 真实 schema 中 6 个"有 timeout 参数工具"的 timeout 默认值（与文档 13.4.2 一致）
SCHEMA_DEFAULT = {
    "compress": 300,
    "shell": 60,
    "httpget": 30,
    "download": 60,
    "fetchpage": 30,
    "ping_port": 5,
}


class _FuseEngine(ToolRetryEngine):
    """注入 _get_schema_timeout_default，避免依赖真实工具注册表"""

    def _get_schema_timeout_default(self, action):
        return SCHEMA_DEFAULT.get(action)


# =============================================================================
# _compute_fuse — 三路取值（BUG-2 核心）
# =============================================================================

class TestComputeFuse:
    def _engine(self):
        return _FuseEngine(tools={})

    # --- 原则4：有 inner，保险丝 = max(inner, CEILING)+BUFFER ---

    def test_llm_passed_timeout_uses_llm_value(self):
        """原则2+4：LLM 显式传 300，保险丝 = max(300,600)+30 = 630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": 300}, 60, 0) == 630

    def test_llm_passed_timeout_above_ceiling_uses_llm(self):
        """原则4：inner 超 CEILING(1800) 则随它去 → max(1800,600)+30 = 1830"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": 1800}, 60, 0) == 1830

    def test_llm_passed_timeout_at_ceiling(self):
        """inner == CEILING → 630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": 600}, 60, 0) == 630

    def test_llm_passed_timeout_below_ceiling_still_ceiling(self):
        """原则4 CEILING 托底：LLM 传 5，仍 max(5,600)+30=630（保险丝恒 ≥ 内部超时）"""
        eng = self._engine()
        assert eng._compute_fuse("ping_port", {"timeout": 5}, 60, 0) == 630

    # --- 原则3：LLM 未传 → inner = schema 默认值 → 再走原则4 max(inner,CEILING)+BUFFER（BUG-2 修复核心） ---

    def test_no_timeout_schema_default_then_max_buffer(self):
        """原则3+4：compress 未传 → inner=schema默认300 → 取max max(300,600)=600 → +30=630（修复前掉 default=60 被截杀）"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {}, 60, 0) == 630

    def test_no_timeout_ping_port_schema_default_then_max_buffer(self):
        """原则3+4：ping_port 未传 → inner=schema默认5 → 取max max(5,600)=600 → +30=630"""
        eng = self._engine()
        assert eng._compute_fuse("ping_port", {}, 60, 0) == 630

    def test_no_timeout_shell_schema_default_then_max_buffer(self):
        """原则3+4：shell 未传 → inner=schema默认60 → 取max max(60,600)=600 → +30=630"""
        eng = self._engine()
        assert eng._compute_fuse("shell", {}, 60, 0) == 630

    # --- 原则1：无 timeout 参数工具 → 渐进 ---

    def test_no_timeout_param_progressive(self):
        """原则1：listdir 无 timeout 参数 → min(60*(n+1),300) 渐进"""
        eng = self._engine()
        assert eng._compute_fuse("listdir", {}, 60, 0) == 60
        assert eng._compute_fuse("listdir", {}, 60, 1) == 120
        assert eng._compute_fuse("listdir", {}, 60, 2) == 180

    def test_no_timeout_param_progressive_capped(self):
        """原则1：渐进 cap PROGRESSIVE_MAX=300"""
        eng = self._engine()
        assert eng._compute_fuse("listdir", {}, 60, 9) == PROGRESSIVE_MAX

    def test_explicit_none_timeout_falls_to_schema(self):
        """LLM 显式传 timeout=None → 视为未传，inner=schema默认300 → max(300,600)+30=630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": None}, 60, 0) == 630

    def test_zero_timeout_falls_to_schema(self):
        """LLM 传 timeout=0 → 非法值，inner=schema默认300 → max(300,600)+30=630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": 0}, 60, 0) == 630

    def test_negative_timeout_falls_to_schema(self):
        """LLM 传 timeout=-5 → 非法值，inner=schema默认300 → max(300,600)+30=630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": -5}, 60, 0) == 630

    def test_bool_timeout_ignored(self):
        """LLM 传 timeout=True(bool) → 非 int/float，inner=schema默认300 → max(300,600)+30=630"""
        eng = self._engine()
        assert eng._compute_fuse("compress", {"timeout": True}, 60, 0) == 630


# =============================================================================
# _get_schema_timeout_default — schema 读取容错（BUG-2 兜底稳健性）
# =============================================================================

class TestGetSchemaTimeoutDefault:
    def _engine(self):
        return ToolRetryEngine(tools={})

    def test_reads_compress_schema_default(self):
        """真实 schema：CompressInput.timeout 默认 300（引擎读默认值兜底来源）"""
        from app.tools.file.file_schema import CompressInput
        assert CompressInput.model_fields["timeout"].default == 300

    def test_reads_ping_port_schema_default(self):
        """真实 schema：NetworkDiagnoseInput.timeout 默认 5（ping_port 有 timeout 参数）"""
        from app.tools.network.network_schema import NetworkDiagnoseInput
        assert NetworkDiagnoseInput.model_fields["timeout"].default == 5

    def test_missing_timeout_param_returns_none(self):
        """无 timeout 参数的工具 → 返回 None（listdir 无 timeout）"""
        eng = self._engine()
        with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
            meta = MagicMock()
            meta.input_schema = {"properties": {"path": {"type": "string"}}, "required": []}
            mock_gt.return_value = meta
            assert eng._get_schema_timeout_default("listdir") is None

    def test_missing_schema_returns_none(self):
        """metadata 无 input_schema → 返回 None（不抛异常）"""
        eng = self._engine()
        with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
            meta = MagicMock()
            meta.input_schema = None
            mock_gt.return_value = meta
            assert eng._get_schema_timeout_default("x") is None

    def test_zero_default_returns_none(self):
        """schema 默认值 ≤0 → 视为无有效默认，返回 None"""
        eng = self._engine()
        with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
            meta = MagicMock()
            meta.input_schema = {"properties": {"timeout": {"default": 0}}, "required": []}
            mock_gt.return_value = meta
            assert eng._get_schema_timeout_default("x") is None

    def test_get_tool_exception_returns_none(self):
        """tool_registry.get_tool 抛异常 → 返回 None（不向外抛）"""
        eng = self._engine()
        with patch("app.tools.registry.tool_registry.get_tool", side_effect=Exception("boom")):
            assert eng._get_schema_timeout_default("x") is None


# =============================================================================
# BUG-2.5 — CompressInput.timeout ge/le 约束（compress timeout clamp 生效）
# =============================================================================

class TestCompressTimeoutConstraint:
    def test_schema_has_ge_le(self):
        """CompressInput.timeout 含 ge=5/le=1800（BUG-2.5 修复）"""
        from app.tools.file.file_schema import CompressInput
        field = CompressInput.model_fields["timeout"]
        assert field.default == 300
        metadata = [repr(m) for m in field.metadata]
        assert any("ge=5" in m for m in metadata)
        assert any("le=1800" in m for m in metadata)

    def test_compress_input_rejects_out_of_range(self):
        """LLM 传 timeout=1 应被 pydantic 拒绝(ge=5) → clamp/校验生效"""
        from app.tools.file.file_schema import CompressInput
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CompressInput(path="/tmp/a", dest="/tmp/b.zip", timeout=1)

    def test_compress_input_accepts_min_max(self):
        """timeout=5 和 1800 均在合法范围，可正常构建"""
        from app.tools.file.file_schema import CompressInput
        assert CompressInput(path="/tmp/a", dest="/tmp/b.zip", timeout=5).timeout == 5
        assert CompressInput(path="/tmp/a", dest="/tmp/b.zip", timeout=1800).timeout == 1800

    def test_compress_input_default_timeout(self):
        """未传 timeout → 默认 300"""
        from app.tools.file.file_schema import CompressInput
        assert CompressInput(path="/tmp/a", dest="/tmp/b.zip").timeout == 300
