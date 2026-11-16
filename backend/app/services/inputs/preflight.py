# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 小欧 新建: 输入预检唯一入口。聚合识别
#   (classify_ref/scan_text_urls, 无 model_id)与能力判定(quality_of, 读 profile),
#   产出逐项 key/source_kind/content_kind/ok/reason/quality/delivery/must_native/
#   duplicate_of + worst_quality + routing_advice。建议性预览: 不含 limits/accepted,
#   不下载、不触发二次抽取 — 小欧-2026-11-15
# 2026-11-16 小欧 [23]阶段D: 增 mode(suggest/auto/strict)与 candidates 入参; 传入 candidates
#   时经 capability_router(need_of→route)产出 routing_advice(degraded_ok=(mode!=strict)),
#   preflight 永不阻断(strict 也只出建议, 阻断在发送侧) — 小欧-2026-11-16

"""services.inputs.preflight — 输入预检(厚后端核心, 纯判定零副作用)。

两阶段管线(单一管道, 不另设旁路):
  识别阶段(模型无关): items[] 与正文扫描(scan_text_urls)合并 → classify_ref 出
    (source_kind, content_kind); 无条件执行, 不因模型不支持而跳过。
  能力判定阶段(读画像): quality_of(source, kind, profile) → 四态质量;
    delivery 由 QUALITY_TO_DELIVERY 单表派生, 不另设枚举。
准入判定复用 media_payload.url_reject_reason(与 remote_fetch 四闸门同源同判)。

不做的事(SRP): 不做体积裁决(budget)、不做上限计数(accepted)、不下载、不物化;
  strict 拦截只在发送侧, 本模块永不阻断。
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.attachments import contract
from app.attachments.extract import scan_text_urls
from app.services.agent.media_payload import url_reject_reason

_QUALITY_ORDER = ("native", "text_full", "meta_only", "link_only")


@dataclass
class PreflightItem:
    key: str
    source_kind: str
    content_kind: str
    ok: bool = True
    reason: str = ""
    quality: str = ""
    delivery: str = ""
    must_native: bool = False
    duplicate_of: str = ""
    url: str = ""


@dataclass
class PreflightResult:
    items: List[PreflightItem] = field(default_factory=list)
    worst_quality: str = "native"        # native | degraded(任一非 native 即 degraded)
    text_url_only: bool = False          # 正文去掉扫描到的 URL 后只剩空白(接管判据真源在后端)
    routing_advice: Dict[str, str] = field(
        default_factory=lambda: {"action": "keep", "reason": ""})


def _resolve_profile(model_id: str, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """画像唯一来源: 显式传入优先; 否则 model_id 解析(与 capability.profile_of 同源)。"""
    if profile is not None:
        return profile
    from app.services.agent.capability import profile_of
    provider, _, model = model_id.partition("/")
    return profile_of(provider, model)


def _item_key(source_kind: str, data: Dict[str, Any]) -> str:
    """去重键: url 用 url 本身; 本地来源用 path/attachment_id; 兜底 label。"""
    if source_kind == "url":
        return str(data.get("url") or "")
    return str(data.get("path") or data.get("attachment_id")
               or data.get("label") or "")


def preflight(text: str = "", items: Optional[List[Dict[str, Any]]] = None,
              model_id: str = "", profile: Optional[Dict[str, Any]] = None,
              mode: str = "suggest",
              candidates: Optional[List[Any]] = None
              ) -> PreflightResult:
    """输入预检(纯函数): 识别无条件执行 → 能力判定读画像 → 逐项产出建议。

    返回 PreflightResult(不含 limits/accepted — 上限裁决归发送侧唯一出口)。
    """
    prof = _resolve_profile(model_id, profile)
    scanned = scan_text_urls(text or "")
    raw: List[Dict[str, Any]] = list(items or [])
    raw += [{"kind": "url", "url": u} for u in scanned]

    result = PreflightResult()
    # 正文接管判据(单一真源在后端): 扫描到的 URL 从正文移除后只剩空白,
    # 即该次粘贴/拖拽是纯 URL 内容 → 前端据此撤出正文改挂 chip; 混排/纯文本为 False。
    rest = text or ""
    for u in scanned:
        rest = rest.replace(u, "")
    result.text_url_only = bool(scanned) and rest.strip() == ""
    seen: Dict[str, str] = {}
    for data in raw:
        if not isinstance(data, dict):
            continue
        source_kind, content_kind = contract.classify_ref(data)
        key = _item_key(source_kind, data)
        url = str(data.get("url") or "")
        reason = url_reject_reason(url) if source_kind == "url" else ""
        item = PreflightItem(key=key or f"{source_kind}:{content_kind}",
                             source_kind=source_kind, content_kind=content_kind,
                             ok=not reason, reason=reason, url=url)
        first = seen.get(key)
        if key and first:
            item.duplicate_of = first      # 去重不剔除: 保留条目并指向首条, 上层自行去重
        else:
            if key:
                seen[key] = item.key
            quality = contract.quality_of(source_kind, content_kind, prof)
            item.quality = quality
            item.delivery = contract.QUALITY_TO_DELIVERY[quality]
            item.must_native = quality == "native"
        result.items.append(item)
    if any(it.quality and it.quality != "native" for it in result.items):
        result.worst_quality = "degraded"
    # 2026-11-16 小欧 [23]阶段D: 传入 candidates 才路由(不传则保持默认 keep, 保纯核心零 I/O);
    #   strict → degraded_ok=False(缺必需能力缺可为 degrade), suggest/auto → True(降级可接受)。
    if candidates is not None:
        from app.services.model.capability_router import need_of, route
        current_provider, _, current_model = model_id.partition("/")
        advice = route(need_of(result.items, degraded_ok=(mode != "strict")),
                       current_model=current_model or model_id,
                       candidates=candidates,
                       current_provider=current_provider if current_model else "")
        result.routing_advice = advice.to_dict()
    return result


def result_to_dict(r: PreflightResult) -> Dict[str, Any]:
    """API 序列化唯一出口(字段与 PreflightItem 一一对应, 无额外翻译)。"""
    return {"items": [vars(it) for it in r.items],
            "worst_quality": r.worst_quality,
            "text_url_only": r.text_url_only,
            "routing_advice": r.routing_advice}
