# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 模型输入能力画像(声明即首选, 实测仅标注/解锁 url 运输),
#   profile_of/profile/supports_image_input 薄投影, 零 IO — 小欧-2026-11-11

"""services.agent.capability — 模型输入能力画像(纯函数, 零 IO)。

声明模态即首选请求模式: input_modalities 含 m → native=True, transport={"inline"};
实测 media.accept[m] ∈ {url,both} 仅增补 transport="url"(运输优化)并标注 source=measured。
实测探针不参与请求判定(样本可能过期/失效), 只影响设置页展示与模型推荐。
"""
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet

from app.config import get_config


# normalize_modalities 是纯词汇归一, 归属重模块 model_service; 顶层 import 会与
# model_service→contract/capability 的下发依赖成环, 故函数内延迟导入。
def _normalize_modalities(values: Any):
    from app.services.model.model_service import normalize_modalities
    return normalize_modalities(values)


@dataclass(frozen=True)
class NativeCap:
    native: bool
    transport: FrozenSet[str]     # {"inline"} / {"inline","url"} / frozenset()
    source: str                   # declared | measured | none (仅展示标注)


_MODALITIES = ("image", "audio", "video", "file")
_EMPTY = frozenset()


def _meta_of(provider: str, model: str) -> Dict[str, Any]:
    """(provider, model) → model_meta 块; 逐级字面键取, 迁移后唯一。"""
    if not provider or not model:
        return {}
    cfg = (get_config().get("ai") or {}).get(provider) or {}
    meta = (cfg.get("model_meta") or {}).get(model) or {}
    return meta if isinstance(meta, dict) else {}


def profile_of(provider: str, model: str) -> Dict[str, NativeCap]:
    """统一入口: 发送侧(llm_model 抽二元组)与 preflight 侧(model_id 解析)同源取画像。"""
    meta = _meta_of(provider, model)
    declared = set(_normalize_modalities(meta.get("input_modalities")))
    accept = ((meta.get("media") or {}).get("accept") or {}) if isinstance(meta.get("media"), dict) else {}
    caps: Dict[str, NativeCap] = {}
    for m in _MODALITIES:
        if m in declared:
            measured = str(accept.get(m) or "")
            transport = {"inline", "url"} if measured in ("url", "both") else {"inline"}
            caps[m] = NativeCap(True, frozenset(transport),
                                "measured" if measured else "declared")
        else:
            caps[m] = NativeCap(False, _EMPTY, "none")
    return caps


def profile(llm_model: Any) -> Dict[str, NativeCap]:
    """薄投影: llm_model 对象 → profile_of; 供计划器/展开期按当前模型取画像。"""
    return profile_of(getattr(llm_model, "provider", "") or "",
                      getattr(llm_model, "model", "") or "")


def supports_image_input(llm_model: Any) -> bool:
    """兼容性薄投影(唯一导出): 语义=profile["image"].native, 不再自行判定。"""
    return profile(llm_model)["image"].native
