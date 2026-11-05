# -*- coding: utf-8 -*-
"""streamer.py — 下游事件流 → 上游 SSE 帧（端点与判别由驱动挂钩给出）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00

要点: 帧粒度按下游给几帧发几帧; 会话过滤由驱动 event_session 判定; 延迟提交由
gateway._stream_text 决定; 事件情态归驱动 event_class, 本文件只认归一值。

编辑历史:
  2026-11-05 删死代码 sse_comment; HEARTBEAT_S→WAIT_SLICE_S(实为等待切片, 不发 ping) -- 小欧
  2026-11-05 15 s 心跳未接线, 仍挂账 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
"""
from __future__ import annotations

import json

WAIT_SLICE_S = 15         # 等待事件的最长切片; ": ping" 心跳仍未接线 — 小欧 2026-11-05
FIRST_FRAME_S = 60        # 60 s 无任何 delta → 提交 504 — 小欧 2026-11-05
SILENT_S = 180            # 已出字后长时间无新帧 — 小欧 2026-11-05


def sse(data):
    """一帧 SSE: data 行 + 空行收尾（宿主只解析 data 行）。— 小欧 2026-11-05"""
    return "data: %s\n\n" % json.dumps(data, ensure_ascii=False)


def first_frame():
    """首帧: delta.role=assistant。— 小欧 2026-11-05"""
    return sse({"choices": [{"index": 0, "delta": {"role": "assistant"},
                             "finish_reason": None}]})


def delta_frame(content="", reasoning="", tool_calls=None):
    """正文 / 思考 / 工具调用 → 三种 delta 形状。— 小欧 2026-11-05"""
    delta = {}
    if content:
        delta["content"] = content
    if reasoning:
        delta["reasoning_content"] = reasoning
    if tool_calls is not None:
        delta["tool_calls"] = [{"index": i, "id": c["id"],
                                "type": c.get("type", "function"),
                                "function": {"name": c["function"]["name"],
                                             "arguments": c["function"]["arguments"]}}
                               for i, c in enumerate(tool_calls)]
    return sse({"choices": [{"index": 0, "delta": delta, "finish_reason": None}]})


def final_frame(model, usage, finish_reason="stop"):
    """末帧: 空 delta + finish_reason + usage + [DONE]。— 小欧 2026-11-05"""
    body = {"id": "", "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]}
    if usage is not None:
        body["usage"] = usage
    return sse(body) + "data: [DONE]\n\n"


async def iter_events(client, session_id, drv):
    """订阅下游事件端点, 按会话过滤后逐条 yield; 订阅失败 yield http_error 不抛。— 小欧 2026-11-05"""
    async with client.stream("GET", drv.path_events()) as resp:
        if resp.status_code != 200:
            yield {"kind": "http_error", "status": resp.status_code}
            return
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            try:
                payload = json.loads(line[5:].strip())
            except ValueError:
                continue                          # 非 JSON 行按噪声丢弃 — 小欧 2026-11-05
            if drv.event_session(payload) != session_id:
                continue                          # 并发不串流 — 小欧 2026-11-05
            yield payload
