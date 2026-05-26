# -*- coding: utf-8 -*-
"""
API v1 共享校验函数 — 小沈 2026-05-25

供 validate_config._validate_credentials 和 validate_ai_service 复用，
消除 api_key 校验逻辑的重复。
"""

from typing import Optional, Tuple


def _validate_api_key(
    api_key: Optional[str], provider: str
) -> Tuple[bool, Optional[str]]:
    """
    校验 API Key 是否有效

    使用场景:
        配置验证和AI服务验证时检查api_key是否为None/空串/纯空白，
        替代各处重复的 `if not api_key or api_key.strip() == ""` 逻辑。

    使用示例/常用名转换说明:
        _validate_api_key(None, "openai")       → (False, "provider 'openai' 缺少 api_key 配置")
        _validate_api_key("", "openai")          → (False, "provider 'openai' 的 api_key 为空")
        _validate_api_key("  ", "openai")        → (False, "provider 'openai' 的 api_key 为空")
        _validate_api_key("sk-xxx", "openai")    → (True, None)

    返回数据说明:
        Tuple[bool, Optional[str]]: (是否有效, 错误消息)；有效时错误消息为None

    Args:
        api_key: 待校验的API密钥
        provider: 提供者名称，用于错误消息

    Author: 小沈 2026-05-25
    """
    if api_key is None:
        return (False, f"provider '{provider}' 缺少 api_key 配置")
    if not isinstance(api_key, str) or api_key.strip() == "":
        return (False, f"provider '{provider}' 的 api_key 为空")
    return (True, None)
