# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建(自 vision.py 更名收窄): 附件/URL 占位编解码 + wire 展开,
#   能力判定归 capability, 识别归 contract/extract, 载荷构造归 media_payload — 小欧-2026-11-11
# 2026-11-11 小欧 补设计缺口: URL·text/richdoc 下载后按契约文本出口注入正文(失败退链接文本);
#   附件无原生通道改复用注入文本(原一行说明丢正文) — 小欧-2026-11-11
# 2026-11-11 小欧 P5 指标埋点: 展开结果逐项 [cap-metric](native/degraded/native_fail) +
#   降级/失败 WARNING 留痕(原先静默, 排障无迹) — 小欧-2026-11-11


# 2026-11-14 小欧 槽位函数/正则迁出: 编解码与正则移入 ref_slots/wire_prefix 单一真源, 本模块
#   改为再导出+消费(既有 import 路径不变), 展开逻辑不变 — 小欧-2026-11-14

# 2026-11-14 小欧 扫描正则改由 SLOT_WRITERS 注册表派生(4.4.3 纪律3): 组合正则不再手写
#   re.compile, 新增来源加注册表一条即自动纳入扫描, 消扩展点漏改 — 小欧-2026-11-14

# 2026-11-14 小欧 三堂会审整改: ①删 attachment_slot/url_item_slot 兼容再导出(禁止 backward,
#   消费方一律走 ref_slots 单源); ②占位展开改 _EXPANDERS 注册表按 m.lastgroup 派发
#   (wire_prefix 正则命名组名=注册表键), 删 group(1)/group(2) 硬编码分组号, 新增来源漏配
#   展开器 KeyError 响亮暴露不再静默错位; ③URL 文本抓取改契约单判据 route.fetch=="text",
#   删 ck in ("text","richdoc") 双判据 — 小欧-2026-11-14
#
# 2026-11-14 小欧 bug挖掘修复: expand_attachment_slots 收尾折叠补非 text 单 part 分支 —— 消息仅含
#   一个原生 part 时原返回 None 丢整个消息内容, 现原样返回 parts; 空展开原样返回 text — 小欧-2026-11-14
#
# 2026-11-14 小欧 第7章7.4 阶段B 收权: expand_attachment_slots/_expand_one/_EXPANDERS 增 session_id
#   透传, _expand_attachment 改 get_attachment_scoped(跨会话 id 拒绝, 与 resolver 同口径) — 小欧-2026-11-14
# 2026-11-15 小欧 语义前缀归一: 降级说明文案字面量收归 app.wire_prefix(INLINE_ATT_UNSENT/INLINE_URL_UNSENT),
#   消除散落字面量 — 小欧-2026-11-15


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
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlsplit

from app.attachments import contract, extract
from app.attachments.extract import classify, classify_url
from app.attachments.observability import metric
from app.logger import logger
from app.services.agent import capability
from app.services.agent.media_payload import build_logical_part, ensure_payload, to_wire_part

from app.ref_slots import SLOT_WRITERS, decode_url_item
from app.wire_prefix import INLINE_ATT_UNSENT, INLINE_URL_UNSENT

_SLOT_RE = re.compile("|".join(w.pattern.pattern for w in SLOT_WRITERS.values()))

# 展开器注册表: 键 = SLOT_WRITERS 键 = wire_prefix 正则命名组名, 绑定见模块底部。
# _expand_one 按 m.lastgroup 派发, 新增来源漏配展开器即 KeyError 响亮暴露, 不静默错位。
_EXPANDERS: Dict[str, Any] = {}


async def _expand_one(m: "re.Match[str]", prof: Dict[str, Any], model: str = "",
                      session_id: str | None = None) -> Tuple[Any, str]:
    """单个占位 → (wire part, 失败降级文字)。不抛异常断轮。"""
    name = m.lastgroup
    return await _EXPANDERS[name](m.group(name), prof, model, session_id)


async def expand_attachment_slots(text: str, llm_model: Any,
                                  session_id: str | None = None) -> Any:
    """占位级展开: 识别全部 ATTACHMENT/URL_ITEM 占位, 按当前模型画像分流。
    url → build_url_part 直传; inline → ensure_payload → to_wire_part;
    none → 占位原位替换为降级文本。无占位原样返回 str。
    session_id: 附件记录会话收权(跨会话 id 回落降级文本, 与 resolver 同口径)。"""
    if not _SLOT_RE.search(text or ""):
        return text
    prof = capability.profile(llm_model)
    parts: List[Dict[str, Any]] = []
    pending: List[str] = []
    cursor = 0
    for m in _SLOT_RE.finditer(text):
        pending.append(text[cursor:m.start()])
        part, fallback = await _expand_one(m, prof, str(llm_model), session_id)
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
    if not parts:
        return text
    if len(parts) == 1 and parts[0].get("type") == "text":
        return parts[0]["text"]
    return parts


async def _expand_attachment(aid: str, prof: Dict[str, Any], model: str = "",
                             session_id: str | None = None) -> Tuple[Any, str]:
    from app.attachments.attachment_service import get_attachment_scoped  # 延迟导入防循环

    att = get_attachment_scoped(aid, session_id)
    if not att:
        return None, INLINE_ATT_UNSENT.format(why=f"{aid} — 附件记录已失效")
    stored = str(att.get("stored_path") or att.get("path") or "")
    kind = att.get("kind") or classify(Path(stored), str(att.get("mime") or ""),
                                       int(att.get("size") or 0))
    route = contract.KIND_CONTRACT[("attachment", kind)]
    cap = prof.get(route.native_modality) if route.native_modality else None
    if not (cap and cap.native):
        logger.warning("[wire] 附件降级 id=%s kind=%s model=%s reason=无原生通道", aid, kind, model)
        metric("degraded", "attachment", kind, model, "无原生通道")
        return None, _inject_fallback(att, aid)
    logical, reason = await build_logical_part(kind, att)
    if not logical:
        logger.warning("[wire] 附件原生载荷失败 id=%s kind=%s model=%s reason=%s", aid, kind, model, reason)
        metric("native_fail", "attachment", kind, model, reason)
        return None, INLINE_ATT_UNSENT.format(why=f"{att.get('original_name') or aid} — {reason}")
    part, reason = to_wire_part(logical)
    if not part:
        logger.warning("[wire] 附件原生方言失败 id=%s kind=%s model=%s reason=%s", aid, kind, model, reason)
        metric("native_fail", "attachment", kind, model, reason)
        return None, INLINE_ATT_UNSENT.format(why=f"{att.get('original_name') or aid} — {reason}")
    metric("native", "attachment", kind, model)
    return part, ""


def _inject_fallback(att: Dict[str, Any], aid: str) -> str:
    """无原生通道 → 复用契约文本出口(注入文本); 出口也失败退一行说明。"""
    try:
        return extract.build_inject_text(att)
    except Exception:  # noqa: BLE001 — 文本出口失败不抛, 退一行说明不断轮
        return INLINE_ATT_UNSENT.format(why=f"{att.get('original_name') or aid} — 当前模型无原生通道")


async def _expand_url(token: str, prof: Dict[str, Any], model: str = "",
                      session_id: str | None = None) -> Tuple[Any, str]:
    url = decode_url_item(token)
    ck = classify_url(url)
    route = contract.KIND_CONTRACT[("url", ck)]
    if route.fetch == "text":   # 契约单判据: 文本抓取进正文; 媒体内联由 ensure_payload 自理
        return await _fetch_extract_text(url, ck, model)
    cap = prof.get(route.native_modality) if route.native_modality else None
    if not (cap and cap.native):
        logger.warning("[wire] URL 降级 kind=%s model=%s url=%s reason=无原生通道", ck, model, url)
        metric("degraded", "url", ck, model, "无原生通道")
        return None, extract.link_body(url)
    transport = "url" if "url" in cap.transport else "inline"
    logical, reason = await ensure_payload({"url": url, "content_kind": ck}, transport)
    if not logical:
        logger.warning("[wire] URL 原生载荷失败 kind=%s model=%s url=%s reason=%s", ck, model, url, reason)
        metric("native_fail", "url", ck, model, reason)
        return None, INLINE_URL_UNSENT.format(why=f"{url} — {reason}")
    part, reason = to_wire_part(logical)
    if not part:
        logger.warning("[wire] URL 原生方言失败 kind=%s model=%s url=%s reason=%s", ck, model, url, reason)
        metric("native_fail", "url", ck, model, reason)
        return None, INLINE_URL_UNSENT.format(why=f"{url} — {reason}")
    metric("native", "url", ck, model)
    return part, ""


async def _fetch_extract_text(url: str, ck: str, model: str = "") -> Tuple[Any, str]:
    """text/richdoc URL → 下载字节后按契约文本出口注入正文(与模型视觉能力无关);
    下载/解析失败退链接文本, 不抛异常断轮。"""
    from app.services.agent.remote_fetch import fetch_bytes  # 延迟导入防循环
    raw, reason = await fetch_bytes(url, ck)
    if raw:
        name = Path(urlsplit(url).path).name or url
        att = {"original_name": name, "url": url}
        try:
            body = (extract.text_body_from_bytes(att, raw) if ck == "text"
                    else extract.richdoc_body_from_bytes(att, raw, filename=name))
            metric("native", "url", ck, model, "fetched_text")
            return {"type": "text", "text": body}, ""
        except Exception as e:  # noqa: BLE001 — 解析失败退链接文本
            logger.warning("[wire] URL 正文抽取失败 kind=%s url=%s err=%s", ck, url, type(e).__name__)
            metric("extract_fail", "url", ck, model, f"解析失败:{type(e).__name__}")
    link = extract.link_body(url)
    if reason:
        metric("degraded", "url", ck, model, f"获取正文失败:{reason}")
    return None, (f"{link}\n(自动获取正文失败: {reason})" if reason else link)


# 展开器注册表绑定(键 = SLOT_WRITERS 键 = wire_prefix 正则命名组名)
_EXPANDERS["attachment"] = _expand_attachment
_EXPANDERS["url"] = _expand_url
