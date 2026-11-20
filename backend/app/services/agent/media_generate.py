# -*- coding: utf-8 -*-
"""媒体生成回调实现(services 层) — 供 tool_executor 注入给 media 工具。

编辑历史: 2026-11-20 小欧 新建: 按模型名定位 provider + 拿凭据 + 调 generation_client 统一出口,
  产出原始 url/b64 回给生图/生视频工具; 探测与业务共用 generate_* 同一 HTTP 出口(设计[15] Phase B)。
"""
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
                          timeout: Optional[float] = None) -> Dict[str, Any]:
    """生成回调主入口 → {ok, settled, url, b64, reason}。

    kind=image → generate_image; kind=video → generate_video(默认 t2v)。
    产物原始 url/b64 经 out 出口取回(未截断)。任何异常回 ok=False 不抛, 由工具收口。
    """
    provider, api_base, api_key = _provider_and_base(model)
    if not provider or not api_base:
        return {"ok": False, "settled": False, "reason": f"未找到模型 {model} 的 provider/api_base"}
    headers = get_provider_adapter(provider).static_headers(api_key)
    out: Dict[str, Any] = {}
    try:
        if kind == "image":
            kw = {"timeout": timeout} if timeout else {}
            ok, ev, settled = await generate_image(api_base, headers, model, prompt,
                                                   image=image, out=out, **kw)
        elif kind == "video":
            # 工具侧 mode 是 t2v/i2v, generation 端点要 text/reference — 在此映射(单一转换点)
            vmode = VIDEO_MODE_I2V if mode == "i2v" else VIDEO_MODE_T2V
            kw = {"timeout": timeout} if timeout else {}
            ok, ev, settled = await generate_video(api_base, headers, model, prompt, vmode,
                                                   images=images, out=out, **kw)
        else:
            return {"ok": False, "settled": False, "reason": f"未知生成类型 {kind}"}
    except Exception as e:  # noqa: BLE001 — 生成异常回退, 不打断对话轮
        logger.warning(f"[media_generate] 生成异常 kind={kind} model={model} err={e}")
        return {"ok": False, "settled": False, "reason": f"生成异常: {type(e).__name__}: {e}"}
    return {
        "ok": ok,
        "settled": settled,
        "url": str(out.get("url") or ""),
        "b64": str(out.get("b64") or ""),
        "reason": ev,
    }
