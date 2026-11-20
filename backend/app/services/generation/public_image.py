# -*- coding: utf-8 -*-
"""本地图片公网化(services/generation) — 把本地图字节上传到临时图床拿到公网直链。

背景: 生视频 i2v(reference 模式)的 images 只吃公网 URL 字符串, 厂商要能直连 GET,
  本地路径/attachment_id/data URI 都不行(实测 data URI 被拒)。本模块把本地图临时公网化,
  供 i2v 参考图用; 生图 i2i 仍走 data URI(厂商接受), 两条路不混。
编辑历史: 2026-11-20 小欧 新建: uguu.se 图床(实测上传返回 d.uguu.se/h.uguu.se 公网直链, GET 真实 PNG);
  代理三级回退(环境代理→OmniVPN 本地 7890/7891→直连), 因为生产服务进程无代理环境变量而国外图床直连不通,
  本机 mihomo 常驻 7890; 任何失败返回空串由调用方降级, 不抛异常断轮。
"""
import hashlib
import os
from typing import Dict, Tuple

import httpx

from app.logger import logger

# 图床上传端点(单一真源)。uguu.se 实测可用: 返回 files[0].url 公网 PNG 直链。
_UPLOAD_ENDPOINT = "https://uguu.se/upload.php"
_UPLOAD_FIELD = "files[]"
# 代理回退候选: None=直连兜底; 环境代理在 _proxy_candidates 里优先取(避免重复)。
_LOCAL_PROXIES = ("http://127.0.0.1:7890", "http://127.0.0.1:7891")
_UPLOAD_TIMEOUT = 40.0
# 同一张图(按字节摘要)短期内复用公网 URL, 避免重复上传; i2v 生成就几分钟, 时效足够。
_CACHE: Dict[str, str] = {}
_CACHE_MAX = 128


def _proxy_candidates() -> Tuple[str, ...]:
    """代理候选: 环境代理(若有)优先, 再 OmniVPN 本地, 最后直连(None 用空串表示)。"""
    out = []
    env_proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
                 or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "")
    if env_proxy:
        out.append(env_proxy)
    out.extend(_LOCAL_PROXIES)
    out.append("")  # 直连兜底
    return tuple(out)


def _ext_of(mime: str) -> str:
    """mime → 文件后缀, 图床按后缀判类型。"""
    return {
        "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
        "image/gif": "gif", "image/bmp": "bmp",
    }.get((mime or "").lower(), "png")


async def upload_image(raw: bytes, mime: str, stem: str = "image") -> str:
    """本地图字节 → 公网直链; 任何失败返回空串(调用方降级), 不抛异常 — 小欧-2026-11-20。"""
    if not raw:
        return ""
    digest = hashlib.sha256(raw).hexdigest()
    cached = _CACHE.get(digest)
    if cached:
        logger.info(f"[public_image] 命中缓存 url={cached[:100]}")
        return cached
    name = f"{stem}.{_ext_of(mime)}"
    last_err = ""
    for proxy in _proxy_candidates():
        try:
            # trust_env=False + 显式 proxy: 环境代理已在候选里, 避免 httpx 重复叠加; 空串=直连
            async with httpx.AsyncClient(proxy=proxy or None, timeout=_UPLOAD_TIMEOUT,
                                         follow_redirects=True, trust_env=False) as client:
                resp = await client.post(
                    _UPLOAD_ENDPOINT,
                    files={_UPLOAD_FIELD: (name, raw, mime or "image/png")},
                )
            if resp.status_code == 200:
                data = resp.json()
                files = data.get("files") if isinstance(data, dict) else None
                url = str(files[0].get("url") or "") if isinstance(files, list) and files else ""
                if url.startswith("http"):
                    if len(_CACHE) >= _CACHE_MAX:
                        _CACHE.clear()
                    _CACHE[digest] = url
                    logger.info(f"[public_image] 公网化成功 proxy={proxy or '直连'} url={url[:100]}")
                    return url
            last_err = f"http_{resp.status_code}: {resp.text[:120]}"
        except Exception as e:  # noqa: BLE001 — 网络/JSON 异常逐个代理尝试
            last_err = f"{type(e).__name__}: {str(e)[:100]}"
    logger.warning(f"[public_image] 公网化失败(全部代理) stem={stem} last_err={last_err}")
    return ""
