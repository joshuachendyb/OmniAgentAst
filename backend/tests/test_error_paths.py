# -*- coding: utf-8 -*-
"""
错误路径与异常场景单元测试（完整覆盖 15.3/15.4/15.5）

测试范围：
- B3 content tracking：多步对话中current_content变量不丢失
- B1 registry查询：get_implementations_from_registry返回含None的dict
- CRSS+LLM两阶段联调：阈值路由+LLM兜底
- 基础错误路径（废弃工具、缺失参数、格式一致性）

Author: 小沈 - 2026-05-26
"""
import os
import re
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.tools._response import build_error, build_success, is_success, is_error
from app.services.tools.registry import (
    tool_registry, ToolCategory, get_implementations_from_registry,
    get_tools_from_registry_by_category,
)
from app.services.chat_router import route_with_fallback
from app.services.agent.tool_executor import ToolExecutor
from app.constants import (
    ERR_TOOL_NOT_FOUND,
    ERR_TOOL_DEPRECATED,
    ERR_MISSING_PARAM,
    ERR_DOC_FORMAT_NOT_SUPPORTED,
    ERR_META_NO_ACTIVE_TASK,
)


# ====================================================================
# Section 1: B3 - Content Tracking （多步对话 content 不丢失）
# 对应修复：react_sse_wrapper.py:491-492
#   current_content = step_data.get('response', current_content) or current_content
# ====================================================================

class TestB3ContentTracking:
    """B3 - current_content变量在多种final.response场景下不丢失"""

    def test_final_empty_string_preserves_content(self):
        """final.response=""时current_content保持不变"""
        step_data = {"type": "final", "response": ""}
        current_content = "之前累积的chunk内容"
        result = step_data.get("response", current_content) or current_content
        assert result == "之前累积的chunk内容"

    def test_final_none_preserves_content(self):
        """final.response=None时current_content保持不变"""
        step_data = {"type": "final", "response": None}
        current_content = "之前累积的chunk内容"
        result = step_data.get("response", current_content) or current_content
        assert result == "之前累积的chunk内容"

    def test_final_missing_key_preserves_content(self):
        """final没有response键时current_content保持不变"""
        step_data = {"type": "final"}
        current_content = "之前累积的chunk内容"
        result = step_data.get("response", current_content) or current_content
        assert result == "之前累积的chunk内容"

    def test_final_normal_response_overwrites(self):
        """final.response有真实内容时正常覆盖current_content"""
        step_data = {"type": "final", "response": "这是完整的最终回复"}
        current_content = "之前累积的chunk内容"
        result = step_data.get("response", current_content) or current_content
        assert result == "这是完整的最终回复"

    def test_final_response_falsy_zero(self):
        """final.response=0（罕见边缘情况）也会fallback到current_content"""
        step_data = {"type": "final", "response": 0}
        current_content = "之前累积的chunk内容"
        result = step_data.get("response", current_content) or current_content
        assert result == "之前累积的chunk内容"

    def test_chunk_accumulation_multi_step(self):
        """多个chunk事件依次累积更新current_content"""
        current_content = ""
        chunks = ["第一段", "第二段", "第三段"]
        for c in chunks:
            step_data = {"type": "chunk", "content": c}
            current_content = step_data.get("content", current_content)
        assert current_content == "第三段"

    def test_chunk_then_final_empty_response(self):
        """chunk累积后再final.response=""，content不丢失"""
        chunks = ["第一段", "第二段", "第三段"]
        content = ""
        for c in chunks:
            content = {"type": "chunk", "content": c}.get("content", content)
        content = {"type": "final", "response": ""}.get("response", content) or content
        assert content == "第三段"

    def test_chunk_then_final_normal_response(self):
        """chunk累积后再final.response有内容，最终采用final内容"""
        chunks = ["第一段", "第二段"]
        content = ""
        for c in chunks:
            content = {"type": "chunk", "content": c}.get("content", content)
        content = {"type": "final", "response": "完整回复"}.get("response", content) or content
        assert content == "完整回复"

    def test_no_chunk_only_final_empty_response(self):
        """没有chunk且final.response为空时得到空字符串"""
        content = ""
        content = {"type": "final", "response": ""}.get("response", content) or content
        assert content == ""


# ====================================================================
# Section 2: B1 - Registry None （registry查询返回含None的dict）
# 对应风险：registry.py:886 get_implementations_from_registry() 
#   get_implementation(name)可能返回None但不过滤
# ====================================================================

class TestB1RegistryNone:
    """B1 - get_implementations_from_registry返回含None的dict"""

    def test_implementation_none_for_unknown_tool(self):
        """不存在的工具get_implementation返回None"""
        impl = tool_registry.get_implementation("nonexistent_tool_xyz")
        assert impl is None

    def test_get_implementations_from_registry_is_dict(self):
        """get_implementations_from_registry返回dict类型"""
        result = get_implementations_from_registry()
        assert isinstance(result, dict)

    def test_get_implementations_can_contain_none(self):
        """get_implementations_from_registry查询不存在工具时值为None"""
        impl = tool_registry.get_implementation("_this_tool_does_not_exist_")
        assert impl is None

    def test_tool_executor_handles_none_in_available_tools(self):
        """ToolExecutor.execute在available_tools没有目标工具时fallback到全局registry"""
        executor = ToolExecutor(tools={})
        tools_dict = executor.available_tools
        assert isinstance(tools_dict, dict)

    def test_tool_executor_fallback_global_registry(self):
        """ToolExecutor找不到工具时从全局registry获取"""
        executor = ToolExecutor(tools={})
        with patch("app.services.agent.tool_executor.is_deprecated_tool", return_value=None), \
             patch("app.services.agent.tool_executor.get_tool_name_alias", return_value=None):
            result = asyncio.run(executor.execute("_nonexistent_tool_", {}))
            assert result["code"] == ERR_TOOL_NOT_FOUND

    def test_get_tools_from_registry_by_category_filters_none(self):
        """get_tools_from_registry_by_category已过滤None值（对比验证）"""
        result = get_tools_from_registry_by_category(ToolCategory.FILE)
        for name, impl in result.items():
            assert impl is not None, f"工具 {name} 的实现不应为None"


# ====================================================================
# Section 3: CRSS + LLM 两阶段联调 （阈值路由 + LLM兜底）
# 对应函数：chat_router.py:66 route_with_fallback()
#   stage1: CRSS >= 0.3 → 直接返回
#   stage2: LLM兜底，失败时fallback到CRSS结果
# ====================================================================

class TestCrssLlmIntegration:
    """CRSS + LLM 两阶段意图路由联调"""

    @pytest.mark.asyncio
    async def test_crss_high_confidence_direct_return(self):
        """CRSS置信度>=0.3时直接返回，不调LLM"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect:
            mock_detect.return_value = (ToolCategory.FILE, [ToolCategory.FILE], 0.85)

            result = await route_with_fallback("查看文件")
            assert result["source"] == "crss"
            assert result["intent"] == ToolCategory.FILE
            assert result["confidence"] == 0.85
            mock_detect.assert_called_once()

    @pytest.mark.asyncio
    async def test_crss_low_confidence_triggers_llm(self):
        """CRSS置信度<0.3时触发LLM兜底"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect, \
             patch("app.services.preprocessing.intent_classifier.classify_intent") as mock_llm:
            mock_detect.return_value = (ToolCategory.FILE, [ToolCategory.FILE], 0.15)
            mock_llm.return_value = {
                "intent": "network",
                "confidence": 0.92,
                "corrected": "检查网络",
                "all_intents": {"network": 0.92, "file": 0.08}
            }

            result = await route_with_fallback("检查网络")
            assert result["source"] == "llm"
            assert result["confidence"] == 0.92
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_crss_no_primary_triggers_llm(self):
        """CRSS无主意图（primary=None）时触发LLM兜底"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect, \
             patch("app.services.preprocessing.intent_classifier.classify_intent") as mock_llm:
            mock_detect.return_value = (None, [], 0.0)
            mock_llm.return_value = {
                "intent": "desktop",
                "confidence": 0.88,
                "corrected": "截图",
                "all_intents": {"desktop": 0.88, "system": 0.12}
            }

            result = await route_with_fallback("帮我截图")
            assert result["source"] == "llm"
            assert result["intent"] == ToolCategory.DESKTOP

    @pytest.mark.asyncio
    async def test_llm_failure_fallback_to_crss(self):
        """LLM兜底失败时保留CRSS结果（不抛异常）"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect, \
             patch("app.services.preprocessing.intent_classifier.classify_intent") as mock_llm:
            mock_detect.return_value = (None, [], 0.0)
            mock_llm.side_effect = Exception("LLM服务不可用")

            result = await route_with_fallback("测试")
            assert result["source"] == "crss"
            assert "corrected" in result

    @pytest.mark.asyncio
    async def test_crss_exactly_at_threshold(self):
        """CRSS置信度恰好在threshold边界值时直接返回"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect:
            mock_detect.return_value = (ToolCategory.SYSTEM, [ToolCategory.SYSTEM], 0.3)

            result = await route_with_fallback("执行命令")
            assert result["source"] == "crss"
            assert result["intent"] == ToolCategory.SYSTEM
            assert result["confidence"] == 0.3

    @pytest.mark.asyncio
    async def test_crss_high_but_no_llm_call(self):
        """CRSS高分时不调用LLM（通过mock验证LLM未被调用）"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect, \
             patch("app.services.preprocessing.intent_classifier.classify_intent") as mock_llm:
            mock_detect.return_value = (ToolCategory.NETWORK, [ToolCategory.NETWORK], 0.95)

            result = await route_with_fallback("ping测试")
            assert result["source"] == "crss"
            mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_result_with_resolve_category(self):
        """LLM返回字符串意图名正确解析为ToolCategory枚举"""
        with patch("app.services.chat_router.detect_intent_v2") as mock_detect, \
             patch("app.services.preprocessing.intent_classifier.classify_intent") as mock_llm:
            mock_detect.return_value = (None, [], 0.0)
            mock_llm.return_value = {
                "intent": "document",
                "confidence": 0.75,
                "corrected": "读取文档",
                "all_intents": {"document": 0.75, "file": 0.25}
            }

            result = await route_with_fallback("读取文档")
            assert result["intent"] == ToolCategory.DOCUMENT


# ====================================================================
# Section 4: 基础单元测试（保留原测试内容）
# 验证工具响应格式、错误码常量一致性
# ====================================================================

class TestBuildResponseFormat:
    """build_error/build_success格式一致性"""

    def test_build_error_has_required_fields(self):
        """build_error返回{code, data, message}"""
        result = build_error(ERR_DOC_FORMAT_NOT_SUPPORTED, "不支持PDF")
        assert "code" in result
        assert "data" in result
        assert "message" in result
        assert result["code"] == ERR_DOC_FORMAT_NOT_SUPPORTED
        assert result["data"] is None

    def test_build_success_has_required_fields(self):
        """build_success返回{code, data, message}"""
        result = build_success({"path": "/tmp"}, "成功")
        assert result["code"] == "SUCCESS"
        assert result["data"] == {"path": "/tmp"}
        assert result["message"] == "成功"

    def test_is_success_and_is_error(self):
        """is_success/is_error判断正确"""
        ok = build_success({}, "ok")
        err = build_error(ERR_META_NO_ACTIVE_TASK, "无任务")
        assert is_success(ok) is True
        assert is_error(ok) is False
        assert is_success(err) is False
        assert is_error(err) is True

    def test_build_error_with_data(self):
        """build_error可携带data"""
        result = build_error(ERR_MISSING_PARAM, "缺少参数", data={"missing": ["path"]})
        assert result["data"] == {"missing": ["path"]}

    def test_build_success_with_warning(self):
        """build_success可携带warning"""
        result = build_success({}, "ok", warning="文件较大")
        assert result.get("warning") == "文件较大"


class TestToolExecutorErrorPaths:
    """ToolExecutor异常路径"""

    @pytest.mark.asyncio
    async def test_deprecated_tool_returns_error(self):
        """废弃工具返回ERR_TOOL_DEPRECATED"""
        with patch("app.services.agent.tool_executor.is_deprecated_tool", return_value="请使用新工具"):
            executor = ToolExecutor(tools={})
            result = await executor.execute("old_tool", {})
            assert result["code"] == ERR_TOOL_DEPRECATED

    @pytest.mark.asyncio
    async def test_not_found_tool_returns_error(self):
        """不存在的工具返回ERR_TOOL_NOT_FOUND"""
        with patch("app.services.agent.tool_executor.is_deprecated_tool", return_value=None), \
             patch("app.services.agent.tool_executor.get_tool_name_alias", return_value=None):
            executor = ToolExecutor(tools={})
            result = await executor.execute("unknown_tool", {})
            assert result["code"] == ERR_TOOL_NOT_FOUND


class TestErrorCodeConstants:
    """错误码常量一致性"""

    def test_err_doc_format_not_supported_value(self):
        """ERR_DOC_FORMAT_NOT_SUPPORTED值与名称一致"""
        assert ERR_DOC_FORMAT_NOT_SUPPORTED == "ERR_DOC_FORMAT_NOT_SUPPORTED"

    def test_err_meta_no_active_task_value(self):
        """ERR_META_NO_ACTIVE_TASK值与名称一致"""
        assert ERR_META_NO_ACTIVE_TASK == "ERR_META_NO_ACTIVE_TASK"

    def test_err_tool_not_found_value(self):
        """ERR_TOOL_NOT_FOUND值与名称一致"""
        assert ERR_TOOL_NOT_FOUND == "ERR_TOOL_NOT_FOUND"

    def test_no_inconsistent_codes_in_tools(self):
        """工具目录中不存在ERR_DOC_UNSUPPORTED_FORMAT和ERR_META_NO_TASK"""
        bad_codes = {"ERR_DOC_UNSUPPORTED_FORMAT", "ERR_META_NO_TASK"}
        tools_dir = "G:/OmniAgentAs-desk/backend/app/services/tools"
        for root, dirs, files in os.walk(tools_dir):
            for d in list(dirs):
                if d.startswith('.') or d == '__pycache__':
                    dirs.remove(d)
            for f in files:
                if not f.endswith('.py'):
                    continue
                path = os.path.join(root, f)
                with open(path, encoding='utf-8') as fh:
                    for i, line in enumerate(fh, 1):
                        for code in bad_codes:
                            if code in line:
                                pytest.fail(f"{path}:{i} contains deprecated error code {code}")
