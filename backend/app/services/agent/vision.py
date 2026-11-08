# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 小欧 新建: 视觉通道唯一判定与 parts 生成 — 小欧-2026-11-04
# 2026-11-08 小欧 字段统一后: 能力判定只读 input_modalities(不碰 capabilities) — 小欧-2026-11-08
# 2026-11-08 小欧 修: 配置根是 ai(原读顶层 providers 恒空 → 看图通道永不启用); 模型名含 . / 故逐级字面键取 — 小欧-2026-11-08
# 2026-11-08 小欧 收口: 判定容忍 MIME 级 image/*; part 构造下沉 media_payload(唯一产出点) — 小欧-2026-11-08

"""services.agent.vision — 视觉通道(图片类型阶段)。

设计边界:
  1. conversation_history **恒为 str**: 图片以 `[[IMAGE_ATTACHMENT:<id>]]` 占位入列,
     压缩/裁剪/持久化/回执全部零改动;
  2. 仅在 wire 边界(message_builder.expand_vision_parts)把占位展开成 parts,
     且须在落盘/日志取占位原文之后调用(防 base64 入库/入日志);
  3. 能力判定只看模型配置 `input_modalities` 是否含 image(统一后唯一真源, 不写死模型名, 无 capabilities 分支);
  4. 展开失败(记录没了/图超限/读不出)退化为一行说明文字, 不阻断本轮;
  5. 生图/生视频(output)能力不参与判定: 只看 input 维度, 生图模型(input 无 image)不会被误判为看图;
  6. part 构造与内联缓存归 media_payload, 本模块只管占位识别与文本切分。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_config
from app.services.agent.media_payload import build_media_part

IMAGE_SLOT_RE = re.compile(r"\[\[IMAGE_ATTACHMENT:([0-9a-f]{32})\]\]")


def supports_image_input(llm_model: Any) -> bool:
    """模型是否接受 image 入参（看图）。

    统一后唯一读 config.model_meta.input_modalities（字段统一后唯一真源），
    不再有 capabilities 分支；不写死模型名。走 chat/completions 的看图能力。
    """
    provider = getattr(llm_model, "provider", "") or ""
    model = getattr(llm_model, "model", "") or ""
    if not provider or not model:
        return False
    provider_cfg = (get_config().get("ai") or {}).get(provider) or {}
    meta = (provider_cfg.get("model_meta") or {}).get(model) or {}
    mods = meta.get("input_modalities") or []
    if not isinstance(mods, list):
        return False
    # 容忍 MIME 级声明(image/jpeg 等): 远端词汇不统一, 精确等值会静默关掉看图 — 小欧-2026-11-08
    return any(isinstance(m, str) and (m == "image" or m.lower().startswith("image/")) for m in mods)


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
        if att:
            part, reason = await build_media_part("image", att)
        else:
            part, reason = None, "附件记录已失效"
        if part:
            _flush()
            parts.append(part)
        else:
            name = att.get("original_name") if att else m.group(1)
            pending.append(f"[图片附件未内联: {name} — {reason}]\n")
        cursor = m.end()
    pending.append(text[cursor:])
    _flush()
    return parts