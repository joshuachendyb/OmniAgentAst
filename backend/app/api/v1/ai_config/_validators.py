"""ai_config 包通用校验函数 — Provider / Model 存在性检查

【小健 2026-05-31】新建：消除各 endpoint 文件中重复的 "xxx not in config.get('ai', {})" 检查
"""

from fastapi import HTTPException


def ensure_provider_exists(config: dict, provider_name: str) -> None:
    """确保 Provider 存在于配置中，否则抛 HTTPException(404)"""
    if provider_name not in config.get('ai', {}):
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_name} 不存在"
        )


def ensure_provider_not_duplicate(config: dict, provider_name: str) -> None:
    """确保 Provider 名不重复，否则抛 HTTPException(400)"""
    if provider_name in config.get('ai', {}):
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider_name} 已存在"
        )


def ensure_model_exists(config: dict, provider_name: str, model_name: str) -> None:
    """确保模型在指定 Provider 中存在，否则抛 HTTPException(404)"""
    providers = config.get('ai', {})
    if provider_name not in providers:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_name} 不存在"
        )
    models = providers[provider_name].get('models', [])
    if model_name and model_name not in models:
        raise HTTPException(
            status_code=404,
            detail=f"模型 {model_name} 在 Provider {provider_name} 中不存在"
        )


def ensure_model_not_duplicate(config: dict, provider_name: str, model_name: str) -> None:
    """确保模型名不重复，否则抛 HTTPException(400)"""
    providers = config.get('ai', {})
    if provider_name not in providers:
        return
    models = providers[provider_name].get('models', [])
    if model_name and model_name in models:
        raise HTTPException(
            status_code=400,
            detail=f"模型 {model_name} 已存在"
        )


__all__ = [
    "ensure_provider_exists",
    "ensure_provider_not_duplicate",
    "ensure_model_exists",
    "ensure_model_not_duplicate",
]
