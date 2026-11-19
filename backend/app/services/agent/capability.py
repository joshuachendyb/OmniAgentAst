# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 模型输入能力画像(声明即首选, 实测仅标注/解锁 url 运输),
#   profile_of/profile/supports_image_input 薄投影, 零 IO — 小欧-2026-11-11

# 2026-11-18 opencode 文档模态按声明开启(与图片/音视频同口径): 声明 file 即原生 file part,
#   未声明降级为文本全文注入; 探测只作取证/展示(图片外链门见下条) — opencode-2026-11-18
# 2026-11-20 小欧 视频 transport 加 inline: 本地视频字节转 data URI 走 video_url(media_payload 已实现), mimo 实测能解析; 原只有 url 导致本地视频被误判无原生通道降级"未发送"
# 2026-11-20 小欧 三堂会审整改: docstring 与 _TRANSPORT 注释同步为"视频 url+inline 两种方言都可达", 消除与改后代码的矛盾

# 2026-11-18 opencode 运输方式归方言固有能力(_TRANSPORT), 实测只在一处开门: 图片外链。
#   其余模态(音频/文档内联、视频地址)是方言决定的事实, 不需要探测;(旧「实测外链可用才转发
#   图片地址」过期后会让厂商抓不到素材且请求不报错 —— 链接图默认下载后内联, 有实测证明才转发)
#   — opencode-2026-11-18

"""services.agent.capability — 模型输入能力画像(纯函数, 零 IO)。

声明模态即首选请求模式: input_modalities 含 m → native=True。
运输方式由方言固有能力(_TRANSPORT)决定: chat 方言里图片/音频/文档可内联字节; 视频两种
方言都可达(url 公网直传 / inline 本地字节转 data URI 走 video_url)。唯一例外是图片外链 ——
厂商是否真去抓公网地址无法从声明推断, 故 media.accept.image ∈ {url, both} 才把 url 加进
图片运输集合, 其余情况链接图下载后内联。
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
    transport: FrozenSet[str]     # {"inline"} / {"url"} / frozenset()
    source: str                   # declared | measured | none (仅展示标注)


_MODALITIES = ("image", "audio", "video", "file")
_EMPTY = frozenset()
# 运输方式 = 方言固有能力, 不是探测结论: 内联没有任何厂商前置条件, 天然的默认;
#   视频 url=公网链接直传, inline=本地字节转 data URI 走 video_url(两种都可达, 见下)。
_TRANSPORT: Dict[str, FrozenSet[str]] = {
    "image": frozenset({"inline"}),
    "audio": frozenset({"inline"}),
    # 视频两种方言都可达: url=公网链接直传; inline=本地字节转 data URI 走 video_url(mimo 等实测支持,
    # 见 media_payload.build_logical_part video 分支) — 小欧-2026-11-20
    "video": frozenset({"url", "inline"}),
    "file": frozenset({"inline"}),
}
# 实测开门白名单(唯一): 厂商会不会去抓图片外链, 声明里没有这项能力位, 只能实测证明 ——
#   accept.image 落在 url/both 才允许图片地址直传; 未探测/只收内联/多处失败一律下载后内联。
_IMAGE_URL_ACCEPT = frozenset({"url", "both"})


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
        if m not in declared:
            caps[m] = NativeCap(False, _EMPTY, "none")
            continue
        measured = str(accept.get(m) or "").strip().lower()
        transport = _TRANSPORT[m]
        if m == "image" and measured in _IMAGE_URL_ACCEPT:
            transport = transport | frozenset({"url"})
        # source 只表达"有没有实测记录", 供设置页标注
        caps[m] = NativeCap(True, transport, "measured" if measured else "declared")
    return caps


def profile(llm_model: Any) -> Dict[str, NativeCap]:
    """薄投影: llm_model 对象 → profile_of; 供计划器/展开期按当前模型取画像。"""
    return profile_of(getattr(llm_model, "provider", "") or "",
                      getattr(llm_model, "model", "") or "")


def supports_image_input(llm_model: Any) -> bool:
    """兼容性薄投影(唯一导出): 语义=profile["image"].native, 不再自行判定。"""
    return profile(llm_model)["image"].native
