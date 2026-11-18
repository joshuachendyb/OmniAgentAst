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

# 2026-11-18 opencode 修正: ①三个反查函数(_lookup_provider/_split_target/_target_known)
#   各自 get_models() 一次, 裸 model 一次预检要扫库 3 遍 → 合并为 _resolve_target 单扫
#   (provider/model/known 一次取齐); ②逐条判定加隔离, 单条脏数据只标该条失败,
#   不再整份预检为空; ③删 must_native(与 quality=="native" 同义且无消费方)与
#   _QUALITY_ORDER(死常量); ④strict 文案据实修正 —— 发送侧不存在该模式的拦截,
#   原注释"strict 拦截在发送侧 409"与实现不符 — opencode-2026-11-18


"""services.inputs.preflight — 输入预检(厚后端核心, 纯判定零副作用)。

两阶段管线(单一管道, 不另设旁路):
  识别阶段(模型无关): items[] 与正文扫描(scan_text_urls)合并 → classify_ref 出
    (source_kind, content_kind); 无条件执行, 不因模型不支持而跳过。
  能力判定阶段(读画像): quality_of(source, kind, profile) → 四态质量;
    delivery 由 QUALITY_TO_DELIVERY 单表派生, 不另设枚举。
准入判定复用 media_payload.url_reject_reason(与 remote_fetch 四闸门同源同判)。

不做的事(SRP): 不做体积裁决(budget)、不做上限计数(accepted)、不下载、不物化;
  strict 只改"需求域归类"(缺原生能力时给 degrade 建议), 与 suggest/auto 一样**不阻断发送**
  —— 本仓发送侧不存在该模式的拦截, 要不要换模型由用户点推荐条决定。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.attachments import contract
from app.attachments.extract import scan_text_urls
from app.logger import logger
from app.services.agent.media_payload import inline_limit_bytes, url_reject_reason


@dataclass
class PreflightItem:
    key: str
    source_kind: str
    content_kind: str
    ok: bool = True
    reason: str = ""
    quality: str = ""
    delivery: str = ""
    duplicate_of: str = ""
    url: str = ""


@dataclass
class PreflightResult:
    items: List[PreflightItem] = field(default_factory=list)
    worst_quality: str = "native"        # native | degraded(任一非 native 即 degraded)
    text_url_only: bool = False          # 正文去掉扫描到的 URL 后只剩空白(接管判据真源在后端)
    routing_advice: Dict[str, str] = field(
        default_factory=lambda: {"action": "keep", "reason": ""})


def _resolve_target(model_id: str) -> Tuple[str, str, bool]:
    """model_id → (provider, model, known), 模型库扫一遍取齐(不再各查各的)。

    'p/m': provider/model 直接取, known 另需模型库确有该组合(与"未知模型不判降级"一致);
    裸 model 名: 扫库反查首个含该模型的 provider, 命中即 known;
    库异常/未命中 → known=False(不臆造 provider, 不臆判降级, 不产路由建议)。
    """
    mid = str(model_id or "")
    if not mid:
        return "", "", False
    provider, sep, model = mid.partition("/")
    from app.services.model.model_service import get_models
    try:
        providers = get_models().get("providers") or []
    except Exception as e:  # noqa: BLE001 — 反查失败不阻断预检, 退化为未知模型
        logger.warning("[preflight] 模型库读取失败, 按未知模型处理: %s", e)
        return (provider if sep else ""), model, False
    if sep:
        found = any(
            str(p.get("name") or "") == provider
            and any(str(m.get("name") or "") == model for m in (p.get("models") or []))
            for p in providers)
        return provider, model, bool(provider and model and found)
    for p in providers:
        if any(str(m.get("name") or "") == mid for m in (p.get("models") or [])):
            return str(p.get("name") or ""), mid, True
    return "", mid, False


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
    size = contract.size_of(data)
    return 0 < size <= inline_limit_bytes()


def _item_key(source_kind: str, data: Dict[str, Any]) -> str:
    """去重键: url 用 url 本身; 本地来源用 path/attachment_id(+选区行区间); 兜底 label。"""
    if source_kind == "url":
        return str(data.get("url") or "")
    base = str(data.get("path") or data.get("attachment_id")
               or data.get("label") or "")
    lr = data.get("lineRange")
    stamp = f"{lr.get('start')}-{lr.get('end')}" if isinstance(lr, dict) and lr else ""
    return f"{base}#{stamp}" if base and stamp else base


def _judge(data: Dict[str, Any], prof: Dict[str, Any], known: bool) -> PreflightItem:
    """单条判定(识别 + 能力), 不含去重; 异常由调用方按条隔离。"""
    source_kind, content_kind = contract.classify_ref(data)
    key = _item_key(source_kind, data)
    url = str(data.get("url") or "")
    reason = url_reject_reason(url) if source_kind == "url" else ""
    item = PreflightItem(key=key or f"{source_kind}:{content_kind}",
                         source_kind=source_kind, content_kind=content_kind,
                         ok=not reason, reason=reason, url=url)
    if not known:
        return item      # 未知模型不判降级, 与"无模型不路由"同口径
    # 实例口径: 已物化或可物化的 file 图像/音频与运行时 plan_refs 同判, 消假降级
    has_slot = bool(data.get("attachment_id")) or _native_slot(
        source_kind, content_kind, data, prof)
    quality = contract.quality_of(source_kind, content_kind, prof, has_slot=has_slot)
    item.quality = quality
    item.delivery = contract.QUALITY_TO_DELIVERY[quality]
    return item


def preflight(text: str = "", items: Optional[List[Dict[str, Any]]] = None,
              model_id: str = "", profile: Optional[Dict[str, Any]] = None,
              mode: str = "suggest",
              candidates: Optional[List[Any]] = None
              ) -> PreflightResult:
    """输入预检(纯函数): 识别无条件执行 → 能力判定读画像 → 逐项产出建议。

    返回 PreflightResult(不含 limits/accepted — 上限裁决归发送侧唯一出口)。
    """
    from app.services.agent.capability import profile_of
    provider, model, known = _resolve_target(model_id)
    if profile is not None:
        known = True     # 显式传入画像视为已知
    prof = profile if profile is not None else profile_of(provider, model)
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
        try:
            item = _judge(data, prof, known)
        except Exception as e:  # noqa: BLE001 — 单条脏数据只标该条失败, 不整份清空
            logger.warning("[preflight] 单条判定失败(已隔离): kind=%r err=%s",
                           data.get("kind"), e)
            item = PreflightItem(
                key=str(data.get("url") or data.get("path") or data.get("label") or ""),
                source_kind=str(data.get("kind") or "file"), content_kind="unknown",
                ok=False, reason=f"预检失败: {type(e).__name__}")
        first = seen.get(item.key)
        if item.key and first:
            item.duplicate_of = first      # 去重不剔除: 保留条目并指向首条, 上层自行去重
        elif item.key:
            seen[item.key] = item.key
        result.items.append(item)
    if any(it.quality and it.quality != "native" for it in result.items):
        result.worst_quality = "degraded"
    # 2026-11-16 小欧 [23]阶段D: 传入 candidates 才路由(不传则保持默认 keep, 保纯核心零 I/O);
    #   strict → degraded_ok=False(缺必需能力可为 degrade), suggest/auto → True(降级可接受)。
    #   strict 只改"需求域归类", 不产生任何拦截 —— 发送侧也不拦(见模块说明), 建议仅供用户决策。
    if candidates is not None and known:
        from app.services.model.capability_router import need_of, route
        advice = route(need_of(result.items, degraded_ok=(mode != "strict")),
                       current_model=model or model_id,
                       candidates=candidates,
                       current_provider=provider)
        result.routing_advice = advice.to_dict()
    return result


def result_to_dict(r: PreflightResult) -> Dict[str, Any]:
    """API 序列化唯一出口(字段与 PreflightItem 一一对应, 无额外翻译)。"""
    return {"items": [vars(it) for it in r.items],
            "worst_quality": r.worst_quality,
            "text_url_only": r.text_url_only,
            "routing_advice": r.routing_advice}
