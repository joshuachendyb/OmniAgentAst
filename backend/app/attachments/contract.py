# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 附件能力协商契约(二维 KIND_CONTRACT / KindRoute / ItemPlan /
#   classify_ref / dedup_key / state_of / plan_refs / aggregate_state / ref_capability_map /
#   limits / kind_options), 零 IO 零配置, 仅引用 extract 词典与具名出口 — 小欧-2026-11-11

# 2026-11-11 小欧 三堂会审整改: 增 suffix_kind() 后缀→content_kind 词典下发出口,
#   消前端 useRefCapabilityMap 复制后缀表的双真源漂移 — 小欧-2026-11-11

# 2026-11-12 小欧 修正 state_of 两处错判: ①text 路由(native_modality=None,
#   fallback_quality=content)误判 degraded, 实为全文注入, 判 native 档;
#   ②_URL_OVERRIDE["text"] 的 fallback_quality 由 content 改 link(实际出口
#   _link_body 只注入链接地址), 判 opaque 档 — 判定对齐运行时实际, 纠错非兼容改动

# 2026-11-14 小欧 - 修: limits() 下发 max_image_bytes/max_file_bytes(引 attachment_service 配额常量),
#   上限唯一真源在后端, 前端预检/文案改读此口径, 消前端写死 10MB/20MB 双真源 — 小欧-2026-11-14

# 2026-11-12 小欧 删 state_of 的 transport_ok 死参数: plan_refs 仅在非 native 分支调用,
#   该参数在判定式中恒不起作用; ref_capability_map 投影传 False 致有原生模态路由
#   (image/video/audio/richdoc)在矩阵永远显不出 native, 与 plan_refs 只看 cap.native
#   的运行时口径分叉(视觉模型图片格错显元信息注入)。native 判定统一只看画像声明 — 小欧-2026-11-12


# 2026-11-14 小欧 状态模型正交化(quality/delivery/reason) + 槽位注册表单源:
#   state 一枚举背"能力可达/投递方式/保真档"三义, 凭 state 装配必然漏投(file/selection 文本被判
#   native 却无占位 → 首发正文整条消失)。拆为 quality(保真, 不驱动装配)与 delivery(装配动作),
#   可写原生槽来源只由 ref_slots.SLOT_WRITERS.keys() 提供, _plan_of 纳入 has_slot 判定;
#   删 state_of/aggregate_state/ref_capability_map/STATES 与死字段 on_native_fail/transport;
#   fallback_quality 与 quality 同域(text_full|meta_only|link_only) 直取, 不再二次翻译 — 小欧-2026-11-14


# 2026-11-14 小欧 三堂会审整改(14条违规修复): ①ItemPlan 收敛为 (source_kind, content_kind,
#   quality) 最小面, 删死字段 key/reason 与 delivery(投递由 QUALITY_TO_DELIVERY 单表派生);
#   ②删 _reason/reason 死链路, _plan_of 直返 quality 单值; ③删 KIND_MODALITY/QUALITIES/
#   DELIVERIES 死导出与 dedup_key 死函数(全仓零消费); ④内部来源 ("log","message") 收敛为
#   _INTERNAL_TEXT_SOURCES 单常量; ⑤URL 路由 fetch 语义化: 文本抓取标 "text", 媒体内联
#   由 ensure_payload 自理不再标 optional, 消 attachment_wire 双判据 — 小欧-2026-11-14
#
# 2026-11-14 小欧 三堂会审整改(第2批): extract 私名出口转公开(text_body/link_body/
#   image_card/video_card/audio_card/binary_card/richdoc_body/*_from_bytes), 消契约跨模块
#   消费私有名; _plan_of 收敛为 quality 单值返回, 投递动作由 QUALITY_TO_DELIVERY 单表派生,
#   ItemPlan 删 key/delivery/reason 三死字段, 内部来源收敛 _INTERNAL_TEXT_SOURCES — 小欧-2026-11-14


"""attachments.contract — 能力协商契约(纯函数, 零 IO 零配置)。

单一契约表 KIND_CONTRACT[(source_kind, content_kind)] → KindRoute:
类型×来源 → 原生模态/降级质量/文本出口/失败回退。前后端与守门测试共用其投影。
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.attachments.extract import (
    AUDIO_SUFFIXES,
    IMAGE_SUFFIXES,
    RICH_SUFFIXES,
    TEXT_SUFFIXES,
    VIDEO_SUFFIXES,
    audio_card,
    binary_card,
    image_card,
    link_body,
    richdoc_body,
    text_body,
    video_card,
    classify,
    classify_url,
    scan_text_urls,
)
from app.constants import MAX_REMOTE_IMAGES
from app.ref_slots import SLOT_WRITERS

# 对外重导出词典与识别函数(契约消费方禁止再去 extract 复制一份)
__all__ = [
    "KIND_CONTRACT", "KindRoute", "ItemPlan", "SOURCE_KINDS",
    "CONTENT_KINDS", "MODALITIES", "QUALITY_TO_DELIVERY",
    "classify_ref", "quality_of", "plan_refs", "ref_quality_map",
    "limits", "kind_options", "suffix_kind",
    "AUDIO_SUFFIXES", "IMAGE_SUFFIXES", "RICH_SUFFIXES", "TEXT_SUFFIXES", "VIDEO_SUFFIXES",
    "classify_url", "scan_text_urls",
]

_MAX_URLS = 8   # 单次引用 URL 条数上限(本方案新增, 无既有真源, 就此定点)

SOURCE_KINDS = ("file", "selection", "attachment", "url", "log", "message")
CONTENT_KINDS = ("text", "image", "video", "audio", "richdoc", "binary", "unknown")
MODALITIES = ("image", "audio", "video", "file")
# 质量四值(保真结果); 投递动作由 QUALITY_TO_DELIVERY 单表派生, 不另设枚举双真源。
# fallback_quality 与 quality 同域(text_full | meta_only | link_only), 直取不翻译;
#   解析失败已在 resolver 层 dropped, 计划器只处理可用条目 — 小欧-2026-11-14
QUALITY_TO_DELIVERY = {
    "native": "slot", "text_full": "text",
    "meta_only": "text", "link_only": "text",
}


@dataclass(frozen=True)
class KindRoute:
    native_modality: Optional[str]          # 可尝试的原生模态; None=恒走文本
    fallback_quality: str                   # text_full | meta_only | link_only (与 quality 同域)
    extractor: Callable[..., str]          # 永远成功的文本出口
    fetch: str = "none"                    # none | optional | required (URL 来源)


_BASE: Dict[str, KindRoute] = {
    "text":    KindRoute(None,    "text_full", text_body),
    "richdoc": KindRoute("file",  "text_full", richdoc_body),
    "image":   KindRoute("image", "meta_only", image_card),
    "video":   KindRoute("video", "meta_only", video_card),
    "audio":   KindRoute("audio", "meta_only", audio_card),
    "binary":  KindRoute(None,    "meta_only", binary_card),
    "unknown": KindRoute(None,    "link_only", link_body),
}
# URL 路由 fetch 语义: "text"=文本抓取进正文(_expand_url 走 _fetch_extract_text);
#   "none"=不做 wire 层抓取(媒体内联载荷由 ensure_payload 按 transport 自理) — 小欧-2026-11-14
_URL_OVERRIDE: Dict[str, KindRoute] = {
    "text":    KindRoute(None,    "link_only", link_body, fetch="text"),
    "image":   KindRoute("image", "link_only", link_body),
    "video":   KindRoute("video", "link_only", link_body),
    "audio":   KindRoute("audio", "link_only", link_body),
    "richdoc": KindRoute("file",  "link_only", link_body, fetch="text"),
    "binary":  KindRoute(None,    "link_only", link_body),
}


_INTERNAL_TEXT_SOURCES = ("log", "message")   # 内部来源恒为文本语义


def _build_contract() -> Dict[Tuple[str, str], KindRoute]:
    table: Dict[Tuple[str, str], KindRoute] = {}
    for source in SOURCE_KINDS:
        for content in CONTENT_KINDS:
            if source in _INTERNAL_TEXT_SOURCES:
                table[(source, content)] = _BASE["text"]
            elif source == "url":
                table[(source, content)] = _URL_OVERRIDE.get(content, _BASE[content])
            else:
                table[(source, content)] = _BASE[content]
    return table


KIND_CONTRACT: Dict[Tuple[str, str], KindRoute] = _build_contract()


@dataclass(frozen=True)
class ItemPlan:
    source_kind: str
    content_kind: str
    quality: str        # native | text_full | meta_only | link_only


def classify_ref(item: Dict[str, Any]) -> Tuple[str, str]:
    """唯一分类点(纯识别, 不读模型): 返回 (source_kind, content_kind)。
    log/message 恒映射 text; url 走 classify_url; 其余复用 extract.classify。"""
    src = str(item.get("kind") or "file")
    if src in _INTERNAL_TEXT_SOURCES:
        return src, "text"
    if src == "url" or item.get("url"):
        return "url", classify_url(str(item.get("url") or ""), str(item.get("content_type") or ""))
    path = str(item.get("stored_path") or item.get("path") or "")
    size = int(item.get("size") or 0)
    return src, classify(Path(path), str(item.get("mime") or ""), size)


def _plan_of(source_kind: str, content_kind: str,
             prof: Dict[str, Any]) -> str:
    """quality 唯一判定: 计划器与矩阵投影共用, 禁止第二处派生。

    关键: 来源能否写原生槽(SLOT_WRITERS) 参与判定 —— 模型声明支持但来源无槽
    (file/selection 的 image 等) 不得判 native, 否则装配层无处可写。"""
    route = KIND_CONTRACT[(source_kind, content_kind)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if source_kind in SLOT_WRITERS and cap and cap.native:
        return "native"
    # fallback_quality 与 quality 同域直取: 缺键即契约漂移, 立即 KeyError 暴露, 不用默认值掩盖
    return route.fallback_quality


def quality_of(source_kind: str, content_kind: str, prof: Dict[str, Any]) -> str:
    """二维质量投影单值(矩阵/前端只读): 与 plan_refs 同源(均经 _plan_of)。"""
    return _plan_of(source_kind, content_kind, prof)


def plan_refs(items: Optional[List[Dict[str, Any]]], prof: Dict[str, Any]) -> List[ItemPlan]:
    """来源无关计划器(纯函数): 投递动作 = QUALITY_TO_DELIVERY[quality], 装配层单表派生。"""
    return [ItemPlan(src, ck, _plan_of(src, ck, prof))
            for src, ck in (classify_ref(it) for it in items or [])]


def ref_quality_map(prof: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """二维只读投影 {source_kind: {content_kind: quality}}, 前端徽标/矩阵只读索引。"""
    return {s: {c: quality_of(s, c, prof) for c in CONTENT_KINDS}
            for s in SOURCE_KINDS}


def limits() -> Dict[str, int]:
    """上限单一真源(C8): max_refs 引既有 services/refs/limits.MAX_REFS(20),
    max_url_images 引既有 app.constants.MAX_REMOTE_IMAGES(4);
    max_image_bytes/max_file_bytes 引 attachment_service 配额常量(上传分档口径);
    max_urls 为本方案新增上限(单次引用 URL 条数), 无既有真源, 就此定点声明。
    MAX_REFS 延迟导入: refs.limits→agent 包初始化→react_loop→contract 会成环。"""
    from app.services.refs.limits import MAX_REFS
    from app.attachments.attachment_service import MAX_FILE_BYTES, MAX_IMAGE_BYTES
    return {"max_refs": MAX_REFS, "max_urls": _MAX_URLS,
            "max_url_images": MAX_REMOTE_IMAGES,
            "max_image_bytes": MAX_IMAGE_BYTES, "max_file_bytes": MAX_FILE_BYTES}


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
