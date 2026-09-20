# -*- coding: utf-8 -*-
"""
model_service — 模型编排器（位于 model 域，与 config_service/config_helpers/resolver 同域聚合）

编辑历史:
  2026-09-20 - 小沈 - 新建：5.2 模型管理契约
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from app.logger import logger
from app.services.model.config_helpers import (
    get_config_path,
    mask_secret_value,
    merge_region_patch,
    read_yaml_config,
    _config_mtime,
)

RESERVED_AI_KEYS = {"provider", "model", "model_ref"}


def _raw_ai() -> Dict[str, Any]:
    raw = read_yaml_config(Path(get_config_path())) or {}
    ai = raw.get("ai", {})
    return ai if isinstance(ai, dict) else {}


def _provider_names(ai: Dict[str, Any]) -> List[str]:
    return [k for k, v in ai.items() if isinstance(v, dict) and k not in RESERVED_AI_KEYS]


def get_current_ref(ai: Dict[str, Any], providers: List[str]) -> Dict[str, str]:
    ref = ai.get("model_ref")
    if isinstance(ref, dict) and ref.get("provider") and ref.get("model"):
        return {"provider": str(ref["provider"]), "model": str(ref["model"])}
    provider = str(ai.get("provider") or (providers[0] if providers else ""))
    models = _models_of(ai, provider)
    model = str(ai.get("model") or (models[0]["name"] if models else ""))
    return {"provider": provider, "model": model}


def _models_of(ai: Dict[str, Any], provider: str) -> List[Dict[str, Any]]:
    p = ai.get(provider, {})
    raw_models = p.get("models", []) if isinstance(p, dict) else []
    params_block = (p.get("model_params", {}) or {}) if isinstance(p, dict) else {}
    meta_block = (p.get("model_meta", {}) or {}) if isinstance(p, dict) else {}
    out: List[Dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, str):
            m = str(m.get("name", "")) if isinstance(m, dict) else str(m)
        if not m or m in [o["name"] for o in out]:
            continue
        meta = (meta_block.get(m) or {}) if isinstance(meta_block, dict) else {}
        params = (params_block.get(m) or {}) if isinstance(params_block, dict) else {}
        out.append({
            "name": m,
            "label": str(meta.get("label") or m),
            "default_params": params,
            "range": meta.get("range", {}) or {},
            "capabilities": meta.get("capabilities", []) or [],
        })
    return out


def get_models() -> Dict[str, Any]:
    ai = _raw_ai()
    providers = []
    for name in _provider_names(ai):
        p = ai[name]
        is_env = bool(os.environ.get(f"{name.upper()}_API_KEY"))
        providers.append({"name": name, "label": str(p.get("label", name)),
                          "api_base": str(p.get("api_base", "")),
                          "api_key": mask_secret_value(p.get("api_key", "")),
                          "env": is_env,
                          "timeout": p.get("timeout", 60),
                          "models": _models_of(ai, name)})
    return {"providers": providers,
            "current_model_ref": get_current_ref(ai, [p["name"] for p in providers])}


def get_providers() -> List[Dict[str, Any]]:
    return get_models()["providers"]


def _sync_current(region: Dict[str, Any], provider: str, model: str) -> None:
    region["ai.model_ref"] = {"provider": provider, "model": model}
    if provider and model:
        region["ai.provider"] = provider
        region["ai.model"] = model


def add_model(provider: str, model: str, label: str = "",
              default_params: Optional[Dict[str, Any]] = None,
              range_: Optional[Dict[str, Any]] = None,
              capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    if any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError("同名模型已存在")
    models = list(ai[provider].get("models", []) or [])
    if not all(isinstance(m, str) for m in models):
        models = [_m["name"] for _m in _models_of(ai, provider)]
    models.append(model)
    region: Dict[str, Any] = {
        f"ai.{provider}.models": models,
        f"ai.{provider}.model_params.{model}": default_params or {},
        f"ai.{provider}.model_meta.{model}": {
            "label": label or model,
            "range": range_ or {},
            "capabilities": capabilities or [],
        },
    }
    merge_region_patch(region, scope="model")
    return {**get_models(), "ok": True, "mtime": _config_mtime()}


def update_model(provider: str, model: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if not any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError(f"模型不存在: {provider}/{model}")
    region: Dict[str, Any] = {}
    for k in ("label", "range", "capabilities"):
        if fields.get(k) is not None:
            region[f"ai.{provider}.model_meta.{model}.{k}"] = fields[k]
    dp = fields.get("default_params")
    if isinstance(dp, dict) and dp:
        for pk, pv in dp.items():
            region[f"ai.{provider}.model_params.{model}.{pk}"] = pv
    if not region:
        raise ValueError("无有效配置项")
    merge_region_patch(region, scope="model")
    return {"ok": True, "model": model, "mtime": _config_mtime()}


def delete_model(provider: str, model: str) -> Dict[str, Any]:
    ai = _raw_ai()
    models = [m for m in (ai.get(provider, {}).get("models", []) or [])
              if (m if isinstance(m, str) else m.get("name")) != model]
    region: Dict[str, Any] = {
        f"ai.{provider}.models": models,
        f"ai.{provider}.model_params.{model}": None,
        f"ai.{provider}.model_meta.{model}": None,
    }
    switched_to = None
    cur = get_current_ref(ai, _provider_names(ai))
    if cur["provider"] == provider and cur["model"] == model:
        names = [m for m in models if isinstance(m, str)] or \
                [(_m["name"]) for _m in _models_of(ai, provider) if _m["name"] in models]
        if names:
            _sync_current(region, provider, names[0])
            switched_to = names[0]
        else:
            rest = [n for n in _provider_names(ai) if n != provider]
            target_p, target_m = "", ""
            for n in rest:
                ms = _models_of(ai, n)
                if ms:
                    target_p, target_m = n, ms[0]["name"]
                    break
            _sync_current(region, target_p, target_m)
            switched_to = target_m or None
    merge_region_patch(region, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}


def add_provider(name: str, label: str = "", api_base: str = "",
                 api_key: str = "", model: str = "", timeout: int = 60) -> Dict[str, Any]:
    ai = _raw_ai()
    if name in _provider_names(ai):
        raise ValueError("同名 Provider 已存在")
    merge_region_patch({f"ai.{name}": {
        "name": name, "label": label or name, "api_base": api_base, "api_key": api_key,
        "timeout": timeout, "models": [model] if model else []}}, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def update_provider_config(name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {name}")
    region = {}
    key_map = {"api_key": "api_key", "base_url": "api_base", "api_base": "api_base",
               "timeout": "timeout", "retry_times": "max_retries", "max_retries": "max_retries"}
    for k, v in fields.items():
        if k in key_map and v is not None:
            region[f"ai.{name}.{key_map[k]}"] = v
    if fields.get("clear") is True:
        region[f"ai.{name}.api_key"] = ""
    if not region:
        raise ValueError("无有效配置项")
    merge_region_patch(region, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def delete_provider(name: str) -> Dict[str, Any]:
    ai = _raw_ai()
    names = _provider_names(ai)
    if name not in names:
        raise ValueError(f"Provider 不存在: {name}")
    if len(names) <= 1:
        raise ValueError("禁止删除最后一个 Provider（需至少保留一个可用模型）")
    region: Dict[str, Any] = {f"ai.{name}": None}
    switched_to = None
    cur = get_current_ref(ai, names)
    if cur["provider"] == name:
        rest = [n for n in names if n != name]
        target_p, target_m = "", ""
        if rest:
            ms = _models_of(ai, rest[0])
            target_p, target_m = rest[0], (ms[0]["name"] if ms else "")
        _sync_current(region, target_p, target_m)
        switched_to = target_p or None
    merge_region_patch(region, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}
