# -*- coding: utf-8 -*-
"""streamer.py — 下游事件流 → 上游 SSE 帧（通用层; 端点与判别由驱动挂钩给出, D25）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
对齐: 7.4 流式转发 / 4.5 帧序列与延迟提交 / 5.6 工具模式整包

要点:
  - 帧粒度: 下游给几帧发几帧, 不做逐字切分（1.5 N4; 实测 93 字回答仅 4 帧, 4.5）;
  - 过滤: 事件的会话归属由驱动 event_session() 给出, 不等即并发串流（7.4）;
  - 延迟提交: gateway 在首个可映射 delta 到达前【不提交】响应头（4.5 状态机）,
    本文件只负责帧的形状与订阅骨架, 提交时机在 gateway._stream_text;
  - 事件情态语义归驱动 event_class()（方言）; 本文件只认 "content/reasoning/
    idle/error/ignore/http_error" 六种归一值。

编辑历史:
  2026-11-05 删死代码 sse_comment(全仓零调用); HEARTBEAT_S→WAIT_SLICE_S(实为等待切片, 不发 ping);
             未接线的 15 s ": ping" 心跳仍按 4.5 挂账, 接线时再加 -- 小欧
"""
from __future__ import annotations

import json

WAIT_SLICE_S = 15          # 等待事件的最长切片(4.5); ": ping" 心跳仍未接线, 见编辑历史
FIRST_FRAME_S = 60        # 60 s 无任何 delta → 提交 504（4.5 / 7.6 流式首帧）
SILENT_S = 180            # 已出字后长时间无新帧（7.6 流式静默）


def sse(data):
    """一帧 SSE。data: 行 + 空行收尾（宿主只解析 data: 行, 4.8.3）。"""
    return "data: %s\n\n" % json.dumps(data, ensure_ascii=False)


def first_frame():
    """首帧: delta.role=assistant（4.5 帧序列第 1 帧的硬要求）。"""
    return sse({"choices": [{"index": 0, "delta": {"role": "assistant"},
                             "finish_reason": None}]})


def delta_frame(content="", reasoning="", tool_calls=None):
    """驱动归一的正文 / 思考 / 工具调用 → 4.8.3 三种 delta 形状。"""
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
    """末帧: 空 delta + finish_reason + usage（无条件携带, 4.5）+ [DONE]。"""
    body = {"id": "", "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}]}
    if usage is not None:
        body["usage"] = usage
    return sse(body) + "data: [DONE]\n\n"


async def iter_events(client, session_id, drv):
    """订阅驱动给出的下游事件端点（httpx 流式），按驱动会话过滤, 逐条 yield payload。

    订阅失败不抛——yield {"kind": "http_error", "status": ...} 交给 gateway
    在提交响应头前变成干净 HTTP 错误（4.5 延迟提交的另一半）。子会话结束时
    gateway 主动 aclose() 本生成器 → async with 退出 → 连接释放（7.4 终止行）。
    """
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
                continue                          # 非 JSON 行按噪声丢弃
            if drv.event_session(payload) != session_id:
                continue                          # 并发不串流（7.4 过滤行）
            yield payload
