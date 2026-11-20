# -*- coding: utf-8 -*-
"""媒体生成回调实现(services 层) — 供 tool_executor 注入给 media 工具。

编辑历史: 2026-11-20 小欧 新建: 按模型名定位 provider + 拿凭据 + 调 generation_client 统一出口,
  产出原始 url/b64 回给生图/生视频工具; 探测与业务共用 generate_* 同一 HTTP 出口(设计[15] Phase B)。
编辑历史: 2026-11-20 小欧 b64 产物落盘: SenseNova U1.5 只返 2048² PNG 的 b64(约4MB)无公网URL,
  直接塞 LLM 回复会超消息大小; 本层(services, 可 import attachments)把 b64 落盘为会话 attachment,
  返回 attachment_id/file_path, 工具声明产物, 前端产物抽屉经 loadRawBlob 带 token 预览(零前端改动)。
编辑历史: 2026-11-20 小欧 图源归一: 实测 agnes-image-2.1-flash 与 sensenova-u1.5-lite 的 i2i/i2v image 参数都接受标准
  data URI; _resolve_image_source 把本地路径/attachment_id 读字节转 data URI(公网URL原样), 打通本地图片编辑(无需公网图床)。
"""
import base64
import os
from typing import Any, Dict, Optional

from app.config import get_config
from app.llm.adapters import get_provider_adapter
from app.logger import logger
from app.services.generation.generation_client import (
    VIDEO_MODE_I2V,
    VIDEO_MODE_T2V,
    generate_image,
    generate_video,
)


def _resolve_image_source(src: str) -> str:
    """图片源归一: 本地路径/attachment_id → data URI(厂商可直连解析); 公网 URL/已是 data URI 原样返回。
    实测 agnes-image-2.1-flash 与 sensenova-u1.5-lite 的 i2i image 参数均接受标准 data URI — 小欧-2026-11-20
    """
    if not src:
        return src
    lowered = src.lower()
    if lowered.startswith(("data:", "http://", "https://")):
        return src
    import base64
    import re
    path = ""
    # 32hex attachment_id → 取 stored_path
    if re.fullmatch(r"[0-9a-f]{32}", src):
        try:
            from app.attachments import attachment_service
            rec = attachment_service.get_attachment(src)
            if rec:
                path = str(rec.get("stored_path") or "")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[media_generate] 附件解析失败 id={src} err={e}")
    else:
        path = src  # 直接当本地路径
    if not path or not os.path.isfile(path):
        logger.warning(f"[media_generate] 图片源不可用, 原样透传: {src[:80]}")
        return src
    try:
        raw = open(path, "rb").read()
        # mime 按后缀, 默认 png
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    except OSError as e:
        logger.warning(f"[media_generate] 图片读取失败 path={path} err={e}")
        return src


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
    # 图源归一: 本地路径/attachment_id → data URI(实测两 provider 的 i2i/i2v 都接受)
    src_image = _resolve_image_source(image) if image else None
    src_images = [_resolve_image_source(x) for x in images] if images else None
    try:
        if kind == "image":
            kw = {"timeout": timeout} if timeout else {}
            ok, ev, settled = await generate_image(api_base, headers, model, prompt,
                                                   image=src_image, out=out, **kw)
        elif kind == "video":
            # 工具侧 mode 是 t2v/i2v, generation 端点要 text/reference — 在此映射(单一转换点)
            vmode = VIDEO_MODE_I2V if mode == "i2v" else VIDEO_MODE_T2V
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
