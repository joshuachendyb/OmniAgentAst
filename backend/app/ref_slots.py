# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-14 小欧 新建: 引用槽位注册表(SlotWriter + SLOT_WRITERS + 编解码)。来源集合只由本表
#   keys 提供, 计划器(contract)与装配层(message_builder)同源取用, 消除"哪些来源有原生槽"的
#   第二份硬编码。仅依赖 app.wire_prefix 与 stdlib, 不依赖 contract/attachment_wire(防止循环) — 小欧-2026-11-14
#
# 2026-11-14 小欧 三堂会审整改: url_item_slot 删 str.encode('ascii') 冗余转码(b64 产物
#   本就是 ASCII str, len(str) 即字节数), 消双重解析 — 小欧-2026-11-14
#
# 2026-11-14 小欧 bug挖掘修复: attachment_slot 按 SLOT_ATTACHMENT_RE 全匹配校验 id 形态,
#   非 32hex id 不再写出正则不可识别的占位原样泄漏给模型(返回空串, 装配层回落文本块) — 小欧-2026-11-14
"""ref_slots — 引用槽位注册表: 来源 → (正则, 占位构造器)。

SLOT_WRITERS.keys() 是"可写原生槽来源"的唯一真源; make(ref) 恒返回一行 wire 文本
(占位或占位失败时的降级链接文本), 装配层直接拼接, 不再按 source_kind 分派。
"""
import base64
import re
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from app.wire_prefix import (
    SLOT_ATTACHMENT_RE,
    SLOT_URL_RE,
    SLOT_LABEL_ATTACHMENT,
    SLOT_LABEL_URL,
)

_URL_ITEM_MAX = 512  # b64url 编码上限; 超长不写占位, 装配期降级链接文本


def attachment_slot(ref: dict) -> str:
    aid = str(ref.get("attachment_id") or "")
    # 占位必须可被 SLOT_ATTACHMENT_RE 识别: 非 32hex id 不写占位(装配层回落文本块), 防原样泄漏
    return (f"[[ATTACHMENT:{aid}]]"
            if SLOT_ATTACHMENT_RE.fullmatch(f"[[ATTACHMENT:{aid}]]") else "")


def url_item_slot(item: dict) -> Tuple[str, str]:
    """URL → (占位, 链接文本)。编码超 512B 返回 ("", 链接文本) —— 不产生坏占位。"""
    url = str(item.get("url") or "")
    enc = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii").rstrip("=")
    if len(enc) > _URL_ITEM_MAX:
        return "", url
    return f"[[URL_ITEM:{enc}]]", url


def decode_url_item(token: str) -> str:
    pad = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode(token + pad).decode("utf-8", errors="replace")


def _make_attachment(ref: dict) -> str:
    slot = attachment_slot(ref)
    return f"{SLOT_LABEL_ATTACHMENT}: {slot}\n" if slot else ""


def _make_url(ref: dict) -> str:
    slot, link = url_item_slot(ref)
    return (f"{SLOT_LABEL_URL}: {slot}\n" if slot
            else f"{SLOT_LABEL_URL}: (链接文本) {link}\n")


@dataclass(frozen=True)
class SlotWriter:
    pattern: re.Pattern
    make: Callable[[dict], str]


SLOT_WRITERS: Dict[str, SlotWriter] = {
    "attachment": SlotWriter(SLOT_ATTACHMENT_RE, _make_attachment),
    "url": SlotWriter(SLOT_URL_RE, _make_url),
}
