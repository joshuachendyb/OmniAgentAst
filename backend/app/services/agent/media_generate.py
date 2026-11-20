# -*- coding: utf-8 -*-
"""媒体生成回调实现(services 层) — 供 tool_executor 注入给 media 工具。

编辑历史: 2026-11-20 小欧 新建: 按模型名定位 provider + 拿凭据 + 调 generation_client 统一出口,
  产出原始 url/b64 回给生图/生视频工具; 探测与业务共用 generate_* 同一 HTTP 出口(设计[15] Phase B)。
编辑历史: 2026-11-20 小欧 b64 产物落盘: SenseNova U1.5 只返 2048² PNG 的 b64(约4MB)无公网URL,
  直接塞 LLM 回复会超消息大小; 本层(services, 可 import attachments)把 b64 落盘为会话 attachment,
  返回 attachment_id/file_path, 工具声明产物, 前端产物抽屉经 loadRawBlob 带 token 预览(零前端改动)。
编辑历史: 2026-11-20 小欧 图源归一: 实测 agnes-image-2.1-flash 与 sensenova-u1.5-lite 的 i2i/i2v image 参数都接受标准
  data URI(仅 i2i; i2v reference 只吃公网 URL, data URI 被拒); _image_bytes 统一读字节, i2i 转 data URI, i2v 走 public_image 公网化。
编辑历史: 2026-11-20 小欧 本地图 i2v 公网化: 新增 _image_bytes 抽出图源读取(i2i/i2v 共用, DRY); invoke_generate 的 i2v 分支
  调 public_image.upload_image 把本地图临时公网化后送厂商 images; i2i 仍走 data URI(需求: 本地图也能做图生视频)。
"""
import base64
import os
from typing import Any, Dict, Optional

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


def _image_bytes(src: str) -> Optional[tuple]:
    """图片源 → (字节, mime); 仅本地路径/attachment_id/data URI 可读, 公网 URL 返回 None。
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
    import re
    path = ""
    if re.fullmatch(r"[0-9a-f]{32}", src):  # 32hex attachment_id → stored_path
        try:
            from app.attachments import attachment_service
            rec = attachment_service.get_attachment(src)
            if rec:
                path = str(rec.get("stored_path") or "")
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
    pair = _image_bytes(src)
    if pair is None:
        return src  # 读不出则原样透传, 由厂商判定
    raw, mime = pair
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


async def _publicize_image_source(src: str) -> str:
    """i2v 图源: 本地路径/attachment_id/data URI → 公网 URL(临时图床); 公网 URL 原样。
    i2v reference 的 images 只吃厂商可直连 GET 的公网 URL, data URI 被拒 — 小欧-2026-11-20
    """
    if not src:
        return src
    if src.lower().startswith(("http://", "https://")):
        return src
    pair = _image_bytes(src)
    if pair is None:
        return src  # 读不出则原样透传, 厂商会报 source_unreachable
    raw, mime = pair
    from app.services.generation.public_image import upload_image
    url = await upload_image(raw, mime)
    return url or src  # 公网化失败则原样透传, 交由厂商拒绝并记因


def _save_b64_attachment(b64: str, session_id: str, mime: str, stem: str) -> Optional[Dict[str, str]]:
    """把生成产物 b64 落盘为会话 attachment → {attachment_id, file_path, name} 或 None。
    仅 services 层可调(import attachments), 失败只告警不抛 — 小欧-2026-11-20"""
    if not b64 or not session_id:
        return None
    try:
        import uuid

        from app.attachments import attachment_service
        raw = base64.b64decode(b64)
        ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime or "jpg" in mime else "bin")
        name = f"{stem}-{uuid.uuid4().hex[:8]}.{ext}"
        rec = attachment_service.save_bytes(session_id, name, raw, mime=mime or f"image/{ext}")
        return {"attachment_id": str(rec.get("id") or ""), "file_path": str(rec.get("stored_path") or ""), "name": name}
    except Exception as e:  # noqa: BLE001 — 落盘失败降级, 不打断对话
        logger.warning(f"[media_generate] b64 落盘失败 session={session_id} err={e}")
        return None


def _provider_and_base(model: str):
    """根据模型名定位 (provider, api_base, api_key); 遍历 config.ai 各 provider 的 models 列表。
    未找到返回 (None, "", "")。"""
    ai = get_config().get("ai") or {}
    if not isinstance(ai, dict):
        return None, "", ""
    for name, p in ai.items():
        if not isinstance(p, dict) or name.startswith("_") or name in {"model_ref"}:
            continue
        models = p.get("models") or []
        if model in models:
            api_base = str(p.get("api_base") or "")
            api_key = os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or "")
            return name, api_base, api_key
    return None, "", ""


async def invoke_generate(kind: str, model: str, prompt: str,
                          *, image: Optional[str] = None,
                          mode: Optional[str] = None,
                          images: Optional[list] = None,
                          timeout: Optional[float] = None,
                          session_id: Optional[str] = None) -> Dict[str, Any]:
    """生成回调主入口 → {ok, settled, url, b64, file_path, attachment_id, reason}。

    kind=image → generate_image; kind=video → generate_video(默认 t2v)。
    产物 url 直接回; 只有 b64(如 SenseNova)时经 session_id 落盘为 attachment, 回 file_path。
    任何异常回 ok=False 不抛, 由工具收口。
    """
    provider, api_base, api_key = _provider_and_base(model)
    if not provider or not api_base:
        return {"ok": False, "settled": False, "reason": f"未找到模型 {model} 的 provider/api_base"}
    headers = get_provider_adapter(provider).static_headers(api_key)
    out: Dict[str, Any] = {}
    try:
        if kind == "image":
            # i2i: 图源转 data URI(两 provider 实测接受), 公网 URL 原样
            src_image = _resolve_image_source(image) if image else None
            kw = {"timeout": timeout} if timeout else {}
            ok, ev, settled = await generate_image(api_base, headers, model, prompt,
                                                   image=src_image, out=out, **kw)
        elif kind == "video":
            # 工具侧 mode 是 t2v/i2v, generation 端点要 text/reference — 在此映射(单一转换点)
            vmode = VIDEO_MODE_I2V if mode == "i2v" else VIDEO_MODE_T2V
            # i2v: 图源须公网 URL(厂商直连 GET), 本地图经临时图床公网化; t2v 无图源
            src_images = None
            if vmode == VIDEO_MODE_I2V and images:
                src_images = [await _publicize_image_source(x) for x in images]
            kw = {"timeout": timeout} if timeout else {}
            ok, ev, settled = await generate_video(api_base, headers, model, prompt, vmode,
                                                   images=src_images, out=out, **kw)
        else:
            return {"ok": False, "settled": False, "reason": f"未知生成类型 {kind}"}
    except Exception as e:  # noqa: BLE001 — 生成异常回退, 不打断对话轮
        logger.warning(f"[media_generate] 生成异常 kind={kind} model={model} err={e}")
        return {"ok": False, "settled": False, "reason": f"生成异常: {type(e).__name__}: {e}"}
    url = str(out.get("url") or "")
    b64 = str(out.get("b64") or "")
    result: Dict[str, Any] = {
        "ok": ok,
        "settled": settled,
        "url": url,
        "b64": b64,
        "file_path": "",
        "attachment_id": "",
        "reason": ev,
    }
    # 只有 b64 无公网 URL(如 SenseNova U1.5 官方只返 2048² PNG b64) → 落盘为 attachment,
    # 工具据此声明产物, 前端产物抽屉经 loadRawBlob 带 token 预览, 不把 4MB data URI 塞进 LLM 回复
    if ok and not url and b64 and session_id:
        mime = "image/png" if kind == "image" else "video/mp4"
        saved = _save_b64_attachment(b64, session_id, mime, f"generated_{kind}")
        if saved:
            result.update(saved)
    return result
