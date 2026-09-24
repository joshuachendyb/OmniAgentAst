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
# 2026-09-22 - 小欧 - [62]P1/P2 param_options 读写链落地：①P1 加 DEFAULT_PARAM_OPTIONS 全局兜底 +
#   _resolve_param_options 三层解析并集（模型级>provider级>全局）、_models_of 组装 param_options；
#   update_model 先合并本次新选项再校验（避免同批改选项+改值误杀）、unknown 白名单加 param_options、
#   落 model_meta；update_provider_config key_map 加 param_options（Provider级写入口）。
#   ②P2 add_model 签名加 param_options + 选项表非空 string[]/值在表内（0拒）校验 + 落 model_meta
#   （不送 param_options 与现状兼容，tree 不写该键）。
# 2026-09-22 - 小欧 - [62]P7 4.3(1)c：get_models 显示层 timeout/max_retries 兜底改读 tuning
#   （timeout→tuning.llm_net.read_timeout 默认150、max_retries→tuning.llm.stream_max_retries 默认3），
#   import 补 from app.config import get_config——消除显示值60/3与运行时30/3 不一致（显示即真相）。
# 2026-09-22 - 小欧 - [62]P8 4.3(9)：①常量区加 PROVIDER_PARAM_TYPES + KNOWN_PROVIDER_KEYS（元数据源头，
#   新增 Provider 参数只需加一行 + config.yaml 对字段，前端零改）；②get_models Provider 段加
#   param_types 元数据 + 动态标量值透传（KNOWN_PROVIDER_KEYS 之外标量平铺）；③update_provider_config
#   加 param_types 白名单（key_map + PROVIDER_PARAM_TYPES 之外拒，防任意键注入）+ 动态字段落盘
#   （param_types 内 key_map 外的标量直写 ai.{provider}.{k}，复用 merge_nested_patch 叶值链路）。
# 2026-09-24 - 小欧 - 参数键级删除：update_model 白名单加 remove_params——先从 model_params 拷贝删键、
#   同步清 model_meta.range/param_options 对应键，再 merge default_params（空 dp 仍=整块清空，与既有 P8 语义叠加：
#   remove 先算好 new_params，dp 非空则 update，dp 为空则置 {}）。前端①参数行 × 删除按钮通道 — 小欧-2026-09-24
# 2026-09-24 - 小欧 - 三堂会审修复（BZ-3/BZ-6/BZ-7/BZ-9 四条，逐条真伪鉴别后落码）：
#   ①BZ-3 remove 不再无条件 setdefault model_meta（原必建空块落 YAML model_meta.{model}:{} 污染），
#     range/param_options 清理仅实际命中才建块；
#   ②BZ-6 remove 的 meta 清理挪到 fields param_options 写入之后执行（原在前，293 行同批
#     param_options 全量覆盖使已删键选项复活）；清理跳过 default_params 重加键（keep 集合，
#     remove+dp 同批恢复值时其 meta 保留不误删）；
#   ③BZ-7 remove_params 全为不存在键（model_params 均无命中且 meta 无命中、无 default_params、
#     无其它字段）= 幂等 no-op 成功返回不写盘（原仍全量 merge 空耗备份/原子重写/mtime 抖动）；
#   ④BZ-9 range/param_options 双份近似清理收敛 for meta_key 单循环（DRY）— 小欧-2026-09-24
# 2026-09-24 - 小欧 - [68] 模型库：新增 fetch_remote_models（GET 远程列表）与
#   replace_provider_models（PUT 替换写入 + 差集孤儿清理）— 小欧-2026-09-24
# 2026-09-24 23:55:00 - 小欧 - [68] 第四章核查修复 2 处：①fetch_remote_models 组头
#   api_key 补读 {NAME}_API_KEY env 接管值（env 优先，YAML 兜底；原仅读 YAML，
#   env 接管时 YAML 可无 api_key 致 Bearer 空 key 远端 401）；②api_base 空的 400
#   文案补「该 Provider」前缀对齐设计 L138 — 小欧-2026-09-24
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import os
import httpx
from fastapi import HTTPException
from app.llm.adapters import get_provider_adapter

from app.logger import logger
from app.config import get_config  # [62]P7 4.3(1)c：get_models 显示层读 tuning 三层回落 — 小欧 2026-09-22（config_helpers 同层已引，无循环）
from app.services.model.config_helpers import (
    get_config_path,
    mask_secret_value,
    merge_nested_patch,
    read_yaml_config,
    _config_mtime,
)

RESERVED_AI_KEYS = {"provider", "model", "model_ref"}

# v1.1：仅全局兜底默认，不同模型3/4/5个选项走config覆盖，不写死（小欧 2026-09-22）
DEFAULT_PARAM_OPTIONS: Dict[str, List[str]] = {
    "reasoning_effort": ["low", "medium", "high"],
}

# [62]P8 4.3(9)-1 动态参数元数据表象（小欧 2026-09-22）
# 新增 Provider 参数：在此加一行 + config.yaml 对应 provider 加字段，前后端自动适配，不再改前端代码
# （rate_limit 作闭环演示实例保留启用——BY-09 测试以它验证读-写-存-显四段）
PROVIDER_PARAM_TYPES: Dict[str, Dict[str, Any]] = {
    "timeout":     {"type": "number", "label": "超时(秒)", "min": 1, "default": 60},
    "max_retries": {"type": "number", "label": "重试次数", "min": 0, "default": 3},
    "label":       {"type": "string", "label": "显示名"},
    "rate_limit":  {"type": "number", "label": "速率限制", "min": 0, "default": 0},
}
KNOWN_PROVIDER_KEYS = {"name", "api_base", "api_key", "env", "models", "param_types"}


def _resolve_param_options(ai: Dict[str, Any], provider: str, model: str,
                           params: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, List[str]]:
    """三层解析 param_options（模型级 > provider级 > 全局兜底）并取并集（小欧 2026-09-22）。

    params=该模型 model_params 当前值，meta=该模型 model_meta；并集保证"有选项无默认值"
    时值不丢（config 已配置该项但 meta 未列选项 → 用 server/provider 级选项承接）。
    """
    out: Dict[str, List[str]] = {}
    meta_opts = meta.get("param_options") or {}
    for k in list(params) + [k for k in meta_opts if k not in params]:
        mo = meta_opts.get(k)  # 1.模型级最高
        po = ((ai.get(provider) or {}).get("param_options") or {}).get(k)  # 2.provider级
        go = DEFAULT_PARAM_OPTIONS.get(k)  # 3.全局兜底
        v = mo if mo is not None else (po if po is not None else go)
        if isinstance(v, list) and v:
            out[k] = list(v)
    return out


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
            "param_options": _resolve_param_options(ai, provider, m, params, meta),
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
                          "timeout": p.get('timeout') if p.get('timeout') is not None else get_config().get("tuning.llm_net.read_timeout", 150),  # [62]P7 4.3(1)c：显示值=运行时三层回落值（原兜底60≠运行30，显示即真相被打破）
                          "max_retries": p.get('max_retries') if p.get('max_retries') is not None else get_config().get("tuning.llm.stream_max_retries", 3),  # [62]P7 4.3(1)c：与 __init__ 三层回落同源
                          "param_types": PROVIDER_PARAM_TYPES,  # [62]P8 4.3(9)-2-a：元数据表下发（前端只渲染不定义）
                          **{k: v for k, v in p.items()
                             if k not in KNOWN_PROVIDER_KEYS and isinstance(v, (str, int, float, bool))},  # [62]P8 4.3(9)-2-a：动态标量值透传（rate_limit 等新参数零改前端）
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
              capabilities: Optional[List[str]] = None,
              param_options: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    _raise_if_env_takeover(provider)
    if not model:
        raise ValueError("模型名不能为空")
    if any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError("同名模型已存在")
    # 与 update_model 同规则：选项表须为非空 string[]，值须在表内，0 直接 400（小欧 2026-09-22）
    allowed = dict(param_options or {})
    for k, vs in allowed.items():
        if not isinstance(vs, list) or not vs or not all(isinstance(x, str) for x in vs):
            raise ValueError(f"不支持的选项表: {k}须为非空string[]")
    for k, v in (default_params or {}).items():
        allow = allowed.get(k, DEFAULT_PARAM_OPTIONS.get(k))
        if allow is not None and v not in allow:
            raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allow}")
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
                **({"param_options": param_options} if param_options else {}),
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
    # 白名单放行+落model_meta（小欧 2026-09-22：加 param_options，否则送了即报不支持的配置项）
    # 2026-09-24 小欧：加 remove_params（键级删除，与 default_params merge 叠加）— 小欧-2026-09-24
    unknown = set(fields) - {"label", "range", "capabilities", "default_params", "param_options", "remove_params"}
    if unknown:
        raise ValueError(f"不支持的配置项: {sorted(unknown)}")
    tree: Dict[str, Any] = {"ai": {provider: {}}}
    node = tree["ai"][provider]
    for k in ("label", "range", "capabilities"):
        if fields.get(k) is not None:
            node.setdefault("model_meta", {}).setdefault(model, {})[k] = fields[k]
    dp = fields.get("default_params")
    # v1.6：先合并本次新选项再校验，避免同批改选项+改值时用旧单子误杀（小欧 2026-09-22）
    cur = next((x for x in _models_of(ai, provider) if x["name"] == model), None) or {}
    allowed = dict(cur.get("param_options") or {})
    if isinstance(fields.get("param_options"), dict):
        for k, v in fields["param_options"].items():
            if isinstance(v, list) and v:
                allowed[k] = list(v)
    if isinstance(dp, dict):
        for k, v in dp.items():
            if k in allowed and v not in allowed[k]:
                raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allowed[k]}")
    # 2026-09-24 小欧：remove_params 键级删除——拷贝当前 model_params 删键得 new_params；
    #   三堂会审修复（BZ-3/BZ-6/BZ-7/BZ-9）：①移除本段原无条件 setdefault model_meta（原 remove
    #   必建空块、YAML 落 model_meta.{model}:{} 污染）；②range/param_options 清理挪到下方
    #   fields 写入完成之后统一做（remove 删除意图最终生效，防同批 param_options 覆盖复活；
    #   且跳过 default_params 重加键 keep——remove+dp 同批恢复值时其 meta 保留）；③双份
    #   range/options 清理收敛 for meta_key 循环（DRY）；④remove 全为不存在键且 meta 无命中时
    #   不再空写盘（幂等 no-op 成功返回）— 小欧-2026-09-24
    removed = fields.get("remove_params")
    orig_params = ai[provider].get("model_params", {}).get(model, {}) or {}
    new_params: Optional[Dict[str, Any]] = None
    removed_hit = False
    if isinstance(removed, list) and removed:
        removed_hit = any(k in orig_params for k in removed)
        new_params = dict(orig_params)
        for k in removed:
            new_params.pop(k, None)
    if isinstance(dp, dict):
        if dp:
            if new_params is None:
                new_params = dict(orig_params)
            new_params.update(dp)
        else:
            # 2026-09-21 小欧 修 P8：空 default_params 提交 = 显式清空模型参数块（原实现走
            # isinstance 且为空跳过 → node 空 → "无有效配置项" 500）。merge_nested_patch
            # 支持空 dict 叶值直接落 YAML 空块，validate 侧 parseInt 兼容。
            new_params = {}
    # BZ-7：仅 remove 真命中或 default_params 有变更才写 model_params（全 miss 不空写）
    if new_params is not None and (removed_hit or isinstance(dp, dict)):
        node.setdefault("model_params", {})[model] = new_params
    # 选项表落 model_meta（小欧 2026-09-22）
    if isinstance(fields.get("param_options"), dict):
        node.setdefault("model_meta", {}).setdefault(model, {})["param_options"] = fields["param_options"]
    # BZ-3/BZ-6/BZ-9：remove 同步清 range/param_options——在 fields 写入之后执行（删除意图最终
    #   生效，防 293 行同批 param_options 覆盖复活）；跳过 default_params 中重加键（keep）；
    #   仅实际命中才 setdefault 建 model_meta 块（防空块污染）；range/options 单循环（DRY）
    if isinstance(removed, list) and removed:
        keep = set(dp) if isinstance(dp, dict) else set()
        base_meta = (ai[provider].get("model_meta", {}) or {}).get(model, {}) or {}
        node_meta = node.get("model_meta", {}).get(model)
        for meta_key in ("range", "param_options"):
            cur = dict((node_meta or {}).get(meta_key) or base_meta.get(meta_key) or {})
            hit_keys = [k for k in removed if k not in keep and k in cur]
            if hit_keys:
                for k in hit_keys:
                    cur.pop(k, None)
                node.setdefault("model_meta", {}).setdefault(model, {})[meta_key] = cur
    if not node:
        # BZ-7：remove_params 全为不存在键 = 幂等 no-op，成功返回不写盘（原仍全量 merge，
        #   空耗备份/原子重写/mtime 抖动）；其余无有效配置项仍拒
        if isinstance(removed, list) and removed:
            return {"ok": True, "model": model, "mtime": _config_mtime()}
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
               "label": "label", "param_options": "param_options"}
    # [62]P8 4.3(9)-3-d 白名单：仅 key_map + PROVIDER_PARAM_TYPES + clear（清空标记）内字段可落盘，其余拒（防任意键注入）
    if isinstance(fields, dict):
        unknown_key = next(
            (k for k in fields if k not in set(key_map) and k not in PROVIDER_PARAM_TYPES
             and k != "clear"), None
        )
        if unknown_key:
            raise ValueError(f"不支持的Provider配置项: {unknown_key}")
    tree: Dict[str, Any] = {"ai": {name: {}}}
    node = tree["ai"][name]
    for k, v in fields.items():
        if k in key_map and v is not None:
            node[key_map[k]] = v
    # [62]P8 4.3(9)-3-d 动态参数落盘：param_types 内、key_map 外的动态字段写 ai.{provider}.{k}（标量叶值直写）
    for k, v in fields.items():
        if k in PROVIDER_PARAM_TYPES and k not in key_map:
            node[k] = v
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


def _require_provider_for_fetch(name: str, ai: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """[68] 拉取前置校验层：provider 存在性 + api_base 非空，返回 (p, api_base) — 小欧 2026-09-24"""
    if name not in _provider_names(ai):
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")
    p = ai[name]  # _provider_names 已保证 isinstance(ai[name], dict)
    api_base = str(p.get("api_base") or "").strip()
    if not api_base:
        raise HTTPException(status_code=400, detail="该 Provider 未配置 api_base，请先到模型 Tab → ③ Provider 配置填写")
    return p, api_base


async def _http_get_remote_models(api_base: str, headers: Dict[str, str]) -> Tuple[Any, Optional[str]]:
    """[68] HTTP 拉取层 → (resp, err)；网络异常统一 err 文案 — 小欧 2026-09-24"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{api_base.rstrip('/')}/models", headers=headers)
    except Exception as e:
        logger.error(f"拉取远程模型失败: {e}")
        return None, f"拉取失败: {e}"
    return resp, None


def _parse_remote_models_body(resp: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """[68] 响应解析层 → (models, err)；HTTP>=400/非JSON/非数组 → err — 小欧 2026-09-24"""
    if resp.status_code >= 400:
        message = f"HTTP {resp.status_code}"
        try:
            body = resp.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict) and err.get("message"):
                    message = str(err["message"])
                elif body.get("message"):
                    message = str(body["message"])
        except Exception:
            pass
        return None, message
    try:
        body = resp.json()
    except Exception as e:
        return None, f"响应解析失败: {e}"
    if not isinstance(body, dict):
        return None, "远端返回结构异常"
    data = body.get("data")
    if not isinstance(data, list):
        return None, "远端返回结构异常（data 非数组）"
    models: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        mid = item.get("id") or item.get("model")
        if not mid:
            continue
        models.append({"id": str(mid), "owned_by": item.get("owned_by")})
    return models, None


async def fetch_remote_models(name: str) -> Dict[str, Any]:
    """[68] 拉取 Provider 远程模型列表 — 后端代理绕 CORS；远端失败统一 200+ok:false — 小欧 2026-09-24"""
    ai = _raw_ai()
    p, api_base = _require_provider_for_fetch(name, ai)
    # 2026-09-24 23:55:00 - 小欧 - 设计 L137：api_key 含 {NAME}_API_KEY env 接管值（env 优先，YAML 兜底）— 小欧-2026-09-24
    api_key = os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or "")
    headers = get_provider_adapter(name).static_headers(api_key)
    configured = [m for m in (p.get("models") or []) if isinstance(m, str)]
    ref = get_current_ref(ai)
    current_model = ref["model"] if ref["provider"] == name else None

    def _fail(message: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "provider": name,
            "models": [],
            "count": 0,
            "configured": configured,
            "current_model": current_model,
            "message": message,
        }

    resp, err = await _http_get_remote_models(api_base, headers)
    if err:
        return _fail(err)
    models, err = _parse_remote_models_body(resp)
    if err:
        return _fail(err)
    return {
        "ok": True,
        "provider": name,
        "models": models,
        "count": len(models),
        "configured": configured,
        "current_model": current_model,
    }


def replace_provider_models(name: str, models: List[str]) -> Dict[str, Any]:
    """[68] 替换式写入 ai.{provider}.models + 差集孤儿清理 — 小欧 2026-09-24"""
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")
    p = ai[name]  # _provider_names 已保证 isinstance(ai[name], dict)
    if os.environ.get(f"{name.upper()}_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{name}' 由环境变量 {name.upper()}_API_KEY 接管，只读",
        )
    new_list: List[str] = []
    seen = set()
    for m in models:
        s = str(m).strip()
        if s and s not in seen:
            seen.add(s)
            new_list.append(s)
    if not new_list:
        raise HTTPException(status_code=400, detail="模型列表不能为空")
    ref = get_current_ref(ai)
    if ref["provider"] == name and ref["model"] and ref["model"] not in new_list:
        raise HTTPException(
            status_code=400,
            detail=f"不能移除当前全局模型 {ref['model']}，请先切换全局模型",
        )
    old = [m for m in (p.get("models") or []) if isinstance(m, str)]
    removed = [m for m in old if m not in set(new_list)]
    added = [m for m in new_list if m not in set(old)]
    tree: Dict[str, Any] = {"ai": {name: {"models": new_list}}}
    node = tree["ai"][name]
    params_block = p.get("model_params") or {}
    meta_block = p.get("model_meta") or {}
    if isinstance(params_block, dict):
        orphans = {m: None for m in removed if m in params_block}
        if orphans:
            node["model_params"] = orphans
    if isinstance(meta_block, dict):
        orphans = {m: None for m in removed if m in meta_block}
        if orphans:
            node["model_meta"] = orphans
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "mtime": _config_mtime(), "added": added, "removed": removed}
