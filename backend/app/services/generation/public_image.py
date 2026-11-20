# -*- coding: utf-8 -*-
"""本地图片公网化(services/generation) — 把本地图字节上传到临时图床拿到公网直链。

归属说明(为何也在 generation 层): 本模块是 i2v 生成的前置辅助——为生成端点准备可参考的公网图,
  与 generation_client(生成端点出口)同属"生图生视频链路", 消费方是 media_generate 回调。
  generation 包现含两类 HTTP: ①generation_client=生成端点唯一出口(/images/generations、/videos);
  ②本模块=图床上传端点(i2v 参考图公网化), 二者端点不同、职责分离 — 小欧-2026-11-20 三堂会审

背景: 生视频 i2v(reference 模式)的 images 只吃公网 URL 字符串, 厂商要能直连 GET,
  本地路径/attachment_id/data URI 都不行(实测 data URI 被拒)。本模块把本地图临时公网化,
  供 i2v 参考图用; 生图 i2i 仍走 data URI(厂商接受), 两条路不混。
图床协议约束: multipart 字段名固定 files[], 响应取 files[0].url(uguu.se 契约)。换端点须兼容
  该请求/响应结构, 否则公网化失败; 端点与代理均可配置(media.public_image_upload_url / public_image_proxy)。
编辑历史: 2026-11-20 小欧 新建: uguu.se 图床(实测上传返回 d.uguu.se/h.uguu.se 公网直链, GET 真实 PNG);
  代理三级回退(环境代理→OmniVPN 本地 7890/7891→直连), 因为生产服务进程无代理环境变量而国外图床直连不通,
  本机 mihomo 常驻 7890; 任何失败返回空串由调用方降级, 不抛异常断轮。
编辑历史: 2026-11-20 小欧 配置化: 图床端点/代理改读 media.public_image_upload_url / public_image_proxy,
  默认值提模块常量作单一真源(settings_registry 引用), 本机 VPN(7890)为默认代理; 代理候选按"配置→环境→本地端口→直连"优先级去重回退。
编辑历史: 2026-11-20 小欧 三堂会审命名整改: _ext_of(mime→后缀)名含糊, 改名 _mime_to_extension; 局部变量 out→candidates
  (代理候选列表)、data→upload_result(上传响应 JSON), 消含糊命名; 纯改名零行为变更。
"""
import hashlib
import os
from typing import Any, Dict, Tuple

import httpx

from app.config import get_config

# 图床端点默认值单一真源在 app.constants(三堂会审常量归位): settings_registry 注册项与此处运行期兜底同源。
from app.constants import PUBLIC_IMAGE_UPLOAD_URL as DEFAULT_UPLOAD_ENDPOINT
from app.logger import logger

# 以下为本模块内部协议/运行参数(非跨模块共享), 随用方留在业务模块 — 小欧-2026-11-20 三堂会审
_UPLOAD_FIELD = "files[]"  # uguu.se multipart 字段名, 协议固定
_LOCAL_FALLBACK_PROXIES = ("http://127.0.0.1:7890", "http://127.0.0.1:7891")  # 未配置时的本机端口兜底
_UPLOAD_TIMEOUT = 40.0
# 同一张图(按字节摘要)短期内复用公网 URL, 避免重复上传; i2v 生成就几分钟, 时效足够。
_CACHE: Dict[str, str] = {}
_CACHE_MAX = 128


def _media_config() -> Dict[str, Any]:
    """media 配置块; 缺键走模块默认, 配置缺失不改变既有行为 — 小欧-2026-11-20。"""
    cfg = get_config().get("media")
    return cfg if isinstance(cfg, dict) else {}


def _proxy_candidates() -> Tuple[str, ...]:
    """代理候选, 按优先级去重: 配置首选 → 环境变量 → 本机端口兜底 → 直连(空串)。

    配置 media.public_image_proxy 非空时置顶(尊重用户显式指定的跨界出口); 其后保留环境变量
    与本机 mihomo 默认端口, 任一环节失败可回退, 末位直连兜底 — 小欧-2026-11-20。
    """
    cfg = _media_config()
    candidates: list = []

    def add(value: Any) -> None:
        p = str(value or "").strip()
        if p and p not in candidates:
            candidates.append(p)

    add(cfg.get("public_image_proxy"))
    add(os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"))
    for p in _LOCAL_FALLBACK_PROXIES:
        add(p)
    candidates.append("")  # 直连兜底
    return tuple(candidates)


def _mime_to_extension(mime: str) -> str:
    """mime 类型 → 文件后缀, 图床按后缀判类型。"""
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
    name = f"{stem}.{_mime_to_extension(mime)}"
    endpoint = str(_media_config().get("public_image_upload_url") or "").strip() or DEFAULT_UPLOAD_ENDPOINT
    last_err = ""
    for proxy in _proxy_candidates():
        try:
            # trust_env=False + 显式 proxy: 环境代理已在候选里, 避免 httpx 重复叠加; 空串=直连
            async with httpx.AsyncClient(proxy=proxy or None, timeout=_UPLOAD_TIMEOUT,
                                         follow_redirects=True, trust_env=False) as client:
                resp = await client.post(
                    endpoint,
                    files={_UPLOAD_FIELD: (name, raw, mime or "image/png")},
                )
            if resp.status_code == 200:
                upload_result = resp.json()
                files = upload_result.get("files") if isinstance(upload_result, dict) else None
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
