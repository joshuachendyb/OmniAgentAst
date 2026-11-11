# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: URL 下载唯一出网口(四闸门: 协议/逐跳重判/DNS 后拒私网/超时限额) — 小欧-2026-11-11
# 2026-11-11 小欧 补错误追踪日志: 各失败路径原先静默返回, 排障无迹可循;
#   增 logger.warning 留痕 + [cap-metric] fetch_fail 埋点(P5 指标) — 小欧-2026-11-11

"""services.agent.remote_fetch — URL 下载唯一出网口。

只为"模型支持内联、不支持外链"的 URL 服务。安全四闸门:
只收 http/https(复用 media_payload.url_reject_reason) / 重定向≤3 跳逐跳重判 /
解析后拒私网回环保留地址(防 DNS 指向内网) / 超时 10s + 体积上限。
失败返回 (None, 原因), 不抛异常断轮。
"""
import asyncio
import ipaddress
import socket
from typing import Optional, Tuple
from urllib.parse import urlsplit

import httpx

from app.attachments.attachment_service import MAX_FILE_BYTES, MAX_IMAGE_BYTES
from app.attachments.observability import metric
from app.logger import logger
from app.services.agent.media_payload import url_reject_reason

_TIMEOUT = 10
_MAX_HOPS = 3


async def _host_reject_reason(host: str) -> str:
    """DNS 解析后逐 IP 判定: 拒私网/回环/保留(字面量判定拦不住 DNS 重指向)。
    getaddrinfo 是同步阻塞调用, 必须 to_thread 下放, 严禁在事件循环内直调。"""
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
    except OSError:
        return "域名无法解析"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_multicast or not ip.is_global:
            return "不接受内网/保留地址"
    return ""


def _fetch_fail(url: str, kind: str, reason: str) -> Tuple[Optional[bytes], str]:
    """失败出口单点: WARNING 留痕(排障) + fetch_fail 埋点(P5 指标), 不抛异常断轮。"""
    logger.warning("[remote_fetch] 下载失败 url=%s kind=%s reason=%s", url, kind, reason)
    metric("fetch_fail", "url", kind or "unknown", reason=reason)
    return None, reason


async def fetch_bytes(url: str, kind: str = "") -> Tuple[Optional[bytes], str]:
    """URL → (字节, ""); 失败 (None, 原因), 不抛异常断轮。
    上限按目标 kind: 图片 MAX_IMAGE_BYTES, 其余 MAX_FILE_BYTES。"""
    reason = url_reject_reason(url)
    if reason:
        return _fetch_fail(url, kind, reason)
    reason = await _host_reject_reason(urlsplit(url).hostname or "")
    if reason:
        return _fetch_fail(url, kind, reason)
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_FILE_BYTES
    hops = 0
    current = url
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=_TIMEOUT) as client:
            while hops < _MAX_HOPS:
                resp = await client.get(current)
                if resp.is_redirect:
                    current = str(resp.headers.get("location") or "")
                    reason = url_reject_reason(current) or await _host_reject_reason(urlsplit(current).hostname or "")
                    if reason:
                        return _fetch_fail(url, kind, f"重定向被拒: {reason}")
                    hops += 1
                    continue
                if resp.status_code >= 400:
                    return _fetch_fail(url, kind, f"下载失败: HTTP {resp.status_code}")
                if len(resp.content) > limit:
                    return _fetch_fail(url, kind, "超过下载体积上限")
                return resp.content, ""
    except (httpx.HTTPError, OSError) as e:
        return _fetch_fail(url, kind, f"下载异常: {type(e).__name__}")
    return _fetch_fail(url, kind, "重定向次数超限")
