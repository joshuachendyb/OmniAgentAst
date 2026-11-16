# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-16 小欧 [23]阶段D: 新建能力路由(纯函数, 不落库)。InputNeed/need_of 聚合
#   输入项原生需求(按 degraded_ok 二选一归 required/optional); Candidate/route 按
#   「同 provider→实测优先→上下文长度↓→配置顺序」裁决链产出 RoutingAdvice;
#   build_candidates 从模型库 get_models() 逐模型取 profile_of 原生模态(唯一真源) — 小欧-2026-11-16
# 2026-11-16 小欧 [23]阶段D: RoutingAdvice 增 provider(前端一键切换落 L2 需 provider+model) — 小欧-2026-11-16

"""services.model.capability_router — 能力路由(纯函数, 零落库)。

只消费能力画像(profile_of)聚合出的 Candidate 与 preflight 逐项质量, 不判 accept、不发请求。
need_of: 输入项 → 原生需求(required/optional 按 degraded_ok 互斥归类)。
route:  需求 + 候选 → RoutingAdvice(keep|switch|degrade), 裁决链见 [23] §6.2。
"""
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Optional

# content_kind → 原生处理所需模态(text/binary/unknown 无原生模态, 不产生需求)
_CONTENT_MODALITY = {"image": "image", "video": "video", "audio": "audio", "richdoc": "file"}


@dataclass(frozen=True)
class InputNeed:
    required_native: FrozenSet[str] = frozenset()
    optional_native: FrozenSet[str] = frozenset()
    degraded_ok: bool = True


@dataclass(frozen=True)
class Candidate:
    model: str
    provider: str = ""
    native: FrozenSet[str] = frozenset()      # 声明支持的原生模态
    measured: FrozenSet[str] = frozenset()    # 其中经实测确认的模态(排序优先)
    context_length: int = 0
    order: int = 0                            # 配置顺序(稳定兜底)


@dataclass(frozen=True)
class RoutingAdvice:
    action: str = "keep"                      # keep | switch | degrade
    model: str = ""
    reason: str = ""
    provider: str = ""                        # switch 目标 provider(前端落 L2 需 provider+model)

    def to_dict(self) -> Dict[str, str]:
        return {"action": self.action, "model": self.model,
                "reason": self.reason, "provider": self.provider}


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def need_of(items: Optional[Iterable[Any]], degraded_ok: bool = True) -> InputNeed:
    """输入项(PreflightItem 或同名字典) → 原生需求聚合, 不做能力判定。

    content_kind∈{image,video,audio,richdoc} 且 quality 非 native(当前模型已降级)
      → 该模态计入需求域; quality=native/text/binary/unknown → 不产生需求。
    需求域按 degraded_ok 二选一: True→optional_native(降级可接受), False→required_native。
    """
    mods = set()
    for it in items or []:
        modality = _CONTENT_MODALITY.get(str(_field(it, "content_kind", "") or ""))
        quality = str(_field(it, "quality", "") or "")
        if modality and quality and quality != "native":
            mods.add(modality)
    wanted = frozenset(mods)
    if degraded_ok:
        return InputNeed(required_native=frozenset(), optional_native=wanted,
                         degraded_ok=True)
    return InputNeed(required_native=wanted, optional_native=frozenset(),
                     degraded_ok=False)


def _rank_key(wanted: FrozenSet[str], current_provider: str):
    """裁决链排序键: 同 provider 优先 → 实测优先于声明 → 上下文长度↓ → 配置顺序。"""
    def key(c: Candidate):
        same_provider = 0 if (current_provider and c.provider == current_provider) else 1
        measured = 0 if wanted <= c.measured else 1
        return (same_provider, measured, -int(c.context_length or 0), c.order)
    return key


def route(need: InputNeed, current_model: str = "",
          candidates: Optional[Iterable[Candidate]] = None,
          current_provider: str = "") -> RoutingAdvice:
    """需求 + 候选 → 建议。keep=保持当前; switch=推荐切换; degrade=必需能力缺失。"""
    wanted = frozenset(need.required_native or need.optional_native) if need else frozenset()
    if not wanted:
        return RoutingAdvice("keep")
    feasible = [c for c in (candidates or []) if wanted <= c.native]
    if not feasible:
        if need.required_native:
            return RoutingAdvice("degrade",
                                 reason="无候选模型原生支持必需能力，将降级处理")
        return RoutingAdvice("keep")          # optional 无候选: 降级可接受, 静默
    best = min(feasible, key=_rank_key(wanted, current_provider))
    if best.model == current_model:
        return RoutingAdvice("keep")
    return RoutingAdvice("switch", model=best.model, provider=best.provider,
                         reason=f"推荐切换至 {best.model}"
                                f"（原生支持 {'/'.join(sorted(wanted))}）")


def build_candidates() -> List[Candidate]:
    """候选唯一真源 = 模型库 get_models(); 逐模型经 capability.profile_of 取原生模态。

    native 来自 profile 的声明原生模态; measured 取 NativeCap.source=="measured" 的模态,
    仅用于排序优先(实测优先于声明), 不参与可行性判定。
    """
    from app.services.agent.capability import profile_of
    from app.services.model.model_service import get_models

    out: List[Candidate] = []
    order = 0
    for provider in get_models().get("providers", []) or []:
        provider_name = str(provider.get("name") or "")
        for model in provider.get("models", []) or []:
            model_name = str(model.get("name") or "")
            if not model_name:
                continue
            caps = profile_of(provider_name, model_name)
            native = frozenset(k for k, cap in caps.items() if getattr(cap, "native", False))
            measured = frozenset(
                k for k, cap in caps.items()
                if getattr(cap, "native", False) and getattr(cap, "source", "") == "measured")
            ctx = model.get("context_length")
            out.append(Candidate(model=model_name, provider=provider_name,
                                 native=native, measured=measured,
                                 context_length=int(ctx) if ctx else 0, order=order))
            order += 1
    return out
