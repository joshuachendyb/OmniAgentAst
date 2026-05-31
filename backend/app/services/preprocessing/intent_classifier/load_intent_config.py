# -*- coding: utf-8 -*-
"""
load_intent_config — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第36-53行
"""

from app.constants import DEFAULT_LLM_TIMEOUT

_DEFAULT_INTENT_MODEL = "gemma3:4b"
_DEFAULT_OLLAMA_API_BASE = "https://ollama.com/v1"


def load_intent_config() -> dict:
    """拷贝自 intent_classifier.py 第40-53行"""
    from app.config import get_config
    oc_config = get_config().get('ai.ollamacloud', {})
    oc_models = oc_config.get("models", [])
    fallback_model = oc_models[0] if oc_models else _DEFAULT_INTENT_MODEL
    return {
        "api_base": oc_config.get("api_base", _DEFAULT_OLLAMA_API_BASE),
        "api_key": oc_config.get("api_key", ""),
        "model": oc_config.get("intent_model", fallback_model),
        "timeout": oc_config.get("timeout", DEFAULT_LLM_TIMEOUT),
    }
