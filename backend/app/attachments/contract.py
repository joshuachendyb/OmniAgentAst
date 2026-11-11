# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 附件能力协商契约(二维 KIND_CONTRACT / KindRoute / ItemPlan /
#   classify_ref / dedup_key / state_of / plan_refs / aggregate_state / ref_capability_map /
#   limits / kind_options), 零 IO 零配置, 仅引用 extract 词典与具名出口 — 小欧-2026-11-11

# 2026-11-11 小欧 三堂会审整改: 增 suffix_kind() 后缀→content_kind 词典下发出口,
#   消前端 useRefCapabilityMap 复制后缀表的双真源漂移 — 小欧-2026-11-11


"""attachments.contract — 能力协商契约(纯函数, 零 IO 零配置)。

单一契约表 KIND_CONTRACT[(source_kind, content_kind)] → KindRoute:
类型×来源 → 原生模态/降级质量/文本出口/失败回退。前后端与守门测试共用其投影。
"""
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.attachments.extract import (
    AUDIO_SUFFIXES,
    IMAGE_SUFFIXES,
    RICH_SUFFIXES,
    TEXT_SUFFIXES,
    VIDEO_SUFFIXES,
    _audio_card,
    _binary_card,
    _image_card,
    _link_body,
    _richdoc_body,
    _text_body,
    _video_card,
    classify,
    classify_url,
    scan_text_urls,
)
from app.constants import MAX_REMOTE_IMAGES

# 对外重导出词典与识别函数(契约消费方禁止再去 extract 复制一份)
__all__ = [
    "KIND_CONTRACT", "KIND_MODALITY", "KindRoute", "ItemPlan", "SOURCE_KINDS",
    "CONTENT_KINDS", "MODALITIES", "STATES", "classify_ref", "dedup_key", "state_of",
    "plan_refs", "aggregate_state", "ref_capability_map", "limits", "kind_options",
    "suffix_kind",
    "AUDIO_SUFFIXES", "IMAGE_SUFFIXES", "RICH_SUFFIXES", "TEXT_SUFFIXES", "VIDEO_SUFFIXES",
    "classify_url", "scan_text_urls",
]

_MAX_URLS = 8   # 单次引用 URL 条数上限(本方案新增, 无既有真源, 就此定点)

SOURCE_KINDS = ("file", "selection", "attachment", "url", "log", "message")
CONTENT_KINDS = ("text", "image", "video", "audio", "richdoc", "binary", "unknown")
MODALITIES = ("image", "audio", "video", "file")
STATES = ("native", "degraded", "opaque")


@dataclass(frozen=True)
class KindRoute:
    native_modality: Optional[str]          # 可尝试的原生模态; None=恒走文本
    fallback_quality: str                   # content | metadata | card | link
    extractor: Callable[..., str]          # 永远成功的文本出口
    on_native_fail: str                    # reuse_text | link_text | notice
    fetch: str = "none"                    # none | optional | required (URL 来源)


_BASE: Dict[str, KindRoute] = {
    "text":    KindRoute(None,    "content",  _text_body,    "reuse_text"),
    "richdoc": KindRoute("file",  "content",  _richdoc_body, "reuse_text"),
    "image":   KindRoute("image", "card",     _image_card,   "reuse_text"),
    "video":   KindRoute("video", "metadata", _video_card,  "reuse_text"),
    "audio":   KindRoute("audio", "metadata", _audio_card,   "reuse_text"),
    "binary":  KindRoute(None,    "card",     _binary_card,  "reuse_text"),
    "unknown": KindRoute(None,    "link",     _link_body,    "notice"),
}
_URL_OVERRIDE: Dict[str, KindRoute] = {
    "text":    KindRoute(None,    "content", _link_body, "link_text", fetch="optional"),
    "image":   KindRoute("image", "link", _link_body, "link_text", fetch="optional"),
    "video":   KindRoute("video", "link", _link_body, "link_text", fetch="optional"),
    "audio":   KindRoute("audio", "link", _link_body, "link_text", fetch="optional"),
    "richdoc": KindRoute("file",  "link", _link_body, "link_text", fetch="optional"),
    "binary":  KindRoute(None,    "link", _link_body, "link_text"),
}


def _build_contract() -> Dict[Tuple[str, str], KindRoute]:
    table: Dict[Tuple[str, str], KindRoute] = {}
    for source in SOURCE_KINDS:
        for content in CONTENT_KINDS:
            if source in ("log", "message"):        # 内部来源恒为文本语义
                table[(source, content)] = _BASE["text"]
            elif source == "url":
                table[(source, content)] = _URL_OVERRIDE.get(content, _BASE[content])
            else:
                table[(source, content)] = _BASE[content]
    return table


KIND_CONTRACT: Dict[Tuple[str, str], KindRoute] = _build_contract()
KIND_MODALITY = {k: r.native_modality for k, r in _BASE.items()}


@dataclass(frozen=True)
class ItemPlan:
    key: str            # dedup_key(item)
    source_kind: str
    content_kind: str
    state: str          # native | degraded | opaque
    transport: str      # inline | url | none
    reason: str


def classify_ref(item: Dict[str, Any]) -> Tuple[str, str]:
    """唯一分类点(纯识别, 不读模型): 返回 (source_kind, content_kind)。
    log/message 恒映射 text; url 走 classify_url; 其余复用 extract.classify。"""
    src = str(item.get("kind") or "file")
    if src in ("log", "message"):
        return src, "text"
    if src == "url" or item.get("url"):
        return "url", classify_url(str(item.get("url") or ""), str(item.get("content_type") or ""))
    path = str(item.get("stored_path") or item.get("path") or "")
    size = int(item.get("size") or 0)
    return src, classify(Path(path), str(item.get("mime") or ""), size)


def dedup_key(item: Dict[str, Any]) -> str:
    """去重键单一真源: 附件按 attachment_id, 文件按归一 path, URL 按归一 url。"""
    if item.get("attachment_id"):
        return f"att:{item['attachment_id']}"
    if item.get("url"):
        return f"url:{str(item['url']).rstrip('/').lower()}"
    return f"file:{str(item.get('path') or '').replace(chr(92), '/').lower()}"


def state_of(source_kind: str, content_kind: str, prof: Dict[str, Any],
             transport_ok: bool) -> str:
    """唯一状态函数(C9): link/card → opaque; content/metadata → degraded。"""
    route = KIND_CONTRACT[(source_kind, content_kind)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if cap and cap.native and transport_ok:
        return "native"
    if route.fallback_quality in ("content", "metadata"):
        return "degraded"
    return "opaque"


def _reason(route: KindRoute, cap: Any) -> str:
    if not route.native_modality:
        return "该类型无原生通道"
    return "模型未声明该输入模态" if not (cap and cap.native) else "载荷不可获取"


def _pick_transport(cap: Any) -> str:
    return "url" if "url" in cap.transport else "inline"


def plan_refs(items: Optional[List[Dict[str, Any]]], prof: Dict[str, Any]) -> List[ItemPlan]:
    """来源无关计划器(纯函数): native→占位/native part, 其余→文本块。"""
    plans: List[ItemPlan] = []
    for it in items or []:
        src, ck = classify_ref(it)
        route = KIND_CONTRACT[(src, ck)]
        cap = prof.get(route.native_modality) if route.native_modality else None
        base = ItemPlan(dedup_key(it), src, ck, "", "none", "")
        if cap and cap.native:
            plans.append(replace(base, state="native", transport=_pick_transport(cap)))
        else:
            plans.append(replace(base, state=state_of(src, ck, prof, False),
                                 reason=_reason(route, cap)))
    return plans


def aggregate_state(states: List[str]) -> str:
    """最差状态聚合(native < degraded < opaque), 供 [23] preflight 复用。"""
    for worst in ("opaque", "degraded", "native"):
        if worst in states:
            return worst
    return "native"


def ref_capability_map(prof: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """二维只读投影 {source_kind: {content_kind: state}}, 前端/23 只读索引。"""
    return {s: {c: state_of(s, c, prof, False) for c in CONTENT_KINDS}
            for s in SOURCE_KINDS}


def limits() -> Dict[str, int]:
    """上限单一真源(C8): max_refs 引既有 services/refs/limits.MAX_REFS(20),
    max_url_images 引既有 app.constants.MAX_REMOTE_IMAGES(4);
    max_urls 为本方案新增上限(单次引用 URL 条数), 无既有真源, 就此定点声明。
    MAX_REFS 延迟导入: refs.limits→agent 包初始化→react_loop→contract 会成环。"""
    from app.services.refs.limits import MAX_REFS
    return {"max_refs": MAX_REFS, "max_urls": _MAX_URLS,
            "max_url_images": MAX_REMOTE_IMAGES}


def suffix_kind() -> Dict[str, str]:
    """后缀→content_kind 词典单一真源(前端徽标分类消费, 禁止前端再复制后缀表)。"""
    return {**{s: "image" for s in IMAGE_SUFFIXES},
            **{s: "video" for s in VIDEO_SUFFIXES},
            **{s: "audio" for s in AUDIO_SUFFIXES},
            **{s: "richdoc" for s in RICH_SUFFIXES},
            **{s: "text" for s in TEXT_SUFFIXES}}


def kind_options() -> List[Dict[str, str]]:
    """抽屉筛选选项单一真源: value=content_kind, label=中文短名。"""
    labels = {"text": "文本", "image": "图片", "video": "视频", "audio": "音频",
              "richdoc": "富文档", "binary": "二进制", "unknown": "未知"}
    return [{"value": c, "label": labels[c]} for c in CONTENT_KINDS]
