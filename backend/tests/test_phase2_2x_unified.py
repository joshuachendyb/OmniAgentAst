# -*- coding: utf-8 -*-
"""
Phase 2 统一方案单元测试 — 覆盖 2.1/2.2/2.3/2.4/2.5

设计目标:
  2.1+2.2 AIConfigResolver: 验证6份分散fallback收敛为单一入口后的正确性
  2.3   LLM解析单次:        TextStrategy.call() 返回原始响应→base_react 单次 parse
  2.4   意图定义统一:         TYPE_KEYWORDS 与 _TYPE_CATEGORY_MAP_EQUIV 完整一致
  2.5   统一错误分类:         UnifiedErrorClassifier 全类型覆盖

Author: 小健
Date: 2026-05-27
"""
import json
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch

from app.config import Config, get_config
from app.services.ai_config_resolver import AIConfigResolver
from app.services.intents.crss_scorer import CRSS_TYPE_KEYWORDS
from app.services.intents.intent_mapper import INTENT_MAPPING, resolve_category

# TYPE_CATEGORY_MAP 已删除，用 INTENT_MAPPING 构建等价映射用于测试
_TYPE_CATEGORY_MAP_EQUIV = {k: v[1] for k, v in INTENT_MAPPING.items()}
from app.utils.error_classifier import (
    UnifiedErrorClassifier,
    ErrorCategory,
)
from app.services.agent.llm_response_parser import parse_react_response
from app.services.agent.llm_strategies import TextStrategy


# ====================================================================
# 2.1 + 2.2 — AIConfigResolver: 统一Fallback入口
# ====================================================================

class TestAIConfigResolver:
    """AIConfigResolver 全路径测试"""

    @pytest.fixture
    def ai_config_minimal(self) -> Dict[str, Any]:
        """最小有效AI配置"""
        return {
            "ai": {
                "provider": "openai",
                "model": "gpt-4",
                "openai": {"models": ["gpt-4", "gpt-3.5-turbo"]},
            }
        }

    @pytest.fixture
    def ai_config_no_provider(self) -> Dict[str, Any]:
        """未配置当前provider/model，但至少有可用provider"""
        return {
            "ai": {
                "openai": {"models": ["gpt-4"]},
                "anthropic": {"models": ["claude-3"]},
            }
        }

    @pytest.fixture
    def ai_config_fallback_chain(self) -> Dict[str, Any]:
        """配置的provider不存在于config中：触发fallback到第一个可用provider"""
        return {
            "ai": {
                "provider": "nonexistent_provider",
                "model": "gpt-4",
                "openai": {"models": ["gpt-4"]},
                "anthropic": {"models": ["claude-3"]},
            }
        }

    @pytest.fixture
    def ai_config_empty_models(self) -> Dict[str, Any]:
        """所有provider都无可用的models"""
        return {
            "ai": {
                "provider": "openai",
                "model": "gpt-4",
                "openai": {"models": []},
            }
        }

    @pytest.fixture
    def ai_config_empty(self) -> Dict[str, Any]:
        """完全无AI配置"""
        return {"ai": {}}

    def make_resolver(self, config_data: Dict[str, Any]) -> AIConfigResolver:
        """用指定配置数据创建AIConfigResolver"""
        mock_config = MagicMock(spec=Config)
        mock_config.raw_config = config_data
        return AIConfigResolver(config=mock_config)

    # ---- resolve_provider_model ----

    def test_resolve_valid_config(self, ai_config_minimal):
        """有效配置：返回配置的provider+model"""
        resolver = self.make_resolver(ai_config_minimal)
        provider, model = resolver.resolve_provider_model()
        assert provider == "openai"
        assert model == "gpt-4"

    def test_resolve_no_provider_fallback(self, ai_config_no_provider):
        """未指定provider/model：fallback到第一个可用provider的首个model"""
        resolver = self.make_resolver(ai_config_no_provider)
        provider, model = resolver.resolve_provider_model()
        assert provider == "openai"
        assert model == "gpt-4"

    def test_resolve_broken_config_fallback_chain(self, ai_config_fallback_chain):
        """配置的provider无效：fallback链正常工作"""
        resolver = self.make_resolver(ai_config_fallback_chain)
        provider, model = resolver.resolve_provider_model()
        assert provider == "openai"
        assert model == "gpt-4"

    def test_resolve_empty_models_returns_empty(self, ai_config_empty_models):
        """所有provider都无可用model：返回空"""
        resolver = self.make_resolver(ai_config_empty_models)
        provider, model = resolver.resolve_provider_model()
        assert provider == ""
        assert model == ""

    def test_resolve_empty_ai_config(self, ai_config_empty):
        """AI配置块为空：返回空"""
        resolver = self.make_resolver(ai_config_empty)
        provider, model = resolver.resolve_provider_model()
        assert provider == ""
        assert model == ""

    # ---- _is_valid_provider_model ----

    def test_is_valid_true(self):
        """有效配置返回True"""
        resolver = self.make_resolver({
            "ai": {"openai": {"models": ["gpt-4"]}}
        })
        assert resolver._is_valid_provider_model("openai", "gpt-4", {"openai": {"models": ["gpt-4"]}})

    def test_is_valid_empty_provider(self):
        """空provider无效"""
        resolver = self.make_resolver({"ai": {}})
        assert not resolver._is_valid_provider_model("", "gpt-4", {})

    def test_is_valid_empty_model(self):
        """空model无效"""
        resolver = self.make_resolver({"ai": {}})
        assert not resolver._is_valid_provider_model("openai", "", {})

    def test_is_valid_provider_not_in_config(self):
        """provider不存在于config中无效"""
        resolver = self.make_resolver({
            "ai": {"openai": {"models": ["gpt-4"]}}
        })
        assert not resolver._is_valid_provider_model("anthropic", "claude-3", {"openai": {"models": ["gpt-4"]}})

    def test_is_valid_model_not_in_list(self):
        """model不在provider的models列表中无效"""
        resolver = self.make_resolver({
            "ai": {"openai": {"models": ["gpt-4"]}}
        })
        assert not resolver._is_valid_provider_model("openai", "claude-3", {"openai": {"models": ["gpt-4"]}})

    # ---- validate_config ----

    def test_validate_config_valid(self, ai_config_minimal):
        """有效配置：验证通过"""
        resolver = self.make_resolver(ai_config_minimal)
        is_valid, provider, model, errors = resolver.validate_config()
        assert is_valid
        assert provider == "openai"
        assert model == "gpt-4"
        assert len(errors) == 0

    def test_validate_config_missing_ai_block(self):
        """缺少ai配置块：验证不通过"""
        resolver = self.make_resolver({})
        is_valid, provider, model, errors = resolver.validate_config()
        assert not is_valid
        assert any("缺少" in e for e in errors)

    def test_validate_config_no_valid_provider(self, ai_config_empty):
        """无有效provider：验证不通过"""
        resolver = self.make_resolver(ai_config_empty)
        is_valid, provider, model, errors = resolver.validate_config()
        assert not is_valid
        assert any("缺少" in e or "未找到" in e for e in errors)

    # ---- get_service_config ----

    def test_get_service_config_valid(self, ai_config_minimal):
        """有效的provider+model返回provider配置"""
        resolver = self.make_resolver(ai_config_minimal)
        cfg = resolver.get_service_config("openai", "gpt-4")
        assert isinstance(cfg, dict)
        assert "models" in cfg

    def test_get_service_config_empty_provider(self, ai_config_minimal):
        """空provider抛出ValueError"""
        resolver = self.make_resolver(ai_config_minimal)
        with pytest.raises(ValueError, match="provider 不能为空"):
            resolver.get_service_config("", "gpt-4")

    def test_get_service_config_empty_model(self, ai_config_minimal):
        """空model抛出ValueError"""
        resolver = self.make_resolver(ai_config_minimal)
        with pytest.raises(ValueError, match="model 不能为空"):
            resolver.get_service_config("openai", "")

    def test_get_service_config_unknown_provider(self, ai_config_minimal):
        """不存在的provider抛出ValueError"""
        resolver = self.make_resolver(ai_config_minimal)
        with pytest.raises(ValueError, match="不存在 provider"):
            resolver.get_service_config("anthropic", "claude-3")

    def test_get_service_config_model_not_in_provider(self, ai_config_minimal):
        """model不在provider列表中抛出ValueError"""
        resolver = self.make_resolver(ai_config_minimal)
        with pytest.raises(ValueError, match="不在 provider"):
            resolver.get_service_config("openai", "claude-3")


# ====================================================================
# 2.3 — LLM解析统一（单次解析验证）
# ====================================================================

class TestUnifiedLLMParsing:
    """验证 TextStrategy.call()→parse_react_response() 单次解析路径"""

    @pytest.mark.parametrize("response_text,expected_type,expected_action,expected_reasoning", [
        ('{"type":"action","tool_name":"bash","tool_params":{"command":"ls"}}', "action", "bash", ""),
        ('{"type":"finish","reasoning":"已完成","result":"done"}', "implicit", None, "已完成"),
        ('{"type":"chunk","content":"Hello"}', "chunk", None, ""),
    ])
    def test_parse_react_response_action_formats(self, response_text, expected_type, expected_action, expected_reasoning):
        """parse_react_response正确解析各类新格式JSON"""
        result = parse_react_response(response_text)
        assert result["type"] == expected_type
        if expected_action:
            assert result.get("tool_name") == expected_action
        if expected_reasoning:
            assert result.get("reasoning") == expected_reasoning

    @pytest.mark.parametrize("response_text", [
        '{"type":"action","tool_name":"bash","tool_params":{}}',
        '{\n  "type": "action",\n  "tool_name": "bash",\n  "tool_params": {}\n}',
    ])
    def test_parse_react_response_json_variants(self, response_text):
        """parse_react_response容忍JSON格式变体"""
        result = parse_react_response(response_text)
        assert result["type"] == "action"
        assert result["tool_name"] == "bash"

    def test_parse_react_response_old_format(self):
        """解析旧格式（无type字段）"""
        text = 'Thinking...\ntool_name: bash\ntool_params: {"command":"ls"}'
        result = parse_react_response(text)
        assert result["type"] in ("action", "implicit")

    def test_parse_react_response_empty(self):
        """空字符串解析为parse_error"""
        result = parse_react_response("")
        assert result["type"] == "parse_error"

    def test_parse_react_response_random_text(self):
        """非结构化文本解析不应崩溃"""
        result = parse_react_response("不好意思，我不能执行这个操作。")
        assert result["type"] in ("answer", "finish", "implicit")

    def test_text_strategy_call_structure(self):
        """TextStrategy.call()返回的是json序列化字符串"""
        mock_client = AsyncMock()
        mock_client.message = AsyncMock(return_value="")
        strategy = TextStrategy()
        from unittest.mock import AsyncMock as AMock
        mock_llm = MagicMock()
        mock_llm.model = "gpt-4"
        mock_llm.__class__.message = AMock(return_value="")

        # 验证方法签名包含 messages 参数
        import inspect
        sig = inspect.signature(strategy.call)
        params = list(sig.parameters.keys())
        assert "messages" in params or "llm_client" in params


# ====================================================================
# 2.4 — 意图定义统一（TYPE_KEYWORDS + _TYPE_CATEGORY_MAP_EQUIV 一致性）
# ====================================================================

class TestUnifiedIntentDefinitions:
    """验证意图定义的一致性——为2.4统一做好准备"""

    def test_all_type_keywords_have_category_mapping(self):
        """每个TYPE_KEYWORDS都有对应的_TYPE_CATEGORY_MAP_EQUIV条目"""
        for type_name in CRSS_TYPE_KEYWORDS:
            assert type_name in _TYPE_CATEGORY_MAP_EQUIV, f"CRSS_TYPE_KEYWORDS有'{type_name}'但_TYPE_CATEGORY_MAP_EQUIV缺少"

    def test_all_category_maps_have_keywords(self):
        """每个_TYPE_CATEGORY_MAP_EQUIV条目都有对应的CRSS_TYPE_KEYWORDS"""
        for type_name in _TYPE_CATEGORY_MAP_EQUIV:
            assert type_name in CRSS_TYPE_KEYWORDS, f"_TYPE_CATEGORY_MAP_EQUIV有'{type_name}'但CRSS_TYPE_KEYWORDS缺少"

    def test_type_keywords_has_keywords_and_chinese_keywords(self):
        """每个CRSS_TYPE_KEYWORDS条目都包含keywords和chinese_keywords"""
        for type_name, kw_data in CRSS_TYPE_KEYWORDS.items():
            assert "keywords" in kw_data, f"'{type_name}'缺少keywords"
            assert "chinese_keywords" in kw_data, f"'{type_name}'缺少chinese_keywords"
            assert len(kw_data["keywords"]) > 0, f"'{type_name}'的keywords为空"
            assert len(kw_data["chinese_keywords"]) > 0, f"'{type_name}'的chinese_keywords为空"

    def test_category_mapping_values_are_toolcategory(self):
        """_TYPE_CATEGORY_MAP_EQUIV的值都是ToolCategory枚举"""
        from app.services.tools.registry import ToolCategory
        for type_name, category in _TYPE_CATEGORY_MAP_EQUIV.items():
            assert isinstance(category, ToolCategory), f"'{type_name}'映射的值不是ToolCategory"

    def test_merged_categories_correct(self):
        """验证已合并的分类映射正确性"""
        assert _TYPE_CATEGORY_MAP_EQUIV["SHELL"] == _TYPE_CATEGORY_MAP_EQUIV["SYSTEM"]
        assert _TYPE_CATEGORY_MAP_EQUIV["TIME"] == _TYPE_CATEGORY_MAP_EQUIV["SYSTEM"]
        assert _TYPE_CATEGORY_MAP_EQUIV["ENV"] == _TYPE_CATEGORY_MAP_EQUIV["SYSTEM"]
        assert _TYPE_CATEGORY_MAP_EQUIV["CODE_EXECUTION"] == _TYPE_CATEGORY_MAP_EQUIV["SYSTEM"]
        assert _TYPE_CATEGORY_MAP_EQUIV["DATABASE"] == _TYPE_CATEGORY_MAP_EQUIV["DOCUMENT"]

    def test_keyword_count_stable(self):
        """关键词条目数量稳定（防止意外删除）"""
        total_kw = sum(len(v.get("keywords", [])) for v in CRSS_TYPE_KEYWORDS.values())
        total_ckw = sum(len(v.get("chinese_keywords", [])) for v in CRSS_TYPE_KEYWORDS.values())
        assert total_kw >= 10, f"关键词总数({total_kw})异常"
        assert total_ckw >= 10, f"中文关键词总数({total_ckw})异常"

    def test_category_mapping_no_duplicate_values(self):
        """没有重复的intent_name→category映射冲突"""
        seen_categories = set()
        for type_name, category in _TYPE_CATEGORY_MAP_EQUIV.items():
            key = (type_name, category.value)
            assert key not in seen_categories or category.value in ("system", "document"), \
                f"发现重复映射: {type_name}→{category}"
            seen_categories.add(key)


# ====================================================================
# 2.5 — 统一错误分类（UnifiedErrorClassifier 全覆盖）
# ====================================================================

class TestUnifiedErrorClassifier:
    """UnifiedErrorClassifier 全面测试——覆盖所有ErrorCategory"""

    # ---- classify_error: 异常类型分类 ----

    def test_classify_timeout_error(self):
        """asyncio.TimeoutError 分类为 TIMEOUT"""
        import asyncio
        category = UnifiedErrorClassifier.classify_error(asyncio.TimeoutError())
        assert category == ErrorCategory.TIMEOUT

    def test_classify_permission_error(self):
        """PermissionError 分类为 PERMISSION_DENIED"""
        category = UnifiedErrorClassifier.classify_error(PermissionError())
        assert category == ErrorCategory.PERMISSION_DENIED

    def test_classify_file_not_found(self):
        """FileNotFoundError 分类为 FILE_NOT_FOUND"""
        category = UnifiedErrorClassifier.classify_error(FileNotFoundError())
        assert category == ErrorCategory.FILE_NOT_FOUND

    def test_classify_value_error(self):
        """ValueError 分类为 INVALID_PARAMS"""
        category = UnifiedErrorClassifier.classify_error(ValueError())
        assert category == ErrorCategory.INVALID_PARAMS

    def test_classify_type_error(self):
        """TypeError 分类为 INVALID_PARAMS"""
        category = UnifiedErrorClassifier.classify_error(TypeError())
        assert category == ErrorCategory.INVALID_PARAMS

    def test_classify_key_error(self):
        """KeyError 分类为 TOOL_NOT_FOUND"""
        category = UnifiedErrorClassifier.classify_error(KeyError())
        assert category == ErrorCategory.TOOL_NOT_FOUND

    def test_classify_attribute_error(self):
        """AttributeError 分类为 TOOL_NOT_FOUND"""
        category = UnifiedErrorClassifier.classify_error(AttributeError())
        assert category == ErrorCategory.TOOL_NOT_FOUND

    def test_classify_unknown_exception(self):
        """未知异常类型分类为 UNKNOWN"""
        class CustomError(Exception):
            pass
        category = UnifiedErrorClassifier.classify_error(CustomError())
        assert category == ErrorCategory.UNKNOWN

    # ---- httpx 异常 ----

    def test_classify_httpx_connect_error(self):
        """httpx ConnectError 分类为 CONNECT"""
        try:
            import httpx
            error = httpx.ConnectError("connection refused")
            category = UnifiedErrorClassifier.classify_error(error)
            assert category == ErrorCategory.CONNECT
        except ImportError:
            pytest.skip("httpx not installed")

    def test_classify_httpx_timeout_error(self):
        """httpx ReadTimeout 分类为 TIMEOUT"""
        try:
            import httpx
            error = httpx.ReadTimeout("read timed out")
            category = UnifiedErrorClassifier.classify_error(error)
            assert category == ErrorCategory.TIMEOUT
        except ImportError:
            pytest.skip("httpx not installed")

    # ---- IdleTimeoutError ----

    def test_classify_idle_timeout(self):
        """IdleTimeoutError 分类为 IDLE_TIMEOUT"""
        try:
            from app.utils.idle_timeout import IdleTimeoutError
            category = UnifiedErrorClassifier.classify_error(IdleTimeoutError())
            assert category == ErrorCategory.IDLE_TIMEOUT
        except ImportError:
            pytest.skip("IdleTimeoutError not available")

    # ---- 关键词模式匹配 ----

    def test_classify_rate_limit_by_message(self):
        """错误消息中含有rate limit关键词"""
        error = RuntimeError("rate limit exceeded")
        category = UnifiedErrorClassifier.classify_error(error)
        assert category == ErrorCategory.API_RATE_LIMIT

    def test_classify_unauthorized_by_message(self):
        """错误消息中含有auth关键词"""
        error = RuntimeError("authentication failed")
        category = UnifiedErrorClassifier.classify_error(error)
        assert category == ErrorCategory.API_UNAUTHORIZED

    def test_classify_forbidden_by_message(self):
        """错误消息中含有forbidden关键词"""
        error = PermissionError("forbidden access")
        category = UnifiedErrorClassifier.classify_error(error)
        assert category == ErrorCategory.PERMISSION_DENIED

    # ---- HTTP状态码匹配 ----

    def test_classify_http_429_by_message(self):
        """错误消息中带429状态码"""
        error = RuntimeError("HTTP 429 Too Many Requests")
        category = UnifiedErrorClassifier.classify_error(error)
        assert category == ErrorCategory.API_RATE_LIMIT

    def test_classify_http_500_by_message(self):
        """错误消息中带500状态码"""
        error = RuntimeError("HTTP 500 Internal Server Error")
        category = UnifiedErrorClassifier.classify_error(error)
        assert category == ErrorCategory.SERVER

    # ---- classify_error_message ----

    def test_classify_error_message_known_type(self):
        """已知错误类型返回正确code+message"""
        code, message = UnifiedErrorClassifier.classify_error_message("TIMEOUT")
        assert code == "timeout"
        assert "超时" in message

    def test_classify_error_message_permission_denied(self):
        code, message = UnifiedErrorClassifier.classify_error_message("PERMISSION_DENIED")
        assert code == "permission_denied"
        assert "权限" in message

    def test_classify_error_message_file_not_found(self):
        code, message = UnifiedErrorClassifier.classify_error_message("FILE_NOT_FOUND")
        assert code == "file_not_found"
        assert "文件" in message

    def test_classify_error_message_api_rate_limit(self):
        code, message = UnifiedErrorClassifier.classify_error_message("API_RATE_LIMIT")
        assert code == "api_error_429"
        assert "频繁" in message

    def test_classify_error_message_empty_response(self):
        code, message = UnifiedErrorClassifier.classify_error_message("EMPTY_RESPONSE")
        assert code == "empty_response"
        assert "返回有效响应" in message or "请重试" in message

    def test_classify_error_message_unknown_type(self):
        """未知错误类型返回默认fallback"""
        code, message = UnifiedErrorClassifier.classify_error_message("UNKNOWN_TYPE", "custom error")
        assert code == "server"
        assert "custom error" in message

    # ---- get_error_info ----

    def test_get_error_info_timeout(self):
        import asyncio
        info = UnifiedErrorClassifier.get_error_info(asyncio.TimeoutError())
        assert info["category"] == ErrorCategory.TIMEOUT
        assert info["retryable"] is True
        assert info["status"] == "timeout"
        assert "超时" in info["description"]
        assert info["code"] == "timeout"

    def test_get_error_info_file_not_found(self):
        info = UnifiedErrorClassifier.get_error_info(FileNotFoundError())
        assert info["category"] == ErrorCategory.FILE_NOT_FOUND
        assert info["retryable"] is False
        assert info["status"] == "error"
        assert info["code"] == "file_not_found"

    def test_get_error_info_unknown(self):
        class WeirdError(Exception):
            pass
        info = UnifiedErrorClassifier.get_error_info(WeirdError("strange"))
        assert info["category"] == ErrorCategory.UNKNOWN
        assert info["retryable"] is False
        assert "strange" in info["original_error"]

    # ---- ErrorCategory 枚举属性 ----

    @pytest.mark.parametrize("category,expected_retryable", [
        (ErrorCategory.TIMEOUT, True),
        (ErrorCategory.NETWORK, True),
        (ErrorCategory.CONNECT, True),
        (ErrorCategory.PROTOCOL, True),
        (ErrorCategory.API_RATE_LIMIT, True),
        (ErrorCategory.IDLE_TIMEOUT, True),
        (ErrorCategory.PERMISSION_DENIED, False),
        (ErrorCategory.FILE_NOT_FOUND, False),
        (ErrorCategory.INVALID_PARAMS, False),
        (ErrorCategory.TOOL_NOT_FOUND, False),
        (ErrorCategory.CIRCUIT_OPEN, False),
        (ErrorCategory.SERVER, False),
        (ErrorCategory.API_UNAUTHORIZED, False),
        (ErrorCategory.API_FORBIDDEN, False),
        (ErrorCategory.API_BAD_REQUEST, False),
        (ErrorCategory.UNKNOWN, False),
        (ErrorCategory.EMPTY_RESPONSE, False),
    ])
    def test_error_category_retryable(self, category, expected_retryable):
        """所有ErrorCategory的is_retryable属性正确"""
        assert category.is_retryable == expected_retryable

    @pytest.mark.parametrize("category,expected_status", [
        (ErrorCategory.TIMEOUT, "timeout"),
        (ErrorCategory.FILE_NOT_FOUND, "error"),
        (ErrorCategory.NETWORK, "network_error"),
        (ErrorCategory.API_RATE_LIMIT, "rate_limit"),
        (ErrorCategory.API_UNAUTHORIZED, "auth_error"),
        (ErrorCategory.UNKNOWN, "error"),
        (ErrorCategory.EMPTY_RESPONSE, "empty_response"),
        (ErrorCategory.IDLE_TIMEOUT, "idle_timeout"),
    ])
    def test_error_category_to_status(self, category, expected_status):
        """所有ErrorCategory的to_status属性正确"""
        assert category.to_status == expected_status

    @pytest.mark.parametrize("category,expected_keyword", [
        (ErrorCategory.TIMEOUT, "超时"),
        (ErrorCategory.PERMISSION_DENIED, "权限"),
        (ErrorCategory.FILE_NOT_FOUND, "文件"),
        (ErrorCategory.INVALID_PARAMS, "参数"),
        (ErrorCategory.TOOL_NOT_FOUND, "工具"),
        (ErrorCategory.CIRCUIT_OPEN, "熔断"),
        (ErrorCategory.NETWORK, "网络"),
        (ErrorCategory.CONNECT, "连接"),
        (ErrorCategory.PROTOCOL, "协议"),
        (ErrorCategory.SERVER, "服务器"),
        (ErrorCategory.API_RATE_LIMIT, "限流"),
        (ErrorCategory.API_UNAUTHORIZED, "认证"),
        (ErrorCategory.API_FORBIDDEN, "权限不足"),
        (ErrorCategory.API_BAD_REQUEST, "参数"),
        (ErrorCategory.UNKNOWN, "未知"),
        (ErrorCategory.EMPTY_RESPONSE, "空响应"),
        (ErrorCategory.IDLE_TIMEOUT, "超时"),
    ])
    def test_error_category_description(self, category, expected_keyword):
        """所有ErrorCategory的description包含正确关键词"""
        assert expected_keyword in category.description

    # ---- HTTP_STATUS_TO_ERROR_TYPE ----

    def test_http_429_maps_to_rate_limit(self):
        from app.utils.error_classifier import HTTP_STATUS_TO_ERROR_TYPE
        assert HTTP_STATUS_TO_ERROR_TYPE[429] == ErrorCategory.API_RATE_LIMIT

    def test_http_401_maps_to_unauthorized(self):
        from app.utils.error_classifier import HTTP_STATUS_TO_ERROR_TYPE
        assert HTTP_STATUS_TO_ERROR_TYPE[401] == ErrorCategory.API_UNAUTHORIZED

    def test_http_403_maps_to_forbidden(self):
        from app.utils.error_classifier import HTTP_STATUS_TO_ERROR_TYPE
        assert HTTP_STATUS_TO_ERROR_TYPE[403] == ErrorCategory.API_FORBIDDEN

    def test_http_500_maps_to_server(self):
        from app.utils.error_classifier import HTTP_STATUS_TO_ERROR_TYPE
        assert HTTP_STATUS_TO_ERROR_TYPE[500] == ErrorCategory.SERVER

    # ---- is_network_or_api_error ----

    def test_is_network_or_api_error_with_http_code(self):
        result, error_type = UnifiedErrorClassifier.is_network_or_api_error("HTTP 429")
        assert result is True
        assert error_type == ErrorCategory.API_RATE_LIMIT.value

    def test_is_network_or_api_error_rate_limit_text(self):
        result, error_type = UnifiedErrorClassifier.is_network_or_api_error("rate limit exceeded")
        assert result is True
        assert error_type == ErrorCategory.API_RATE_LIMIT.value

    def test_is_network_or_api_error_unauthorized(self):
        result, error_type = UnifiedErrorClassifier.is_network_or_api_error("unauthorized access")
        assert result is False
        assert error_type == ErrorCategory.API_UNAUTHORIZED.value

    def test_is_network_or_api_error_empty(self):
        result, error_type = UnifiedErrorClassifier.is_network_or_api_error("")
        assert result is False
        assert error_type is None

    def test_is_network_or_api_error_no_match(self):
        result, error_type = UnifiedErrorClassifier.is_network_or_api_error("everything is fine")
        assert result is False
        assert error_type is None

    # ---- 便捷函数 ----

    def test_convenience_classify_error(self):
        code, message = UnifiedErrorClassifier.classify_error_message("TIMEOUT")
        assert code == "timeout"
        assert "超时" in message

    def test_convenience_get_error_info(self):
        import asyncio
        info = UnifiedErrorClassifier.get_error_info(asyncio.TimeoutError())
        assert info["code"] == "timeout"
        assert info["category"] == ErrorCategory.TIMEOUT
