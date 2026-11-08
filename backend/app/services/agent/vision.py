# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 小欧 新建: 视觉通道(S2)唯一判定与 parts 生成 — 小欧-2026-11-04
# 2026-11-08 小欧 对照 [14] 字段统一: 能力判定只读 input_modalities(不碰 capabilities) — 小欧-2026-11-08
# 2026-11-08 小欧 修: 配置根是 ai(原读顶层 providers 恒空 → 看图通道永不启用); 模型名含 . / 故逐级字面键取 — 小欧-2026-11-08

"""services.agent.vision — 视觉通道(S2, 图片类型阶段)。

设计边界:
  1. conversation_history **恒为 str**: 图片以 `[[IMAGE_ATTACHMENT:<id>]]` 占位入列,
     压缩/裁剪/持久化/回执全部零改动;
  2. 仅在 wire 边界(message_builder.expand_vision_parts)把占位展开成 OpenAI `image_url` parts,
     且须在落盘/日志取占位原文之后调用(防 base64 入库/入日志);
  3. 能力判定只看模型配置 `input_modalities` 是否含 image(统一后唯一真源, 不写死模型名, 无 capabilities 分支);
  4. 展开失败(记录没了/图超限/读不出)退化为一行说明文字, 不阻断本轮;
  5. 生图/生视频(output)能力不参与判定: S2 只看 input 维度, 生图模型(input 无 image)不会被误判为看图。
"""
import asyncio
import base64
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_config
from app.logger import logger

IMAGE_SLOT_RE = re.compile(r"\[\[IMAGE_ATTACHMENT:([0-9a-f]{32})\]\]")
# 单图内联上限: base64 膨胀 4/3, 2MB 原图 → ~2.7MB 文本, 再大既慢又易撞窗口
VISION_INLINE_MAX_BYTES = 2 * 1024 * 1024

# 手动缓存(data URL 按 绝对路径+mime): 同一任务多轮 LLM 调用不重复 base64; 最多 8 张, 内存上限约 22MB。
# 不用 lru_cache: 异步读盘需 asyncio.to_thread 卸载事件循环, lru_cache 不支持异步函数 (Agnes 补)。
_data_url_cache: Dict[Tuple[str, str], str] = {}
_DATA_URL_MAX = 8


def supports_image_input(llm_model: Any) -> bool:
    """模型是否接受 image 入参（看图）。

    统一后唯一读 config.model_meta.input_modalities（[14] §3 字段统一），
    不再有 capabilities 分支；不写死模型名。走 chat/completions 的看图能力。
    """
    provider = getattr(llm_model, "provider", "") or ""
    model = getattr(llm_model, "model", "") or ""
    if not provider or not model:
        return False
    provider_cfg = (get_config().get("ai") or {}).get(provider) or {}
    meta = (provider_cfg.get("model_meta") or {}).get(model) or {}
    mods = meta.get("input_modalities") or []
    return isinstance(mods, list) and "image" in mods


def split_vision_refs(refs: Optional[list]) -> Tuple[list, list]:
    """(文本引用, 可内联图片引用)。只认 kind=attachment 且 mime=image/*。"""
    text_refs: List[Dict[str, Any]] = []
    image_refs: List[Dict[str, Any]] = []
    for r in refs or []:
        is_img = (r.get("kind") == "attachment"
                  and str(r.get("mime") or "").startswith("image/"))
        (image_refs if is_img else text_refs).append(r)
    return text_refs, image_refs


def image_slot(ref: Dict[str, Any]) -> str:
    """纯文本占位: 由 wire 层替换为 image part; 无 id 时退化为空(不产生坏锚)。"""
    aid = str(ref.get("attachment_id") or "")
    return f"[[IMAGE_ATTACHMENT:{aid}]]" if aid else ""


async def _data_url(stored_path: str, mime: str) -> str:
    """读图 + base64 编码, 经 asyncio.to_thread 卸载出事件循环(Agnes 补: 原同步 open 阻塞)。"""
    key = (stored_path, mime)
    cached = _data_url_cache.get(key)
    if cached:
        return cached

    def _read_and_encode() -> str:
        with open(stored_path, "rb") as fh:
            return f"data:{mime};base64,{base64.b64encode(fh.read()).decode('ascii')}"

    url = await asyncio.to_thread(_read_and_encode)
    if len(_data_url_cache) >= _DATA_URL_MAX:
        _data_url_cache.pop(next(iter(_data_url_cache)), None)  # 最旧淘汰
    _data_url_cache[key] = url
    return url


async def expand_image_slots(text: str) -> Any:
    """含占位 → OpenAI parts; 无占位原样返回 str(零退化)。"""
    if not IMAGE_SLOT_RE.search(text or ""):
        return text
    from app.attachments.attachment_service import get_attachment  # 延迟导入防循环

    parts: List[Dict[str, Any]] = []
    pending: List[str] = []
    cursor = 0

    def _flush() -> None:
        if pending:
            parts.append({"type": "text", "text": "".join(pending)})
            pending.clear()

    for m in IMAGE_SLOT_RE.finditer(text):
        pending.append(text[cursor:m.start()])
        att = get_attachment(m.group(1))
        reason = ""
        if not att:
            reason = "附件记录已失效"
        elif int(att.get("size") or 0) > VISION_INLINE_MAX_BYTES:
            reason = f"图片超过 {VISION_INLINE_MAX_BYTES // (1024 * 1024)}MB 未随消息发送"
        else:
            try:
                url = await _data_url(att["stored_path"], att.get("mime") or "image/png")
            except OSError as e:
                logger.warning(f"[vision] 读图失败 id={m.group(1)} err={e}")
                reason = "图片文件不可读"
            else:
                _flush()
                parts.append({"type": "image_url", "image_url": {"url": url}})
        if reason:
            name = att.get("original_name") if att else m.group(1)
            pending.append(f"[图片附件未内联: {name} — {reason}]\n")
        cursor = m.end()
    pending.append(text[cursor:])
    _flush()
    return parts