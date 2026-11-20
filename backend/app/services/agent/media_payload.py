# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-08 小欧 新建: 媒体附件 → 请求 part 唯一构造点(视觉通道原内联逻辑迁入)
# 2026-11-08 小欧 增自适应选路: 实测支持外链→直传 URL; 超限→本机压缩再内联(替代直接丢弃)
# 2026-11-08 小欧 压缩保方向(EXIF Orientation 烧进像素); 外链准入改 is_global 单判(补 CGNAT) — 小欧-2026-11-08
# 2026-11-11 小欧 逻辑/方言分层: build_media_part → build_logical_part + to_wire_part + ensure_payload,
#   新增 _read_capped/_b64; 压缩/缓存/外链准入原样保留 — 小欧-2026-11-11
# 2026-11-11 小欧 增 URL 直传方言: build_url_part 按 content_kind 分派 video_url/audio_url;
#   to_wire_part 补 video/audio 外链 part(内联仍按原降级口径) — 小欧-2026-11-11
#
# 2026-11-14 商量 视频内联注记: 本地 video 默认回落文本卡。原因非配额限制, 而是方言边界——
#   OpenAI 兼容 chat 无视频内联 part, video_url 需厂商侧可直连 GET(私有本地文件无公网地址)。
#   待实现视频功能时按 provider 定制: provider 声明支持视频内联(如 Gemini inline_data video/mp4)
#   则在此产 inline part, 能力判定复用 probe_model_media 三态, 不做一刀切 — 商量-2026-11-14
#
# 2026-11-14 小欧 音频格式不猜: to_wire_part 按 mime 精确映射 wav/mp3(mpeg→mp3), 非白名单容器
#   返回失败由调用方回落文本卡, 消原"其它容器默认标 wav"误标 — 小欧-2026-11-14

# 2026-11-16 小欧 bug猎修: url_reject_reason 拦非规范点分 IP 字面量(整数/十六进制/八进制/
#   缩写点分/尾点变体此前全部放行, 实际指向本机/内网)

# 2026-11-18 opencode 修正: ①删 build_url_part —— 它产方言 part 却被 ensure_payload 当逻辑
#   part 返回, 调用方 to_wire_part 拿不到 modality, 外链媒体恒失败; URL 直传改由 ensure_payload
#   产出逻辑 part({modality,url}), 方言统一由 to_wire_part 单点产出 — opencode-2026-11-18
#   ②内联补齐响应 mime(fetch_bytes 返回值新增), 消远端音频恒降级/远端 JPEG 被标 image/png
#   ③删 build_logical_part 的 transport 死参数(函数体零使用) — opencode-2026-11-18

# 2026-11-18 opencode 富文档原生通道: ①to_wire_part 补 file 分支(OpenAI 兼容 chat 的
#   {type:file, file:{filename, file_data:data URI}}), richdoc/file 逻辑 part 的 modality
#   统一为 "file"(原样把 content_kind 当 modality, 与 to_wire_part 词表对不上);
#   ②文档内联上限单列 doc_inline_limit_bytes(media.doc_inline_limit_mb, 默认 8MB) —— 图片走
#   压缩后 2MB 口径, PDF 不能压缩, 沿用图片上限会让几乎所有真实文档落到降级;
#   ③容器不猜: 仅 PDF 产原生 file part(docx/xlsx/pptx 各家方言不一), 其余显式原因回落文本抽取
#   — opencode-2026-11-18

# 2026-11-18 opencode 链接图并入统一额度: 上限/压缩策略抽为 _image_data_uri 单点, 本地附件与
#   链接下载图共用 —— 原链接图内联不判额度不压缩, media.inline_limit_mb 对链接图形同虚设,
#   一张 10MB 网图会直接以 13MB base64 进请求体; ensure_payload 的 url 直传只保留
#   视频(方言唯一投递方式)与图片(实测证明厂商能抓外链时才由能力层选到这条),
#   转发开关关掉时图片回落下载内联而不是丢素材 — opencode-2026-11-18

# 2026-11-20 小欧 本地视频原生投递: 实测 mimo(opencli OpenAI兼容网关)接受 data:video/mp4;base64 作为 video_url 且能真看懂内容;
#   build_logical_part 的 video 分支改为本地字节→data URI 放 url(走 to_wire_part 已有 video_url 方言), 新增 video_inline_limit_mb(默认20MB) 与 file 档对齐, 修"声明支持视频却降级未发送"的缺陷
# 2026-11-20 小欧 音频独立内联上限: 新增 audio_inline_limit_mb(默认20MB), 音频分支不再沿用图片2MB口径(不能压缩, 几分钟mp3会全数降级未发送)
# 2026-11-20 小欧 视频发前转 H264: 模型对视频编码要求不一(nano-omni 只收 H264/HEVC/VP8/VP9, MJPG 等报400), 用 imageio-ffmpeg 自带 ffmpeg 把非标准编码转 H264 再投递(新模块 video_transcode, 转码结果按源缓存); 实测 214MB MJPG .mov 转码后 nano-omni 看懂内容
# 2026-11-20 小欧 三堂会审整改: 转码缓存落系统临时目录(原附件同级 .h264 无清理会磁盘泄漏); _ensure_video_h264 返回注解改 Tuple[str,bool]; 复用 _read_capped(path=) 消重复读取函数; 消死变量 transcoded

"""services.agent.media_payload — 媒体附件 → 请求 content part 的唯一构造点。

设计边界:
  1. 两级分层固定: build_logical_part/ensure_payload 只产**逻辑 part**(描述语义:
     modality/mime/data/url), to_wire_part 是唯一把它翻成方言 part 的出口 ——
     任一环节直接产出方言结构都会让下游拿不到 modality;
  2. 选路固定: 视频走 URL 直传(方言唯一投递方式); 图片默认下载后内联字节, 仅当实测证明
     厂商能抓外链(能力层给出的 transport 含 url)才直传地址; 音频/文档恒内联字节,
     超限压缩(仅图片)后仍超 → 一行文字说明;
  3. 失败一律返回 (None, 原因), 调用方退化文字, 不抛异常断轮;
  4. 压缩只为通过内联上限, 不改原文件, 参数取自 media 配置块;
  5. data URL 按「文件+上限+压缩参数」复用, 同一任务多轮不重复编码。
"""
import asyncio
import base64
import io
import ipaddress
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

from app.config import get_config
from app.logger import logger
from app.services.agent.video_transcode import (
    ensure_h264,  # 视频发前转 H264(顶层直引, 消透传函数) — 小欧-2026-11-20 三堂会审
)

_DATA_URL_MAX = 8
_data_url_cache: Dict[Tuple[str, str, int, int, int], str] = {}
_PRIVATE_HOSTS = {"localhost", "localhost.localdomain"}
# 原生 file part 的容器白名单: OpenAI 兼容 chat 的 file part 官方口径是 PDF; docx/xlsx/pptx
# 各家方言不一, 不猜容器, 显式回落文本抽取(richdoc 文本出口保真档 text_full) — opencode-2026-11-18
NATIVE_DOC_MIMES = frozenset({"application/pdf"})


def media_config() -> Dict[str, Any]:
    """media 配置块; 缺键走内置默认, 配置缺失不改变既有行为。"""
    cfg = get_config().get("media")
    return cfg if isinstance(cfg, dict) else {}


def _mb_to_bytes(mb: float) -> int:
    """MB(浮点) → 字节, 下限 1MB; 内联上限换算单点 — 小欧-2026-11-20 三堂会审(DRY)"""
    return max(1, int(mb)) * 1024 * 1024


def inline_limit_bytes() -> int:
    # 本机可调阈值(media.inline_limit_mb, 默认 2MB), 非外部协议上限; 单机自有资源可放宽。
    try:
        mb = float(media_config().get("inline_limit_mb") or 2)
    except (TypeError, ValueError):
        mb = 2.0
    return _mb_to_bytes(mb)


def doc_inline_limit_bytes() -> int:
    """文档内联上限(media.doc_inline_limit_mb, 默认 8MB)。

    与图片分开: 图片超限可压缩, 文档不能(重编码即破坏内容), 沿用 2MB 口径会让绝大多数
    真实 PDF 落到降级。base64 后体积约 ×1.34, 8MB 原文 → 约 10.7MB 请求体, 在主流厂商
    单请求体量之内。"""
    try:
        mb = float(media_config().get("doc_inline_limit_mb") or 8)
    except (TypeError, ValueError):
        mb = 8.0
    return _mb_to_bytes(mb)


def _default_media_inline_bytes() -> int:
    """音视频内联上限缺省值 = 单文件附件上限真源(attachment_service.MAX_FILE_BYTES)。
    不另造数值, 改附件上限时音视频自动跟随 — 小欧-2026-11-20"""
    from app.attachments.attachment_service import MAX_FILE_BYTES  # 延迟导入防循环
    return MAX_FILE_BYTES


def _media_inline_limit_bytes(key: str) -> int:
    """按配置项取音视频内联上限字节数; 未配置/非法时回落单文件附件上限真源。"""
    default = _default_media_inline_bytes()
    raw = media_config().get(key)
    if raw is None or raw == "":
        return default
    try:
        return _mb_to_bytes(float(raw))
    except (TypeError, ValueError):
        return default


def audio_inline_limit_bytes() -> int:
    """音频内联上限(media.audio_inline_limit_mb), 缺省=单文件附件上限。
    音频走 base64 input_audio 投递, 不能像图片那样压缩; 沿用图片 2MB 口径会让几分钟的
    mp3/wav 全数降级"未发送" — 小欧-2026-11-20"""
    return _media_inline_limit_bytes("audio_inline_limit_mb")


def video_inline_limit_bytes() -> int:
    """视频内联上限(media.video_inline_limit_mb), 缺省=单文件附件上限。
    视频走 data URI 的 video_url 投递(完整 base64), 体积远大于图片; 缺省跟随附件上限,
    避免图片 2MB 口径把可用视频全数拒绝 — 小欧-2026-11-20"""
    return _media_inline_limit_bytes("video_inline_limit_mb")


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


def _image_data_uri(raw: bytes, mime: str) -> Tuple[Optional[str], str]:
    """图片字节 → data URI: 超内联上限按配置压缩, 压完仍超退回原因。

    上限与压缩策略唯一落点 —— 本地附件与链接下载图共用, 否则 media.inline_limit_mb
    只对本地文件生效, 链接图能绕开额度把大图直接塞进请求体 — opencode-2026-11-18
    """
    limit = inline_limit_bytes()
    if len(raw) <= limit:
        return f"data:{mime or 'image/png'};base64,{base64.b64encode(raw).decode('ascii')}", ""
    if not bool(media_config().get("compress_enabled", True)):
        return None, f"超过 {limit // (1024 * 1024)}MB，且没开自动压缩"
    edge, quality = _compress_params()
    try:
        raw, mime = _compress(raw, edge, quality)
    except Exception as e:  # noqa: BLE001 — 图片解不开按解析失败退原因
        logger.warning(f"[media] 压缩失败 err={e}")
        return None, "图片无法解析"
    if len(raw) > limit:
        return None, f"压缩后仍超过 {limit // (1024 * 1024)}MB"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}", ""


async def _image_data_url(attachment: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """附件 → data URI; 超内联上限先压缩, 压完仍超则退回原因。"""
    edge, quality = _compress_params()
    limit = inline_limit_bytes()
    key = (str(attachment.get("stored_path") or ""), str(attachment.get("mime") or ""), limit, edge, quality)
    cached = _data_url_cache.get(key)
    if cached:
        return cached, ""

    def _work() -> Tuple[Optional[str], str]:
        with open(key[0], "rb") as fh:
            raw = fh.read()
        return _image_data_uri(raw, key[1])

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
        # 非规范点分形式的 IP 字面量(整数/十六进制/八进制/缩写点分/尾点)同样指向内网,
        # 必须拦: 逐段纯数字或 0x 十六进制段即判编码 IP, 不解析不翻案 — 小欧-2026-11-16
        stripped = host.rstrip(".")
        parts = stripped.split(".")
        if stripped.isdigit() or all(
                p.isdigit() or (p[:2].lower() == "0x" and all(c in "0123456789abcdef" for c in p[2:]))
                for p in parts if p):
            return "不接受内网/保留地址"
        return ""  # 域名放行(不解析)
    # is_global 一处覆盖回环/内网/链路本地/保留/CGNAT(100.64/10); 组播单独判(224/4 的 is_global 为真) — 小欧-2026-11-08
    if ip.is_multicast or not ip.is_global:
        return "不接受内网/保留地址"
    return ""


def _b64(raw: Optional[bytes]) -> str:
    return base64.b64encode(raw or b"").decode("ascii")


def sniff_mime(raw: Optional[bytes]) -> str:
    """字节魔数 → 容器 mime(仅媒体白名单); 判不出返回空串, 调用方自行决定口径。

    存在理由: 远端下载的响应头可能缺 content-type, 而内联 part 的容器格式
    (data:image/*;base64 / input_audio.format)必须准确, 猜错会把 JPEG 标成 PNG
    或把 m4a 标成 wav 交给厂商 —— 宁可显式失败也不误标。
    """
    head = (raw or b"")[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"ID3") or head[0:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return ""


async def _read_capped(attachment: Dict[str, Any],
                       limit: Optional[int] = None,
                       path: Optional[str] = None) -> Tuple[Optional[bytes], str]:
    """读字节(上限 limit, 缺省取图片内联上限); 超限/不可读返回 (None, 原因)。
    path 覆盖: 视频转码后读缓存文件时传入, 与读原附件共用本函数 — 小欧-2026-11-20"""
    if path is None:
        path = str(attachment.get("stored_path") or "")
    cap = limit or inline_limit_bytes()

    def _work() -> Tuple[Optional[bytes], str]:
        with open(path, "rb") as fh:
            raw = fh.read(cap + 1)
        if len(raw) > cap:
            return None, f"超过 {cap // (1024 * 1024)}MB"
        return raw, ""

    try:
        return await asyncio.to_thread(_work)
    except OSError as e:
        logger.warning(f"[media] 读文件失败 path={path} err={e}")
        return None, "文件不可读"


async def build_logical_part(kind: str, attachment: Dict[str, Any]
                             ) -> Tuple[Optional[Dict[str, Any]], str]:
    """本地附件 → 逻辑 part(只描述语义: modality/mime/data/url, 不描述方言)。"""
    if kind == "image":
        url, reason = await _image_data_url(attachment)
        return ({"modality": "image", "mime": attachment.get("mime") or "image/png",
                 "data": None, "url": url}, "") if url else (None, reason)
    if kind == "video":
        # 本地视频 → data URI 走 video_url 方言(chat 无独立视频内联 part, 但 mimo/nano-omni
        # 实测接受 data:video/mp4;base64)。模型对编码要求不一(nano-omni 只收 H264/HEVC/VP8/VP9,
        # MJPG/MP4V 会 400)——发前统一转 H264, 按模型定制的前提是有标准编码可投递 — 小欧-2026-11-20
        stored = str(attachment.get("stored_path") or "")
        play_path, _ = await asyncio.to_thread(ensure_h264, stored)
        limit = video_inline_limit_bytes()
        raw, reason = await _read_capped(attachment, limit, path=play_path)
        if raw is None:
            return None, reason or f"视频超过 {limit // (1024 * 1024)}MB"
        return {"modality": "video", "mime": "video/mp4", "data": None,
                "url": f"data:video/mp4;base64,{_b64(raw)}"}, ""
    if kind == "audio":
        # 音频用独立上限(默认20MB), 不再沿用图片2MB口径 — 小欧-2026-11-20
        raw, reason = await _read_capped(attachment, audio_inline_limit_bytes())
        return ({"modality": "audio", "mime": attachment.get("mime") or "",
                 "data": raw, "url": None}, "") if raw else (None, reason)
    if kind in ("richdoc", "file"):
        # 富文档/文件 → 文档模态: modality 必须是 "file"(to_wire_part 词表), 不能沿用 content_kind;
        #   filename 进 file part, 部分厂商按后缀判容器, 缺名会退化成无扩展名文档。
        raw, reason = await _read_capped(attachment, doc_inline_limit_bytes())
        name = str(attachment.get("original_name") or "") \
            or Path(str(attachment.get("stored_path") or "")).name
        return ({"modality": "file", "mime": attachment.get("mime") or "", "name": name,
                 "data": raw, "url": None}, "") if raw else (None, reason)
    return None, "该类型无原生通道"


def to_wire_part(logical: Dict[str, Any], dialect: str = "chat") -> Tuple[Optional[Dict[str, Any]], str]:
    """逻辑 part → 方言 part。chat 产出 OpenAI 兼容结构; responses 由适配器二次转换。
    video 无标准 chat part: 仅当 provider 适配器显式声明支持才产出, 否则显式原因。
    file(文档)按 NATIVE_DOC_MIMES 白名单产 file part, 容器不在白名单即显式回落文本抽取。"""
    modality, url = logical.get("modality"), logical.get("url")
    if modality == "image":
        if url:
            return {"type": "image_url", "image_url": {"url": url}}, ""
        raw = logical.get("data")
        if raw:
            mime = str(logical.get("mime") or "") or sniff_mime(raw) or "image/png"
            return {"type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{_b64(raw)}"}}, ""
        return None, "图片载荷为空"
    if modality == "video":
        if url:
            return {"type": "video_url", "video_url": {"url": url}}, ""
        # 本地视频已在 build_logical_part 转 data URI 走 url 分支投递(厂商侧 video_url);
        #   走到这里说明既无 url 也无可内联字节(远程视频未下载/超限), 只能回落说明 — 小欧-2026-11-20
        return None, "该传输方言不支持视频内联"
    if modality == "audio":
        if url:
            return {"type": "audio_url", "audio_url": {"url": url}}, ""
        mime = str(logical.get("mime") or "") or sniff_mime(logical.get("data"))
        sub = mime.rpartition("/")[2].lower()
        fmt = {"wav": "wav", "wave": "wav", "x-wav": "wav",
               "mpeg": "mp3", "mp3": "mp3"}.get(sub)
        if not fmt:
            # 不猜格式: 非 wav/mp3 容器显式回落, 防把 ogg/m4a 误标 wav 交给厂商
            return None, "不支持的音频容器(仅 wav/mp3 可原生投递)"
        return {"type": "input_audio",
                "input_audio": {"data": _b64(logical.get("data")), "format": fmt}}, ""
    if modality == "file":
        raw = logical.get("data")
        if not raw:
            return None, "文档载荷为空"
        mime = str(logical.get("mime") or "").split(";")[0].strip().lower() or sniff_mime(raw)
        if not mime:
            return None, "文档类型未知(缺少 mime)"
        if mime not in NATIVE_DOC_MIMES:
            # 不猜容器: docx/xlsx/pptx 各家方言不一, 误标 mime 等于把错误格式交给厂商
            return None, "该文档容器无原生 file part(仅 PDF)"
        return {"type": "file",
                "file": {"filename": str(logical.get("name") or "") or "document.pdf",
                         "file_data": f"data:{mime};base64,{_b64(raw)}"}}, ""
    return None, f"该模态无 {dialect} 方言实现"


async def ensure_payload(item: Dict[str, Any], transport: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """载荷可获取性: url 直传(图片/视频); inline 按 kind 取字节(链接图/音频需先下载)。

    两个运输方式都产**逻辑 part**(modality/mime/data/url), 方言由 to_wire_part 单点产出;
    仅媒体模态(image/audio/video)可达, text/richdoc 的 URL 走 attachment_wire 抽取路径。
    关掉 media.remote_url_passthrough 只停"把地址交给厂商": 图片改下载内联(不丢素材),
    视频本地字节已转 data URI 走 url 投递, 仅远程视频未下载时留一行说明 — 小欧-2026-11-20。"""
    url = str(item.get("url") or "")
    kind = str(item.get("content_kind") or "") or "image"
    if transport == "url":
        if kind not in ("image", "video"):
            # 音频/文档没有地址型 part: 转发地址除押注厂商抓取外别无收益
            return None, "该类型不走链接直传"
        if media_config().get("remote_url_passthrough", True):
            reason = url_reject_reason(url)
            if reason:
                return None, reason
            return {"modality": kind, "mime": "", "data": None, "url": url}, ""
        if kind == "video":
            # 视频在 chat 里没有内联 part, 关掉转发只剩一行说明
            return None, "配置里关闭了媒体链接转发"
        # 图片有内联退路: 关掉转发只表示"不把地址交给厂商", 不丢素材 → 落到下面下载内联
    if kind not in ("image", "audio", "video"):
        return None, "该类型无内联媒体载荷(文本/富文档走抽取路径)"
    from app.services.agent.remote_fetch import fetch_bytes  # 延迟导入: 仅 URL 内联需要
    raw, mime, reason = await fetch_bytes(url, kind)
    if not raw:
        return None, reason
    if kind == "image":
        mime = mime or sniff_mime(raw)
        # 链接图与本地图同一套上限/压缩策略, 否则内联额度对链接图形同虚设
        uri, why = await asyncio.to_thread(_image_data_uri, raw, mime)
        return ({"modality": "image", "mime": mime, "data": None, "url": uri}, "") if uri \
            else (None, why)
    # 响应头缺 content-type 时按字节魔数补齐容器格式, 不猜默认值(见 sniff_mime)
    return {"modality": kind, "mime": mime or sniff_mime(raw),
            "data": raw, "url": None}, ""
