# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-24 商量 - 新增 MCP tools/call 公用传输层: 把 search_web 与 fetch_webpage 各自手写的
#   "组JSON-RPC请求→流式限体读取→SSE取末帧→error信封校验"收敛到一处, 两侧不再重复实现;
#   同时补上抓取链缺失的响应体上限与代理透传 — 商量-2026-11-24
"""
MCP tools/call 传输层

调用方只关心"拿到 JSON-RPC 帧", 传输细节(浏览器UA/限体读取/SSE帧序/error信封)统一在此处理:
- 流式读取并按 SEARCH_WEB_MCP_MAX_BYTES 硬截断, 超大响应记上游响应坏
- JSON 体与 SSE 流同一入口; SSE 取最后一个携带 result/error 的帧(首帧常是进度通知)
- HTTP 200 带 JSON-RPC error 信封时抛 NetError, 不让错误被当成"空结果"吞掉
"""
import json
from typing import Optional

from app.tools.network.http_client_sdk import create_http_client
from app.tools.network.net_backend import NetError
from app.tools.tool_constants import (
    ERR_NET_UPSTREAM_BROKEN,
    SEARCH_WEB_MCP_MAX_BYTES,
    TOOL_BROWSER_UA,
)

_ACCEPT = "application/json, text/event-stream"


class McpFrameMissing(Exception):
    """响应里没有任何可解析的 JSON 帧(上游协议坏, 不是空结果)"""


def _pick_frame(raw: str) -> dict:
    """从 JSON 体或 SSE 流里取结果帧; 两者都无有效帧时抛 McpFrameMissing"""
    body = raw.lstrip()
    if body.startswith("{"):
        try:
            frame = json.loads(body)
        except json.JSONDecodeError as exc:
            raise McpFrameMissing(f"JSON体解析失败: {exc}") from exc
        if isinstance(frame, dict):
            return frame
        raise McpFrameMissing("JSON体非对象")

    data = None
    fallback = None
    for line in raw.split("\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        try:
            frame = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        fallback = frame
        if isinstance(frame, dict) and ("result" in frame or "error" in frame):
            data = frame
    picked = data if data is not None else fallback
    if not isinstance(picked, dict):
        raise McpFrameMissing(f"SSE无有效JSON帧({len(raw)}字节)")
    return picked


async def call_tool(
    url: str,
    tool_name: str,
    arguments: dict,
    timeout_sec: float,
    proxy: Optional[str] = None,
    extra_headers: Optional[dict] = None,
) -> dict:
    """调用 MCP tools/call 并返回 JSON-RPC 帧

    httpx 家族与 NetError 直接上抛(交调用方按链底座口径分类); McpFrameMissing 表示无可解析帧。
    """
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    headers = {"Accept": _ACCEPT, "User-Agent": TOOL_BROWSER_UA}
    headers.update(extra_headers or {})
    async with create_http_client(timeout_sec=timeout_sec, proxy=proxy) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes():
                total += len(chunk)
                if total > SEARCH_WEB_MCP_MAX_BYTES:
                    raise NetError(ERR_NET_UPSTREAM_BROKEN, f"响应超过{SEARCH_WEB_MCP_MAX_BYTES}字节")
                chunks.append(chunk)
            raw = b"".join(chunks).decode("utf-8", errors="replace")

    frame = _pick_frame(raw)
    rpc_error = frame.get("error")
    if isinstance(rpc_error, dict):
        raise NetError(ERR_NET_UPSTREAM_BROKEN, f"JSON-RPC error: {rpc_error.get('message', '')}")
    return frame


def result_text(frame: dict) -> str:
    """取 result.content 里全部 text 段拼接(部分 MCP 结果分成多段)"""
    content = (frame.get("result") or {}).get("content") or []
    return "\n".join(str(c.get("text", "")) for c in content if c.get("type") == "text")


def result_structured(frame: dict) -> dict:
    """取 result.structuredContent(结构化结果优先的引擎用)"""
    return (frame.get("result") or {}).get("structuredContent") or {}
