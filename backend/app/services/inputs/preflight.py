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

# 2026-11-16 小欧 修正: route 的 keep 判定补 provider 比对; 无候选/入参异常的隔离在调用侧(候选为空即可)

# 2026-11-16 小欧 bug猎修: 能力判定改实例口径(quality_of 透传 has_slot), 已物化条目
#   (attachment_id)与运行时 plan_refs 同判, 消预检误报降级并错误建议切模型

# 2026-11-16 opencode 修正: ①裸 model 名反查 provider 取画像(原按 '/' 切分致 model 为空、
#   全量误判降级); 模型库无法定位的未知模型不判降级、不产生路由建议。②未物化 file 图像/音频按 resolver 物化前置(原生+内联上限+音频容器)预判
#   可原生, 消预检/运行时相反; ③去重键补 lineRange, 不同选区不再互相标重复; ④text_url_only
#   按 URL 长度降序移除, 消前缀包含残留。


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
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.attachments import contract
from app.attachments.extract import scan_text_urls
from app.services.agent.media_payload import inline_limit_bytes, url_reject_reason

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


def _lookup_provider(model: str) -> str:
    """裸 model 名在模型库反查唯一 provider; 库异常/未命中返回空串(不臆造 provider)。"""
    if not model:
        return ""
    from app.services.model.model_service import get_models
    try:
        for p in (get_models().get("providers") or []):
            if any(str(m.get("name") or "") == model for m in (p.get("models") or [])):
                return str(p.get("name") or "")
    except Exception:  # noqa: BLE001 — 反查失败不阻断预检, 退化为仅按 model 取画像
        pass
    return ""


def _split_target(model_id: str) -> tuple:
    """model_id → (provider, model): 'p/m' 按 '/' 切分; 裸 model 反查 provider。"""
    mid = str(model_id or "")
    provider, sep, model = mid.partition("/")
    if sep:
        return provider, model
    return _lookup_provider(mid), mid


def _resolve_profile(model_id: str, profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """画像唯一来源: 显式传入优先; 否则 provider/model 解析后取画像(与 capability.profile_of 同源)。"""
    if profile is not None:
        return profile
    from app.services.agent.capability import profile_of
    provider, model = _split_target(model_id)
    return profile_of(provider, model)


def _native_slot(source_kind: str, content_kind: str, data: Dict[str, Any],
                 prof: Dict[str, Any]) -> bool:
    """未物化 file 图像/音频的可物化原生预判(与 resolver 物化前置同口径):
    模型声明原生 + 体积在单文件内联上限内 + 音频容器为 wav/mp3。发送解析必在会话内进行,
    会话条件成立, 故不在此判会话, 避免预检与运行时相反造成假降级。"""
    if source_kind != "file" or content_kind not in ("image", "audio"):
        return False
    route = contract.KIND_CONTRACT[(source_kind, content_kind)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if not (cap and cap.native):
        return False
    if content_kind == "audio" and Path(str(data.get("path") or "")).suffix.lower() \
            not in contract.AUDIO_NATIVE_EXTS:
        return False
    try:
        size = int(data.get("size") or 0)
    except (TypeError, ValueError):
        return False
    return 0 < size <= inline_limit_bytes()


def _target_known(model_id: str) -> bool:
    """模型是否可解析(用于未知模型不臆判降级): 显式传画像时由调用方保证已知, 此处只判模型库。"""
    provider, model = _split_target(model_id)
    if not model:
        return False
    from app.services.model.model_service import get_models
    try:
        for p in (get_models().get("providers") or []):
            if provider and str(p.get("name") or "") != provider:
                continue
            if any(str(m.get("name") or "") == model for m in (p.get("models") or [])):
                return True
    except Exception:  # noqa: BLE001 — 反查失败按未知处理, 不臆判降级
        return False
    return False


def _item_key(source_kind: str, data: Dict[str, Any]) -> str:
    """去重键: url 用 url 本身; 本地来源用 path/attachment_id(+选区行区间); 兜底 label。"""
    if source_kind == "url":
        return str(data.get("url") or "")
    base = str(data.get("path") or data.get("attachment_id")
               or data.get("label") or "")
    lr = data.get("lineRange")
    stamp = f"{lr.get('start')}-{lr.get('end')}" if isinstance(lr, dict) and lr else ""
    return f"{base}#{stamp}" if base and stamp else base


def preflight(text: str = "", items: Optional[List[Dict[str, Any]]] = None,
              model_id: str = "", profile: Optional[Dict[str, Any]] = None,
              mode: str = "suggest",
              candidates: Optional[List[Any]] = None
              ) -> PreflightResult:
    """输入预检(纯函数): 识别无条件执行 → 能力判定读画像 → 逐项产出建议。

    返回 PreflightResult(不含 limits/accepted — 上限裁决归发送侧唯一出口)。
    """
    prof = _resolve_profile(model_id, profile)
    # 画像已知才做能力判定: 显式传入画像视为已知; 否则模型库须能定位该模型。
    # 未知模型不判降级、不产生路由建议, 与"无模型不路由"同口径。
    known = profile is not None or _target_known(model_id)
    scanned = scan_text_urls(text or "")
    raw: List[Dict[str, Any]] = list(items or [])
    raw += [{"kind": "url", "url": u} for u in scanned]

    result = PreflightResult()
    # 正文接管判据(单一真源在后端): 扫描到的 URL 从正文移除后只剩空白,
    # 即该次粘贴/拖拽是纯 URL 内容 → 前端据此撤出正文改挂 chip; 混排/纯文本为 False。
    rest = text or ""
    for u in sorted(scanned, key=len, reverse=True):
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
            if not known:
                result.items.append(item)
                continue
            # 实例口径: 已物化或可物化的 file 图像/音频与运行时 plan_refs 同判, 消假降级
            has_slot = bool(data.get("attachment_id")) or _native_slot(
                source_kind, content_kind, data, prof)
            quality = contract.quality_of(source_kind, content_kind, prof,
                                          has_slot=has_slot)
            item.quality = quality
            item.delivery = contract.QUALITY_TO_DELIVERY[quality]
            item.must_native = quality == "native"
        result.items.append(item)
    if any(it.quality and it.quality != "native" for it in result.items):
        result.worst_quality = "degraded"
    # 2026-11-16 小欧 [23]阶段D: 传入 candidates 才路由(不传则保持默认 keep, 保纯核心零 I/O);
    #   strict → degraded_ok=False(缺必需能力缺可为 degrade), suggest/auto → True(降级可接受)。
    if candidates is not None and known:
        from app.services.model.capability_router import need_of, route
        current_provider, current_model = _split_target(model_id)
        advice = route(need_of(result.items, degraded_ok=(mode != "strict")),
                       current_model=current_model or model_id,
                       candidates=candidates,
                       current_provider=current_provider)
        result.routing_advice = advice.to_dict()
    return result


def result_to_dict(r: PreflightResult) -> Dict[str, Any]:
    """API 序列化唯一出口(字段与 PreflightItem 一一对应, 无额外翻译)。"""
    return {"items": [vars(it) for it in r.items],
            "worst_quality": r.worst_quality,
            "text_url_only": r.text_url_only,
            "routing_advice": r.routing_advice}
