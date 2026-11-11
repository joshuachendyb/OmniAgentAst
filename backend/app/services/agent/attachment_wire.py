# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建(自 vision.py 更名收窄): 附件/URL 占位编解码 + wire 展开,
#   能力判定归 capability, 识别归 contract/extract, 载荷构造归 media_payload — 小欧-2026-11-11

"""services.agent.attachment_wire — 附件/URL 占位的 wire 展开(占位级)。

设计边界:
  1. conversation_history **恒为 str**: 附件 `[[ATTACHMENT:<id>]]` / URL `[[URL_ITEM:<b64url>]]`
     占位入列, 压缩/裁剪/持久化/回执零改动;
  2. 仅在 wire 边界(message_builder.expand_attachment_parts)把占位展开成 parts,
     且须在落盘/日志取占位原文之后调用(防 base64 入库/入日志);
  3. 能力判定归 capability.py(本模块零判定); 识别归 contract/extract(零模型参数);
  4. 展开失败(记录没了/载荷超限/读不出)退化为一行说明文字, 不阻断本轮;
  5. 占位自描述: 展开期按当前模型画像重算 transport, 无请求期状态依赖。
"""
import base64
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.attachments import contract, extract
from app.attachments.extract import classify, classify_url
from app.services.agent import capability
from app.services.agent.media_payload import build_logical_part, ensure_payload, to_wire_part

ATTACHMENT_SLOT_RE = re.compile(r"\[\[ATTACHMENT:([0-9a-f]{32})\]\]")
URL_SLOT_RE = re.compile(r"\[\[URL_ITEM:([A-Za-z0-9_\-=]+)\]\]")
_SLOT_RE = re.compile(f"{ATTACHMENT_SLOT_RE.pattern}|{URL_SLOT_RE.pattern}")
_URL_ITEM_MAX = 512          # b64url 编码上限; 超长不写占位, 装配期降级链接文本


def attachment_slot(ref: Dict[str, Any]) -> str:
    aid = str(ref.get("attachment_id") or "")
    return f"[[ATTACHMENT:{aid}]]" if aid else ""


def url_item_slot(item: Dict[str, Any]) -> Tuple[str, str]:
    """URL → (占位, 链接文本)。编码超 512B 返回 ("", 链接文本) —— 不产生坏占位。"""
    url = str(item.get("url") or "")
    enc = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    if len(enc.encode("ascii")) > _URL_ITEM_MAX:
        return "", url
    return f"[[URL_ITEM:{enc}]]", url


def decode_url_item(token: str) -> str:
    pad = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + pad).decode("utf-8", errors="replace")


async def expand_attachment_slots(text: str, llm_model: Any) -> Any:
    """占位级展开: 识别全部 ATTACHMENT/URL_ITEM 占位, 按当前模型画像分流。
    url → build_url_part 直传; inline → ensure_payload → to_wire_part;
    none → 占位原位替换为降级文本。无占位原样返回 str。"""
    if not (ATTACHMENT_SLOT_RE.search(text or "") or URL_SLOT_RE.search(text or "")):
        return text
    prof = capability.profile(llm_model)
    parts: List[Dict[str, Any]] = []
    pending: List[str] = []
    cursor = 0
    for m in _SLOT_RE.finditer(text):
        pending.append(text[cursor:m.start()])
        part, fallback = await _expand_one(m, prof)
        if part:
            if pending:
                parts.append({"type": "text", "text": "".join(pending)})
                pending.clear()
            parts.append(part)
        else:
            pending.append(fallback + "\n")
        cursor = m.end()
    pending.append(text[cursor:])
    if pending:
        parts.append({"type": "text", "text": "".join(pending)})
    parts = [p for p in parts if p.get("text") or p.get("type") != "text"]
    return parts if len(parts) > 1 else (parts[0].get("text") if parts else text)


async def _expand_one(m: "re.Match[str]", prof: Dict[str, Any]) -> Tuple[Any, str]:
    """单个占位 → (wire part, 失败降级文字)。不抛异常断轮。"""
    if m.group(1):
        return await _expand_attachment(m.group(1), prof)
    return await _expand_url(decode_url_item(m.group(2)), prof)


async def _expand_attachment(aid: str, prof: Dict[str, Any]) -> Tuple[Any, str]:
    from app.attachments.attachment_service import get_attachment  # 延迟导入防循环

    att = get_attachment(aid)
    if not att:
        return None, f"[附件未发送: {aid} — 附件记录已失效]"
    stored = str(att.get("stored_path") or att.get("path") or "")
    kind = att.get("kind") or classify(Path(stored), str(att.get("mime") or ""),
                                       int(att.get("size") or 0))
    route = contract.KIND_CONTRACT[("attachment", kind)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if not (cap and cap.native):
        return None, f"[附件未发送: {att.get('original_name') or aid} — 当前模型无原生通道]"
    logical, reason = await build_logical_part(kind, att)
    if not logical:
        return None, f"[附件未发送: {att.get('original_name') or aid} — {reason}]"
    part, reason = to_wire_part(logical)
    return (part, "") if part else (None, f"[附件未发送: {att.get('original_name') or aid} — {reason}]")


async def _expand_url(url: str, prof: Dict[str, Any]) -> Tuple[Any, str]:
    ck = classify_url(url)
    route = contract.KIND_CONTRACT[("url", ck)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if not (cap and cap.native):
        return None, extract._link_body(url)
    transport = "url" if "url" in cap.transport else "inline"
    logical, reason = await ensure_payload({"url": url, "content_kind": ck}, transport)
    if not logical:
        return None, f"[链接未转发: {url} — {reason}]"
    part, reason = to_wire_part(logical)
    return (part, "") if part else (None, f"[链接未转发: {url} — {reason}]")
