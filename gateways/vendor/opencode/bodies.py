# -*- coding: utf-8 -*-
"""bodies.py — opencode 下游请求体构造（纯函数）。

编写人: 小欧    创建时间: 2026-11-05 19:40:00
依据: packages/schema/src/prompt-input.ts 与 protocol/src/groups/session.ts。

编辑历史:
  2026-11-05 从 opencode_client.py 摘出 session/prompt 两个请求体构造并转正为公有名 -- 小欧
  2026-11-05 原文件全仓零调用的客户端类已移出网关包 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
"""
from __future__ import annotations

from typing import Any, Optional

PROVIDER_ID = "opencode"


def session_body(model: str, title: Optional[str] = None, agent: Optional[str] = None,
                 metadata: Optional[dict] = None, permissions: Any = None,
                 parent_id: Optional[str] = None) -> dict:
    """建会话请求体; 值为 None 的字段一律不传, 协议无采样参数。— 小欧 2026-11-05"""
    body = {"model": {"providerID": PROVIDER_ID, "id": model}}
    if title is not None:
        body["title"] = title
    if agent is not None:
        body["agent"] = agent
    if metadata is not None:
        body["metadata"] = metadata
    if permissions is not None:
        body["permissions"] = permissions
    if parent_id is not None:
        body["parentID"] = parent_id
    return body


def prompt_body(text: str, files: Optional[list] = None, agents: Optional[list] = None,
                skills: Optional[list] = None, metadata: Optional[dict] = None,
                delivery: Optional[str] = None, resume: Optional[bool] = None,
                message_id: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    """发消息请求体: files/agents/skills 附件, delivery=steer|queue, resume=False 只入队;
    extra 原样合并进 body。— 小欧 2026-11-05"""
    body = {"text": text}
    if files:
        body["files"] = files
    if agents:
        body["agents"] = agents
    if skills:
        body["skills"] = skills
    if metadata is not None:
        body["metadata"] = metadata
    if delivery is not None:
        body["delivery"] = delivery
    if resume is not None:
        body["resume"] = resume
    if message_id is not None:
        body["id"] = message_id
    if extra:
        body.update(extra)
    return body
