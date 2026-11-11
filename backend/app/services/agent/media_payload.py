# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-08 小欧 新建: 媒体附件 → 请求 part 唯一构造点(视觉通道原内联逻辑迁入)
# 2026-11-08 小欧 增自适应选路: 实测支持外链→直传 URL; 超限→本机压缩再内联(替代直接丢弃)
# 2026-11-08 小欧 压缩保方向(EXIF Orientation 烧进像素); 外链准入改 is_global 单判(补 CGNAT) — 小欧-2026-11-08
# 2026-11-11 小欧 逻辑/方言分层: build_media_part → build_logical_part + to_wire_part + ensure_payload,
#   新增 _read_capped/_b64; 压缩/缓存/外链准入原样保留 — 小欧-2026-11-11

"""services.agent.media_payload — 媒体附件 → 请求 content part 的唯一构造点。

设计边界:
  1. 选路固定三级: 公网 URL 直传(调用方按实测能力决定) → 压缩/原样内联 → 一行文字说明;
  2. 失败一律返回 (None, 原因), 调用方退化文字, 不抛异常断轮;
  3. 压缩只为通过内联上限, 不改原文件, 参数取自 media 配置块;
  4. data URL 按「文件+上限+压缩参数」复用, 同一任务多轮不重复编码。
"""
import asyncio
import base64
import io
import ipaddress
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

from app.config import get_config
from app.logger import logger

_DATA_URL_MAX = 8
_data_url_cache: Dict[Tuple[str, str, int, int, int], str] = {}
_PRIVATE_HOSTS = {"localhost", "localhost.localdomain"}


def media_config() -> Dict[str, Any]:
    """media 配置块; 缺键走内置默认, 配置缺失不改变既有行为。"""
    cfg = get_config().get("media")
    return cfg if isinstance(cfg, dict) else {}


def inline_limit_bytes() -> int:
    try:
        mb = float(media_config().get("inline_limit_mb") or 2)
    except (TypeError, ValueError):
        mb = 2.0
    return max(1, int(mb)) * 1024 * 1024


def _compress_params() -> Tuple[int, int]:
    cfg = media_config()
    try:
        edge = int(cfg.get("compress_max_edge") or 2048)
    except (TypeError, ValueError):
        edge = 2048
    try:
        quality = int(cfg.get("compress_jpeg_quality") or 85)
    except (TypeError, ValueError):
        quality = 85
    return max(256, edge), min(95, max(1, quality))


def _compress(raw: bytes, edge: int, quality: int) -> Tuple[bytes, str]:
    """缩图重编码: 有 alpha 走 PNG, 其余走 JPEG(照片压缩比高得多)。"""
    from PIL import Image, ImageOps  # 延迟导入: 仅压缩路径需要 — 小欧-2026-11-08

    with Image.open(io.BytesIO(raw)) as img:
        # 竖拍手机的 Orientation 只写在 EXIF, 重编码会丢整个 EXIF 段 →
        #   先把方向烧进像素再编码, 否则发出去的照片躺倒 — 小欧-2026-11-08
        img = ImageOps.exif_transpose(img)
        keep_alpha = img.mode in ("RGBA", "LA", "P")
        img.thumbnail((edge, edge))
        buf = io.BytesIO()
        if keep_alpha:
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue(), "image/png"
        img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"


async def _image_data_url(attachment: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """附件 → data URI; 超内联上限先压缩, 压完仍超则退回原因。"""
    edge, quality = _compress_params()
    limit = inline_limit_bytes()
    key = (str(attachment.get("stored_path") or ""), str(attachment.get("mime") or ""), limit, edge, quality)
    cached = _data_url_cache.get(key)
    if cached:
        return cached, ""
    compress_on = bool(media_config().get("compress_enabled", True))

    def _work() -> Tuple[Optional[str], str]:
        with open(key[0], "rb") as fh:
            raw = fh.read()
        mime = key[1] or "image/png"
        if len(raw) > limit:
            if not compress_on:
                return None, f"超过 {limit // (1024 * 1024)}MB，且没开自动压缩"
            try:
                raw, mime = _compress(raw, edge, quality)
            except Exception as e:
                logger.warning(f"[media] 压缩失败 path={key[0]} err={e}")
                return None, "图片无法解析"
            if len(raw) > limit:
                return None, f"压缩后仍超过 {limit // (1024 * 1024)}MB"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", ""

    try:
        url, reason = await asyncio.to_thread(_work)
    except OSError as e:
        logger.warning(f"[media] 读文件失败 path={key[0]} err={e}")
        return None, "文件不可读"
    if url:
        if len(_data_url_cache) >= _DATA_URL_MAX:
            _data_url_cache.pop(next(iter(_data_url_cache)), None)  # 最旧淘汰
        _data_url_cache[key] = url
    return url, reason


def url_reject_reason(url: str) -> str:
    """外链准入: 只收 http/https 公网地址, 字面量排除本机/内网/保留地址。

    不做 DNS 解析与可达性校验: 真不可达由厂商如实报错, 不为此增加一次网络往返。
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "链接格式不合法"
    if parts.scheme not in ("http", "https"):
        return "只支持 http/https 链接"
    host = (parts.hostname or "").strip().lower()
    if not host:
        return "链接缺少主机名"
    if host in _PRIVATE_HOSTS:
        return "不接受本机地址"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return ""  # 域名放行(不解析)
    # is_global 一处覆盖回环/内网/链路本地/保留/CGNAT(100.64/10); 组播单独判(224/4 的 is_global 为真) — 小欧-2026-11-08
    if ip.is_multicast or not ip.is_global:
        return "不接受内网/保留地址"
    return ""


def build_url_part(url: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """公网图片地址 → image_url part(零字节搬运); 不合法返回 (None, 原因)。"""
    if not media_config().get("remote_url_passthrough", True):
        return None, "配置里关闭了图片链接转发"
    reason = url_reject_reason(url)
    if reason:
        return None, reason
    return {"type": "image_url", "image_url": {"url": url}}, ""


def _b64(raw: Optional[bytes]) -> str:
    return base64.b64encode(raw or b"").decode("ascii")


async def _read_capped(attachment: Dict[str, Any]) -> Tuple[Optional[bytes], str]:
    """读附件字节(上限 inline_limit_bytes); 超限/不可读返回 (None, 原因)。"""
    path = str(attachment.get("stored_path") or "")
    limit = inline_limit_bytes()

    def _work() -> Tuple[Optional[bytes], str]:
        with open(path, "rb") as fh:
            raw = fh.read(limit + 1)
        if len(raw) > limit:
            return None, f"超过 {limit // (1024 * 1024)}MB"
        return raw, ""

    try:
        return await asyncio.to_thread(_work)
    except OSError as e:
        logger.warning(f"[media] 读文件失败 path={path} err={e}")
        return None, "文件不可读"


async def build_logical_part(kind: str, attachment: Dict[str, Any],
                             transport: str = "inline") -> Tuple[Optional[Dict[str, Any]], str]:
    """本地附件 → 逻辑 part(只描述语义: modality/mime/data/url, 不描述方言)。"""
    if kind == "image":
        url, reason = await _image_data_url(attachment)
        return ({"modality": "image", "mime": attachment.get("mime") or "image/png",
                 "data": None, "url": url}, "") if url else (None, reason)
    if kind in ("video", "audio", "richdoc", "file"):
        raw, reason = await _read_capped(attachment)
        return ({"modality": kind, "mime": attachment.get("mime") or "",
                 "data": raw, "url": None}, "") if raw else (None, reason)
    return None, "该类型无原生通道"


def to_wire_part(logical: Dict[str, Any], dialect: str = "chat") -> Tuple[Optional[Dict[str, Any]], str]:
    """逻辑 part → 方言 part。chat 产出 OpenAI 兼容结构; responses 由适配器二次转换。
    video 无标准 chat part: 仅当 provider 适配器显式声明支持才产出, 否则显式原因。"""
    modality, url = logical.get("modality"), logical.get("url")
    if modality == "image":
        if url:
            return {"type": "image_url", "image_url": {"url": url}}, ""
        raw = logical.get("data")
        if raw:
            mime = str(logical.get("mime") or "image/png")
            return {"type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{_b64(raw)}"}}, ""
        return None, "图片载荷为空"
    if modality == "video" and dialect == "chat":
        return None, "该传输方言不支持视频"
    if modality == "audio":
        mime = str(logical.get("mime") or "")
        fmt = mime.rpartition("/")[2] if mime.rpartition("/")[2] in ("wav", "mp3") else "wav"
        return {"type": "input_audio",
                "input_audio": {"data": _b64(logical.get("data")), "format": fmt}}, ""
    return None, f"该模态无 {dialect} 方言实现"


async def ensure_payload(item: Dict[str, Any], transport: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """载荷可获取性: url 直传; inline 需字节时按 route.fetch 调 remote_fetch。
    仅媒体模态(image/audio/video)产出逻辑 part; text/richdoc 的 URL 内联走抽取路径。"""
    if transport == "url":
        return build_url_part(str(item.get("url") or ""))
    kind = str(item.get("content_kind") or "")
    if kind not in ("image", "audio", "video"):
        return None, "该类型无内联媒体载荷(文本/富文档走抽取路径)"
    from app.services.agent.remote_fetch import fetch_bytes     # 延迟导入: 仅 URL 内联需要
    raw, reason = await fetch_bytes(str(item.get("url") or ""), kind)
    return ({"modality": kind, "mime": "", "data": raw, "url": None}, "") \
        if raw else (None, reason)
