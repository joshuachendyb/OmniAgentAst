# -*- coding: utf-8 -*-
"""厂商响应 → 工具生成物规格摘要（标准字段映射唯一真源）。

各厂商字段名不统一，中央别名表把标准规格键映射到厂商候选键名：命中即显示，未命中不显示，不猜不编造。
标准规格: 图像=尺寸/格式/耗时；视频=时长+清晰度/质量档/耗时。新增厂商只往候选里加名字，工具与文案零改动 — 小欧-2026-11-21
"""
from typing import Any, Dict, Tuple

# 标准规格键 → 厂商键名候选(按优先级)
_SPEC_ALIASES: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "image": {
        "size": ("size", "resolution", "image_size"),
        "format": ("output_format", "format", "image_format", "mime_type"),
    },
    "video": {
        "seconds": ("seconds", "duration", "video_seconds"),
        "size": ("size", "resolution", "video_size"),
        "quality": ("quality", "quality_level"),
    },
}

# 任务时间戳: 视频异步任务两端齐才有耗时, 图类同步响应多只有 start 端
_TS_ALIASES = {
    "start": ("created_at", "created", "created_time", "started_at"),
    "end": ("completed_at", "completed", "finished_at", "done_at"),
}

# summary 里的耗时措辞(图像/视频统一)
_DURATION_LABEL = "用时"


def _pick(meta: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    """按候选顺序取首个非空标量；空串/0/bool 视为未命中"""
    for key in keys:
        val = meta.get(key)
        if isinstance(val, bool) or not isinstance(val, (str, int, float)):
            continue
        text = str(val).strip()
        if text and text not in ("0", "0.0"):
            return text
    return ""


def vendor_duration_ms(meta: Dict[str, Any]) -> int:
    """厂商侧耗时(毫秒) = end - start；缺任一端或倒挂返回 0"""
    try:
        start = int(float(_pick(meta, _TS_ALIASES["start"]) or 0))
        end = int(float(_pick(meta, _TS_ALIASES["end"]) or 0))
    except (TypeError, ValueError):
        return 0
    if not start or not end or end < start:
        return 0
    delta = end - start
    return delta if start >= 10 ** 11 else delta * 1000  # 13 位毫秒时间戳不再乘 1000


def build_vendor_spec(kind: str, meta: Dict[str, Any], duration_ms: int) -> Tuple[Dict[str, Any], str]:
    """厂商 meta → (metrics 规格项, summary 规格尾段)；映射不到的字段不进这两处(仍原样在 other_data) — 小欧-2026-11-21"""
    aliases = _SPEC_ALIASES.get(kind, {})
    spec = {key: _pick(meta, names) for key, names in aliases.items()}
    # 值统一 {value,text} 形: 前端工具行标签只认 text/value, 裸标量会渲染成空标签
    metrics: Dict[str, Any] = {k: {"value": v, "text": v} for k, v in spec.items() if v}

    usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
    for key in ("total_tokens", "output_tokens"):
        val = usage.get(key)
        if isinstance(val, int) and not isinstance(val, bool) and val:
            metrics[key] = {"value": val, "text": str(val)}

    if kind == "image":
        segs = [p for p in (spec.get("size"), f"{spec['format']} 格式" if spec.get("format") else "") if p]
    else:
        dim = " ".join(p for p in (f"{spec['seconds']} 秒" if spec.get("seconds") else "", spec.get("size", "")) if p)
        if spec.get("quality"):
            dim = f"{dim}（{spec['quality']}）" if dim else spec["quality"]
        segs = [dim] if dim else []
    if duration_ms:
        segs.append(f"{_DURATION_LABEL} {duration_ms // 1000} 秒")
    return metrics, "".join(f"，{s}" for s in segs)
