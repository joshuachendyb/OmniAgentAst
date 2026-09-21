# -*- coding: utf-8 -*-
"""
model_service — 模型编排器（位于 model 域，与 config_service/config_helpers/resolver 同域聚合）
读：解析 config.yaml 的 models[]/model_params/model_meta/provider_config 区域（动态遍历 provider，
禁止硬编码 provider 名，与旧页铁律一致）；写：校验 → config_helpers.merge_region_patch（单次落盘）→ config.yaml。
数据模型（v4.17）：models[] 保持字符串列表（旧链不变式）；模型参数写 ai.{provider}.model_params.{model}
（运行时 parse_model_params 消费）；label/range/capabilities 写 ai.{provider}.model_meta.{model}（UI 元数据）。
current_model_ref 单源为结构化 ai.model_ref（2026-09-21 小欧 v4.20 收敛：删旧扁平 ai.provider/ai.model 双写）；空值不写空键。

编辑历史:
  2026-09-20 - 小沈 - 新建：5.2 模型管理契约（合并返回/级联/switched_to/立即生效）
  2026-09-20 - 小沈 - 核查 B1/B2/A2：掩码改调 config_helpers.mask_secret_value；合并写改调
    config_helpers.merge_region_patch（消私有跨域）；delete_model 删光当前 provider 模型时跨
    provider 回退，不写空 model_ref
  2026-09-20 - 小欧 - v4.17：models[] 回字符串列表；模型参数/元数据分置 model_params/model_meta；
    delete_provider 单次落盘 + 禁删最后一个 Provider；_sync_current 空值保护
  2026-09-21 - 小欧 - 对齐文档54 9.1.3：delete_provider switched_to 返回 provider 名称（target_p or None），撤销此前误改的模型名称版
  2026-09-21 - 小欧 - 修复 None 陷阱: .get('key','')/get('key',[])/get('key',{}) 在 key 存在但值为 None 时返回 None，
    统一修为 .get('key') or ''/[]/{}/60/3（config_service/config_helpers/model_service/resolver 共 12 处）
   2026-09-21 - 小欧 - 三堂会审第三轮 22 真实 bug 修复（模型域 M1~M14，对应 config_helpers 的
     merge_nested_patch 系列）——①add/update/delete_model 与 add/update/delete_provider 全部改走
     merge_nested_patch 嵌套树写(叶段字面名)：点号模型名 gpt-4.1 不再被拆成 model_params['gpt-4']['1']
     (M1/M2/M3 错位+孤儿)；②add_provider 校验保留键 provider/model/model_ref 与空名(M4/M5/M6)；
     ③delete_model 未知 provider 前置 ValueError，不再写入空块污染(M7/M8)；④add_model 空模型名拒绝(M9)；
     ⑤delete_provider 跳板扫第一个有可用模型的 provider(M10/M11)，deelete_model/deelete_provider
     无可用回退时抛"禁止删除最后一个可用模型"守卫(M12)；⑥add_provider 接受 models 列表与
     max_retries(M13 链路透传)；⑦env 接管双标准对齐：{NAME}_API_KEY 命中的 provider 读只读、
     AI_PROVIDER 命中时当前模型切换/删除只读(M14)；⑧update_provider_config 支持 label 更新(S7)、
     拒绝非法字段(S8)；⑨get_models 输出补 max_retries 对齐 ProviderInfo DTO
   2026-09-21 - 小欧 - 建议报告 P8: update_model 对空 default_params 提交由"跳过+无有效配置项 500"改为
      显式清空（写空块 {}），配合 config_helpers._iter_nested_ops 空 dict 叶值修复根治"清空不落盘"
# 2026-09-21 - 小欧 - 三堂会审修复：timeout/max_retries 的 `or 60/3` 改为 `is not None` 判断，防止合法值0被吞
# 2026-09-21 - 小欧 - v4.20 单源收敛: get_current_ref 去扁平键 fallback 只读 ai.model_ref（签名去 providers 参数）；
#   _sync_current 只写 ai.model_ref（删扁平双写）——与 resolver/config_helpers 统一为单一真相源
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

from app.logger import logger
from app.services.model.config_helpers import (
    get_config_path,
    mask_secret_value,
    merge_nested_patch,
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


def get_current_ref(ai: Dict[str, Any]) -> Dict[str, str]:
    """读当前模型 — 2026-09-21 小欧 v4.20 单源收敛：只读结构化 ai.model_ref（删扁平键 fallback，见[54]）"""
    ref = ai.get("model_ref")
    if isinstance(ref, dict) and ref.get("provider") and ref.get("model"):
        return {"provider": str(ref["provider"]), "model": str(ref["model"])}
    return {"provider": "", "model": ""}


def _models_of(ai: Dict[str, Any], provider: str) -> List[Dict[str, Any]]:
    p = ai.get(provider, {})
    raw_models = p.get("models") or [] if isinstance(p, dict) else []
    params_block = (p.get("model_params", {}) or {}) if isinstance(p, dict) else {}
    meta_block = (p.get("model_meta", {}) or {}) if isinstance(p, dict) else {}
    out: List[Dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, str):
            m = str(m.get("name") or "") if isinstance(m, dict) else str(m)
        if not m or m in [o["name"] for o in out]:
            continue
        meta = (meta_block.get(m) or {}) if isinstance(meta_block, dict) else {}
        params = (params_block.get(m) or {}) if isinstance(params_block, dict) else {}
        out.append({
            "name": m,
            "label": str(meta.get("label") or m),
            "default_params": params,
            "range": meta.get("range") or {},
            "capabilities": meta.get("capabilities") or [],
        })
    return out


def get_models() -> Dict[str, Any]:
    ai = _raw_ai()
    providers = []
    for name in _provider_names(ai):
        p = ai[name]
        is_env = bool(os.environ.get(f"{name.upper()}_API_KEY"))
        providers.append({"name": name, "label": str(p.get("label") or name),
                          "api_base": str(p.get("api_base") or ""),
                          "api_key": mask_secret_value(p.get("api_key") or ""),
                          "env": is_env,
                          "timeout": p.get('timeout') if p.get('timeout') is not None else 60,
                          "max_retries": p.get('max_retries') if p.get('max_retries') is not None else 3,
                          "models": _models_of(ai, name)})
    return {"providers": providers,
            "current_model_ref": get_current_ref(ai)}


def get_providers() -> List[Dict[str, Any]]:
    return get_models()["providers"]


def _raise_if_env_takeover(name: str) -> None:
    """env 接管守卫：设 {NAME}_API_KEY 的 provider 整行只读（与 settings 页 env 语义对齐，M14 双标准）。"""
    if os.environ.get(f"{name.upper()}_API_KEY"):
        raise ValueError(f"Provider '{name}' 由环境变量 {name.upper()}_API_KEY 接管，只读")


def _raise_if_current_ref_env() -> None:
    """当前模型 env 接管守卫：AI_PROVIDER 命中时切换/删除当前模型只读（settings 页同源语义）。"""
    if os.environ.get("AI_PROVIDER"):
        raise ValueError("当前模型由环境变量 AI_PROVIDER 接管，切换/删除当前模型只读")


def _sync_current(tree: Dict[str, Any], provider: str, model: str) -> None:
    """更新嵌套树（merge_nested_patch）中的当前模型 — 2026-09-21 小欧 v4.20 单源收敛：只写 ai.model_ref（删扁平双写，见[54]）。"""
    ai = tree.setdefault("ai", {})
    if provider and model:
        ai["model_ref"] = {"provider": provider, "model": model}


def add_model(provider: str, model: str, label: str = "",
              default_params: Optional[Dict[str, Any]] = None,
              range_: Optional[Dict[str, Any]] = None,
              capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    _raise_if_env_takeover(provider)
    if not model:
        raise ValueError("模型名不能为空")
    if any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError("同名模型已存在")
    models = list(ai[provider].get("models", []) or [])
    if not all(isinstance(m, str) for m in models):
        models = [_m["name"] for _m in _models_of(ai, provider)]
    models.append(model)
    tree: Dict[str, Any] = {
        "ai": {provider: {
            "models": models,
            "model_params": {model: default_params or {}},
            "model_meta": {model: {
                "label": label or model,
                "range": range_ or {},
                "capabilities": capabilities or [],
            }},
        }}
    }
    merge_nested_patch(tree, scope="model")
    return {**get_models(), "ok": True, "mtime": _config_mtime()}


def update_model(provider: str, model: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if not any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError(f"模型不存在: {provider}/{model}")
    _raise_if_env_takeover(provider)
    unknown = set(fields) - {"label", "range", "capabilities", "default_params"}
    if unknown:
        raise ValueError(f"不支持的配置项: {sorted(unknown)}")
    tree: Dict[str, Any] = {"ai": {provider: {}}}
    node = tree["ai"][provider]
    for k in ("label", "range", "capabilities"):
        if fields.get(k) is not None:
            node.setdefault("model_meta", {}).setdefault(model, {})[k] = fields[k]
    dp = fields.get("default_params")
    if isinstance(dp, dict):
        if dp:
            old_params = dict(ai[provider].get("model_params", {}).get(model, {}) or {})
            old_params.update(dp)
            node.setdefault("model_params", {})[model] = old_params
        else:
            # 2026-09-21 小欧 修 P8：空 default_params 提交 = 显式清空模型参数（原实现走
            # isinstance 且为空跳过 → node 空 → "无有效配置项" 500）。merge_nested_patch
            # 支持空 dict 叶值直接落 YAML 空块，validate 侧 parseInt 兼容。
            node.setdefault("model_params", {})[model] = {}
    if not node:
        raise ValueError("无有效配置项")
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "model": model, "mtime": _config_mtime()}


def delete_model(provider: str, model: str) -> Dict[str, Any]:
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    _raise_if_env_takeover(provider)
    models = [m for m in (ai.get(provider, {}).get("models") or [])
              if (m if isinstance(m, str) else m.get("name")) != model]
    tree: Dict[str, Any] = {
        "ai": {provider: {
            "models": models,
            "model_params": {model: None},
            "model_meta": {model: None},
        }}
    }
    switched_to = None
    cur = get_current_ref(ai)
    if cur["provider"] == provider and cur["model"] == model:
        _raise_if_current_ref_env()
        names = [m for m in models if isinstance(m, str)] or \
                [(_m["name"]) for _m in _models_of(ai, provider) if _m["name"] in models]
        if names:
            _sync_current(tree, provider, names[0])
            switched_to = names[0]
        else:
            rest = [n for n in _provider_names(ai) if n != provider]
            target_p, target_m = "", ""
            for n in rest:
                ms = _models_of(ai, n)
                if ms:
                    target_p, target_m = n, ms[0]["name"]
                    break
            if not target_p:
                raise ValueError("禁止删除最后一个可用模型（无其它 Provider 可回退）")
            _sync_current(tree, target_p, target_m)
            switched_to = target_m or None
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}


def _validate_new_provider_name(name: str, ai: Dict[str, Any]) -> None:
    """新 Provider 名校验：非空、非保留键（provider/model/model_ref，撞车会覆盖 ai 元数据损坏）、不重名。"""
    if not name:
        raise ValueError("Provider 名不能为空")
    if name in RESERVED_AI_KEYS:
        raise ValueError(f"Provider 名 '{name}' 为保留键(provider/model/model_ref)，不可用作 Provider 名")
    if name in _provider_names(ai):
        raise ValueError("同名 Provider 已存在")


def add_provider(name: str, label: str = "", api_base: str = "",
                 api_key: str = "", model: str = "", timeout: int = 60,
                 models: Optional[List[str]] = None,
                 max_retries: int = 3) -> Dict[str, Any]:
    ai = _raw_ai()
    _validate_new_provider_name(name, ai)
    ms = list(models or [])
    if model and model not in ms:
        ms.append(model)
    tree: Dict[str, Any] = {"ai": {name: {
        "name": name, "label": label or name, "api_base": api_base, "api_key": api_key,
        "timeout": timeout, "max_retries": max_retries, "models": ms}}}
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def update_provider_config(name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {name}")
    _raise_if_env_takeover(name)
    key_map = {"api_key": "api_key", "base_url": "api_base", "api_base": "api_base",
               "timeout": "timeout", "retry_times": "max_retries", "max_retries": "max_retries",
               "label": "label"}
    tree: Dict[str, Any] = {"ai": {name: {}}}
    node = tree["ai"][name]
    for k, v in fields.items():
        if k in key_map and v is not None:
            node[key_map[k]] = v
    if fields.get("clear") is True:
        node["api_key"] = ""
    if not node:
        raise ValueError("无有效配置项")
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def delete_provider(name: str) -> Dict[str, Any]:
    ai = _raw_ai()
    names = _provider_names(ai)
    if name not in names:
        raise ValueError(f"Provider 不存在: {name}")
    if len(names) <= 1:
        raise ValueError("禁止删除最后一个 Provider（需至少保留一个可用模型）")
    _raise_if_env_takeover(name)
    tree: Dict[str, Any] = {"ai": {name: None}}
    switched_to = None
    cur = get_current_ref(ai)
    if cur["provider"] == name:
        _raise_if_current_ref_env()
        rest = [n for n in names if n != name]
        target_p, target_m = "", ""
        for n in rest:  # 2026-09-21 小欧 修 M10/M11：扫第一个有可用模型的 provider，不止取 rest[0]
            ms = _models_of(ai, n)
            if ms:
                target_p, target_m = n, ms[0]["name"]
                break
        if not target_p:
            raise ValueError("禁止删除最后一个 Provider（其余 Provider 均无可用模型）")
        _sync_current(tree, target_p, target_m)
        switched_to = target_p or None
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}
