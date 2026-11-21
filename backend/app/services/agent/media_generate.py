# -*- coding: utf-8 -*-
"""媒体生成回调实现(services 层) — 供 tool_executor 注入给 media 工具。

归属说明(为何在 agent 层而非 generation 层): 本模块是 tool_executor 注入给工具层的回调实现,
  消费方(tool_executor)在 services/agent, 故随用方放 agent 层; 真正的厂商 HTTP 出generation_client
  仍在 services/generation, 本模块只做"定位 provider/凭据 + 编排调用 + b64 落盘", 不另开生成出口 — 小欧-2026-11-20

编辑历史: 2026-11-20 小欧 新建: 按模型名定位 provider + 拿凭据 + 调 generation_client 统一出口,
  产出原始 url/b64 回给生图/生视频工具; 探测与业务共用 generate_* 同一 HTTP 出口。
编辑历史: 2026-11-20 小欧 b64 产物落盘: SenseNova U1.5 只返 2048² PNG 的 b64(约4MB)无公网URL,
  直接塞 LLM 回复会超消息大小; 本层(services, 可 import attachments)把 b64 落盘为会话 attachment,
  返回 attachment_id/file_path, 工具声明产物, 前端产物抽屉经 loadRawBlob 带 token 预览(零前端改动)。
编辑历史: 2026-11-20 小欧 图源归一: 实测 agnes-image-2.1-flash 与 sensenova-u1.5-lite 的 i2i image 参数接受标准 data URI;
  i2v reference 只接受公网 URL(data URI 被拒); _read_image_source 统一读字节, i2i 转 data URI, i2v 走 public_image 公网化。
编辑历史: 2026-11-20 小欧 本地图 i2v 公网化: 新增 _image_bytes 抽出图源读取(i2i/i2v 共用, DRY); invoke_generate 的 i2v 分支
  调 public_image.upload_image 把本地图临时公网化后送厂商 images; i2i 仍走 data URI(需求: 本地图也能做图生视频)。
编辑历史: 2026-11-20 小欧 命名整改: _image_bytes 返回(字节,mime)二元组名不符实, 改名 _read_image_source 且注解精确为
  Optional[Tuple[bytes,str]]; _provider_and_base 返回三元组漏 key 改 _provider_credentials; 局部变量 pair→image_data、
  vmode→endpoint_mode(端点是 text/reference, 与工具侧 t2v/i2v 区分)、ev→evidence(取证串); 另 rec→attachment_rec/saved_rec
  (附件记录, 消含糊缩写); 纯改名零行为变更。
编辑历史: 2026-11-20 小欧 按厂商文档(agnes-video-2.5/flash)补全视频全能力: invoke_generate 扩 first_frame/last_frame/audios/videos/
  seconds/size/aspect_ratio/seed 参数; mode 支持 t2v/i2v 别名与 text/keyframe/reference 直通; 图片类素材(images/first/last)统一公网化,
  audios/videos 为公网URL原样透传; 厂商实测新模式提交返回 queue_full(非参数错)证明参数结构正确 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 按厂商文档补全生图全能力: invoke_generate image 分支加 ratio/images(多图合成)并透传 provider/size,
  供 generation_client 按厂商方言翻译; 实测 agnes(sensenova) size 协议不同(档位 vs WIDTHxHEIGHT) — 小欧-2026-11-20
编辑历史: 2026-11-21 小欧 三堂会审整改: provider 定位改为 ai.model_ref 当前 provider 优先(同名模型跨 provider 时不再取字典序第一个,
  复用 model_service.get_current_ref/RESERVED_AI_KEYS 单源); 未找到 provider 属确定失败改 settled=True(原 False 让工具回"稍后重试");
  async 入口内的图源读文件/b64 落盘改 asyncio.to_thread(原同步阻塞事件循环); 产物 mime 改为按字节魔数嗅探
  (厂商只回 url/b64 不回 mime, 原按 kind 硬编码 png/mp4 会让 jpeg/webm 产物后缀撒谎) — 小欧-2026-11-21
"""
import asyncio
import base64
import os
import re
from typing import Any, Dict, Optional, Tuple

from app.config import get_config
from app.llm.adapters import get_provider_adapter
from app.logger import logger

# 图源 mime 映射从 media_constants 引入(三堂会审常量归位) — 小欧-2026-11-20
from app.services.agent.media_constants import IMAGE_MIME_BY_EXT
from app.services.generation.generation_client import (
    VIDEO_MODE_I2V,
    VIDEO_MODE_T2V,
    generate_image,
    generate_video,
)


def _read_image_source(src: str) -> Optional[Tuple[bytes, str]]:
    """读取图源 → (字节, mime); 仅本地路径/attachment_id/data URI 可读, 公网 URL 返回 None。
    i2i(转 data URI) 与 i2v(公网化) 共用此读取口, 避免两处重复解析 — 小欧-2026-11-20
    """
    if not src:
        return None
    lowered = src.lower()
    if lowered.startswith("data:"):
        # data:image/png;base64,XXXX → 拆出 mime 与 payload
        try:
            header, payload = src.split(",", 1)
            mime = header[5:].split(";", 1)[0] or "image/png"
            return base64.b64decode(payload), mime
        except (ValueError, base64.binascii.Error) as e:
            logger.warning(f"[media_generate] data URI 解析失败 err={e}")
            return None
    if lowered.startswith(("http://", "https://")):
        return None  # 公网 URL 由调用方原样处理
    path = ""
    if re.fullmatch(r"[0-9a-f]{32}", src):  # 32hex attachment_id → stored_path
        try:
            from app.attachments import attachment_service
            attachment_rec = attachment_service.get_attachment(src)
            if attachment_rec:
                path = str(attachment_rec.get("stored_path") or "")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[media_generate] 附件解析失败 id={src} err={e}")
    else:
        path = src
    if not path or not os.path.isfile(path):
        logger.warning(f"[media_generate] 图片源不可用: {src[:80]}")
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        return raw, IMAGE_MIME_BY_EXT.get(ext, "image/png")
    except OSError as e:
        logger.warning(f"[media_generate] 图片读取失败 path={path} err={e}")
        return None


def _resolve_image_source(src: str) -> str:
    """i2i 图源: 本地路径/attachment_id/data URI → data URI; 公网 URL 原样(厂商可直连)。
    实测 agnes-image-2.1-flash / sensenova-u1.5-lite 的 i2i image 参数接受标准 data URI — 小欧-2026-11-20
    """
    if not src:
        return src
    if src.lower().startswith(("http://", "https://")):
        return src
    image_data = _read_image_source(src)
    if image_data is None:
        return src  # 读不出则原样透传, 由厂商判定
    raw, mime = image_data
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


async def _publicize_image_source(src: str) -> str:
    """i2v 图源: 本地路径/attachment_id/data URI → 公网 URL(临时图床); 公网 URL 原样。
    i2v reference 的 images 只吃厂商可直连 GET 的公网 URL, data URI 被拒 — 小欧-2026-11-20
    """
    if not src:
        return src
    if src.lower().startswith(("http://", "https://")):
        return src
    image_data = await asyncio.to_thread(_read_image_source, src)
    if image_data is None:
        return src  # 读不出则原样透传, 厂商会报 source_unreachable
    raw, mime = image_data
    from app.services.generation.public_image import upload_image
    url = await upload_image(raw, mime)
    return url or src  # 公网化失败则原样透传, 交由厂商拒绝并记因


_MEDIA_MIME_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"\x1a\x45\xdf\xa3", "video/webm"),
)


def _sniff_media_mime(raw: bytes, kind: str) -> str:
    """按字节魔数判定产物 mime → 落盘后缀才对得上真实格式。

    厂商只回 url/b64, 不回报文 mime; 按 kind 硬编码 image/png|video/mp4 会把 jpeg/webm 产物
    落成 .png/.mp4(附件五分类按扩展名走, 预览与转码随之错)。认不出的按 kind 取默认 — 小欧-2026-11-21
    """
    head = raw[:16]
    for sig, mime in _MEDIA_MIME_SIGNATURES:
        if head.startswith(sig):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[4:8] == b"ftyp":
        return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
    return "image/png" if kind == "image" else "video/mp4"


def _save_b64_attachment(b64: str, session_id: str, kind: str, stem: str) -> Optional[Dict[str, str]]:
    """把生成产物 b64 落盘为附件 → {attachment_id, file_path, name} 或 None。
    走系统产出专用落盘口(不受会话存在性/配额/单文件上限约束), 后缀按字节真实格式由附件域映射;
    仅空 b64、解码不出字节或磁盘不可写才返回 None — 小欧-2026-11-21"""
    if not b64:
        return None
    try:
        from app.attachments import attachment_service
        # b64 可能缺 padding 且夹带换行, 补齐 padding + validate=False 忽略非字母表字符
        raw = base64.b64decode(b64 + "=" * (-len(b64) % 4), validate=False)
        if not raw:
            return None
        rec = attachment_service.save_generated_bytes(
            session_id or "", stem, raw, mime=_sniff_media_mime(raw, kind))
        return {
            "attachment_id": str(rec.get("id") or ""),
            "file_path": str(rec.get("stored_path") or ""),
            "name": str(rec.get("original_name") or ""),
        }
    except Exception as e:  # noqa: BLE001 — 落盘失败降级, 不打断对话
        logger.error(f"[media_generate] b64 落盘失败 session={session_id} err={e}")
        return None


def _provider_credentials(model: str) -> Tuple[Optional[str], str, str]:
    """按模型名取调用凭据 (provider, api_base, api_key)。

    定位顺序: 当前模型(ai.model_ref.provider)优先 —— 同一模型名可被多个 provider 声明,
    沿用 model_service 的当前 provider 单源, 避免拼接/鉴权落到字典序第一个 provider;
    未命中再遍历其余 provider。均未找到返回 (None, "", "")。
    """
    ai = get_config().get("ai") or {}
    if not isinstance(ai, dict):
        return None, "", ""
    from app.services.model.model_service import RESERVED_AI_KEYS, get_current_ref
    current = get_current_ref(ai).get("provider") or ""
    names = ([current] if current else []) + [
        name for name in ai
        if name not in RESERVED_AI_KEYS and not name.startswith("_")
    ]
    for name in dict.fromkeys(names):
        p = ai.get(name)
        if not isinstance(p, dict):
            continue
        models = p.get("models") or []
        if model in models:
            api_base = str(p.get("api_base") or "")
            api_key = os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or "")
            return name, api_base, api_key
    return None, "", ""


def _vendor_duration_ms(meta: Dict[str, Any]) -> int:
    """厂商侧任务耗时(毫秒): created_at→completed_at; 缺任一端返回 0 — 小欧-2026-11-21

    与工具墙钟 duration_ms 互补: 墙钟含排队提交+轮询粒度, 厂商耗时才是真出片时间。
    """
    try:
        start = int(meta.get("created_at") or 0)
        end = int(meta.get("completed_at") or 0)
    except (TypeError, ValueError):
        return 0
    return (end - start) * 1000 if start and end and end >= start else 0


async def invoke_generate(kind: str, model: str, prompt: str,
                          *, image: Optional[str] = None,
                          mode: Optional[str] = None,
                          images: Optional[list] = None,
                          return_base64: bool = False,
                          response_format: Optional[str] = None,
                          first_frame: Optional[str] = None,
                          last_frame: Optional[str] = None,
                          audios: Optional[list] = None,
                          videos: Optional[list] = None,
                          seconds: Optional[str] = None,
                          size: Optional[str] = None,
                          ratio: Optional[str] = None,
                          aspect_ratio: Optional[str] = None,
                          seed: Optional[int] = None,
                          timeout: Optional[float] = None,
                          session_id: Optional[str] = None) -> Dict[str, Any]:
    """生成回调主入口 → {ok, settled, url, b64, file_path, attachment_id, reason, meta, vendor_duration_ms}。

    kind=image → generate_image; kind=video → generate_video(全模式: text/keyframe/reference)。
    产物 url 直接回; 只有 b64(如 SenseNova)时经 session_id 落盘为 attachment, 回 file_path。
    meta = 厂商响应其余字段(剔 url/b64 本体), 工具据此拼规格摘要并落 other_data — 小欧-2026-11-21
    任何异常回 ok=False 不抛, 由工具收口。
    """
    provider, api_base, api_key = _provider_credentials(model)
    if not provider or not api_base:
        # 模型/provider 未配置属确定失败(换模型或改配置才有出路), 不能按未定让工具回"稍后重试"
        return {"ok": False, "settled": True, "reason": f"未找到模型 {model} 的 provider/api_base"}
    adapter = get_provider_adapter(provider)
    headers = adapter.static_headers(api_key)
    out: Dict[str, Any] = {}
    try:
        if kind == "image":
            # i2i 单图: 转 data URI(两 provider 实测接受), 公网 URL 原样; 多图合成参考图走公网化(sensenova 多图要公网URL)
            #   图源读文件是同步 IO, 交线程执行, 不阻塞事件循环
            src_image = await asyncio.to_thread(_resolve_image_source, image) if image else None
            src_images = [await _publicize_image_source(x) for x in images] if images else None
            kw = {"timeout": timeout} if timeout else {}
            ok, evidence, settled = await generate_image(
                api_base, headers, model, prompt, image=src_image, images=src_images,
                size=size, ratio=ratio, return_base64=return_base64,
                response_format=response_format, adapter=adapter, out=out, **kw)
        elif kind == "video":
            # 工具侧 mode 支持 t2v/i2v 别名与 text/keyframe/reference 直通 — 单一映射点
            alias = {"t2v": VIDEO_MODE_T2V, "i2v": VIDEO_MODE_I2V}
            endpoint_mode = alias.get(mode or "", mode or VIDEO_MODE_T2V)
            # 图片类素材须公网 URL(厂商直连 GET), 本地路径/attachment_id/data URI 经临时图床公网化
            # keyframe(first/last_frame) 与 reference(images) 都是图片, 统一公网化
            src_images = [await _publicize_image_source(x) for x in images] if images else None
            src_first = await _publicize_image_source(first_frame) if first_frame else None
            src_last = await _publicize_image_source(last_frame) if last_frame else None
            # audios/videos 已是公网 URL/对象(厂商要求直连 GET), 本地文件暂不公网化, 原样透传交由厂商判定
            # 工具 timeout = 视频总等待上限, 映射到 poll_timeout(轮询总时长); httpx 单请求超时用引擎默认。
            #   工具 schema 宣称 timeout 是"等待上限", 必须控制轮询而非仅单请求 — 小欧-2026-11-20
            kw = {"poll_timeout": float(timeout)} if timeout else {}
            ok, evidence, settled = await generate_video(
                api_base, headers, model, prompt, endpoint_mode,
                images=src_images, first_frame=src_first, last_frame=src_last,
                audios=audios, videos=videos, seconds=seconds, size=size,
                aspect_ratio=aspect_ratio, seed=seed, adapter=adapter, out=out, **kw)
        else:
            # 未知 kind 是调用方写错, 重试无出路 → 确定失败
            return {"ok": False, "settled": True, "reason": f"未知生成类型 {kind}"}
    except Exception as e:  # noqa: BLE001 — 生成异常回退, 不打断对话轮
        logger.warning(f"[media_generate] 生成异常 kind={kind} model={model} err={e}")
        return {"ok": False, "settled": False, "reason": f"生成异常: {type(e).__name__}: {e}"}
    url = str(out.get("url") or "")
    b64 = str(out.get("b64") or "")
    meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}
    result: Dict[str, Any] = {
        "ok": ok,
        "settled": settled,
        "url": url,
        "b64": b64,
        "file_path": "",
        "attachment_id": "",
        "reason": evidence,
        "meta": meta,
        "vendor_duration_ms": _vendor_duration_ms(meta),
    }
    # 只有 b64 无公网 URL(如 SenseNova U1.5 官方只返 2048² PNG b64) → 落盘为 attachment,
    # 工具据此声明产物, 前端产物抽屉经 loadRawBlob 带 token 预览, 不把 4MB data URI 塞进 LLM 回复
    if ok and not url and b64:
        # 落盘含写盘+登记(同步 IO), 交线程执行; mime 由附件侧按字节真实格式映射
        saved = await asyncio.to_thread(
            _save_b64_attachment, b64, session_id or "", kind, f"generated_{kind}")
        if saved:
            result.update(saved)
    return result
