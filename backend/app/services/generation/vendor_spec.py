# -*- coding: utf-8 -*-
"""厂商响应 → 工具生成物的 metrics 规格段与 other_data 用量（标准字段映射唯一真源）。

各厂商字段名不统一，中央别名表把标准规格键映射到厂商候选键名：命中即显示，未命中不显示，不猜不编造。
标准规格: 图像=尺寸/格式/用时；视频=时长+清晰度/质量档/用时。新增厂商只往候选里加名字，工具与文案零改动。
落点分工: 规格与有价值标量进 metrics(LLM/前端可见), other_data 只装厂商返回的 token 用量数字 — 小欧-2026-11-21
"""
from typing import Any, Dict, Optional, Tuple

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

# 任务时间戳: 视频异步任务两端齐才有用时, 图类同步响应多只有 start 端
_TS_ALIASES = {
    "start": ("created_at", "created", "created_time", "started_at"),
    "end": ("completed_at", "completed", "finished_at", "done_at"),
}

# 有价值但非规格的厂商字段 → metrics 键名; 映射不到就不显示
_VALUE_ALIASES: Dict[str, Tuple[str, ...]] = {
    "revised_prompt": ("revised_prompt",),          # 厂商改写后的提示词, 说明实际生成了什么
    "error_code": ("code", "error_code"),            # 失败态错误码(排查一手信息)
    "request_id": ("request_id", "trace_id"),        # 厂商侧追单凭据
}
# 任务号: 成功时产物已在手, 只用于失败态追单, 故仅失败时进 metrics
_TASK_ALIASES = ("task_id", "video_id", "id")
# 进 metrics 的用量摘要键(完整 usage 数字落 other_data)
_USAGE_METRICS = ("total_tokens", "output_tokens")


def _pick(source: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    """按候选顺序取首个非空标量；空串/0/bool 视为未命中"""
    for key in keys:
        val = source.get(key)
        if isinstance(val, bool) or not isinstance(val, (str, int, float)):
            continue
        text = str(val).strip()
        if text and text not in ("0", "0.0"):
            return text
    return ""


def _metric(value: Any) -> Dict[str, Any]:
    """metrics 单值统一 {value,text} 形: 前端工具行标签只认 text/value, 裸标量会渲染成空"""
    return {"value": value, "text": str(value)}


def _spec_source(meta: Dict[str, Any]) -> Dict[str, Any]:
    """取值视图: 顶层优先, data[0] 兜底(部分厂商把参数放在产物项里)"""
    head = meta.get("data")
    if isinstance(head, list) and head and isinstance(head[0], dict):
        return {**head[0], **meta}
    return meta


def vendor_duration_ms(meta: Dict[str, Any]) -> int:
    """厂商侧用时(毫秒) = end - start；缺任一端或倒挂返回 0"""
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
    """厂商 meta → (metrics 规格项, summary 规格尾段)；映射不到的字段不进这两处 — 小欧-2026-11-21"""
    aliases = _SPEC_ALIASES.get(kind)
    if aliases is None:  # 未定义模态: 不猜, 不出规格
        return {}, ""
    source = _spec_source(meta)
    spec = {key: _pick(source, names) for key, names in aliases.items()}
    if "/" in spec.get("format", ""):  # mime_type 命中时取子类型(image/png → png)
        spec["format"] = spec["format"].rsplit("/", 1)[-1]
    metrics: Dict[str, Any] = {k: _metric(v) for k, v in spec.items() if v}

    if kind == "image":
        segs = [p for p in (spec.get("size"), f"{spec['format']} 格式" if spec.get("format") else "") if p]
    else:
        dim = " ".join(p for p in (f"{spec['seconds']} 秒" if spec.get("seconds") else "", spec.get("size", "")) if p)
        if spec.get("quality"):
            dim = f"{dim}（{spec['quality']}）" if dim else spec["quality"]
        segs = [dim] if dim else []
    if duration_ms:
        segs.append(f"用时 {duration_ms // 1000} 秒")
    return metrics, "".join(f"，{s}" for s in segs)


def build_vendor_fields(kind: str, result: Dict[str, Any], effective_model: str
                        ) -> Tuple[Dict[str, Any], str, Optional[Dict[str, Any]], str]:
    """生成回调出参 → (metrics, summary 规格段, other_data, 实际模型) — 小欧-2026-11-21

    metrics = 模型 + 标准规格 + 用量摘要 + 有价值标量(改写提示词/失败错误码/request id, 失败态再加任务号);
    other_data 只装厂商返回的 token 用量数字, 其余厂商原文不落库(引擎已剔产物本体, 这里再收窄到用量);
    实际模型以厂商回显为准(无则用生效模型), 由本函数直回, 调用方不再从 metrics 反查。
    """
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    model = str(meta.get("model") or "") or effective_model
    # 编排层已算过的直接用; 缺失时从 meta 时间戳自算, 不因上游漏传而丢规格
    duration_ms = int(result.get("vendor_duration_ms") or 0) or vendor_duration_ms(meta)
    spec_metrics, suffix = build_vendor_spec(kind, meta, duration_ms)

    metrics: Dict[str, Any] = {"model": _metric(model)}
    metrics.update(spec_metrics)
    usage = meta.get("usage") if isinstance(meta.get("usage"), dict) else {}
    for key in _USAGE_METRICS:
        val = usage.get(key)
        if isinstance(val, int) and not isinstance(val, bool) and val:
            metrics[key] = _metric(val)

    source = _spec_source(meta)
    for name, keys in _VALUE_ALIASES.items():
        val = _pick(source, keys)
        if val:
            metrics[name] = _metric(val)
    if result.get("ok") is False:
        task = _pick(source, _TASK_ALIASES)
        if task:
            metrics["task_id"] = _metric(task)

    usage_numbers = {k: v for k, v in usage.items()
                     if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return metrics, suffix, ({"usage": usage_numbers} if usage_numbers else None), model
